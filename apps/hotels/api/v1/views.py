"""
REST API v1 - Property Search, Detail, Availability & Pricing

Endpoints:
  GET  /api/v1/properties/                        — Filtered hotel listing
  GET  /api/v1/properties/<id>/                   — Property detail
  GET  /api/v1/search/                            — Full-text search
  GET  /api/v1/properties/<id>/availability/      — Date-range availability + room prices
  POST /api/v1/pricing/quote/                     — Full pricing breakdown

All responses follow the envelope:
  { "success": true,  "data": { ... } }
  { "success": false, "error": { "code": "...", "message": "..." } }
"""
import logging
from datetime import date as date_type
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from apps.hotels.ota_selectors import (
    ota_visible_properties,
    apply_search_filters,
    apply_date_inventory_filter,
    apply_sorting,
    get_filter_counts,
    get_popular_areas,
)
from apps.hotels.selectors import get_property_detail
from apps.core.throttles import SearchThrottle
from apps.core.service_guard import require_service_enabled
from rest_framework.decorators import throttle_classes
from .serializers import PropertyCardSerializer, PropertyDetailSerializer

logger = logging.getLogger('zygotrip.api.hotels')


# ──────────────────────────────────────────────────────────────────────────────
# SAFE INTELLIGENCE FALLBACKS (Step 4 — never crash on missing intelligence data)
# ──────────────────────────────────────────────────────────────────────────────

def _safe_quality_score(property_obj):
    """Return HotelQualityScore data or empty defaults if missing."""
    try:
        from apps.core.models import HotelQualityScore
        qs = HotelQualityScore.objects.get(property=property_obj)
        return {
            'overall_score': float(qs.overall_score) if qs.overall_score else 0,
            'is_top_rated': qs.is_top_rated,
            'is_value_pick': qs.is_value_pick,
            'is_trending': qs.is_trending,
            'computed_at': qs.updated_at.isoformat() if hasattr(qs, 'updated_at') and qs.updated_at else None,
        }
    except Exception:
        return {
            'overall_score': 0,
            'is_top_rated': False,
            'is_value_pick': False,
            'is_trending': False,
            'computed_at': None,
        }


def _safe_demand_forecast(property_obj):
    """Return DemandForecast data or empty defaults if missing."""
    try:
        from apps.core.models import DemandForecast
        from django.utils import timezone as tz
        forecast = DemandForecast.objects.filter(
            property=property_obj,
            forecast_date__gte=tz.now().date(),
        ).order_by('forecast_date').first()
        if forecast:
            return {
                'forecast_date': str(forecast.forecast_date),
                'demand_score': float(forecast.demand_score) if forecast.demand_score else 0,
                'predicted_occupancy': float(forecast.predicted_occupancy) if hasattr(forecast, 'predicted_occupancy') and forecast.predicted_occupancy else None,
                'recommendation': getattr(forecast, 'recommendation', None),
            }
        return {'forecast_date': None, 'demand_score': 0, 'predicted_occupancy': None, 'recommendation': None}
    except Exception:
        return {'forecast_date': None, 'demand_score': 0, 'predicted_occupancy': None, 'recommendation': None}


def _safe_cache_get(key):
    """Redis-safe cache get — returns None on any Redis failure."""
    try:
        from django.core.cache import cache as _cache
        return _cache.get(key)
    except Exception:
        logger.warning("Redis unavailable for cache.get(%s), falling back to DB", key)
        return None


def _safe_cache_set(key, value, ttl=300):
    """Redis-safe cache set — silently fails on Redis unavailability."""
    try:
        from django.core.cache import cache as _cache
        _cache.set(key, value, ttl)
    except Exception:
        logger.warning("Redis unavailable for cache.set(%s), skipping cache write", key)


class HotelPagination(PageNumberPagination):
    """Standardised pagination for hotel listing endpoints."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': {
                'results': data,
                'pagination': {
                    'count': self.page.paginator.count,
                    'total_pages': self.page.paginator.num_pages,
                    'current_page': self.page.number,
                    'next': self.get_next_link(),
                    'previous': self.get_previous_link(),
                },
            },
        })


def _base_queryset():
    """Single source of truth for the public hotel queryset.

    S4: prefetch room_types with their images and amenities to prevent N+1
    when RoomTypeSerializer renders nested images/amenities fields.
    """
    return ota_visible_properties().prefetch_related(
        'images',
        'amenities',
        'room_types',
        'room_types__images',     # room-level gallery
        'room_types__amenities',  # room-level amenities
        'room_types__meal_plans', # room-level meal plans (RoomMealPlan table)
    )


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([SearchThrottle])
@require_service_enabled('hotels')
def property_list_api(request):
    """
    GET /api/v1/properties/

    Supported query parameters:
      location, city, min_price, max_price, free_cancellation,
      amenity (repeatable), property_type (repeatable),
      checkin (YYYY-MM-DD), checkout (YYYY-MM-DD),
      sort (popular|price_asc|price_desc|rating|newest),
      page, page_size
    """
    start = timezone.now()

    qs = _base_queryset()
    qs = apply_search_filters(qs, request.GET)
    qs = apply_date_inventory_filter(qs, request.GET)
    qs = apply_sorting(qs, request.GET.get('sort', 'popular'))

    paginator = HotelPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = PropertyCardSerializer(page, many=True, context={'request': request})

    query_ms = round((timezone.now() - start).total_seconds() * 1000, 2)
    logger.debug("property_list_api: %d results in %sms", len(page), query_ms)

    # Compute filter counts from the FILTERED queryset (not paginated page)
    filter_counts = get_filter_counts(qs)

    response = paginator.get_paginated_response(serializer.data)
    response.data['meta'] = {
        'query_time_ms': query_ms,
        'filters_applied': {
            'location': request.GET.get('location', ''),
            'sort': request.GET.get('sort', 'popular'),
        },
    }
    response.data['filter_counts'] = filter_counts
    # Popular area chips for "Popular Locations in X" section (Goibibo-parity)
    response.data['popular_areas'] = get_popular_areas(qs, request.GET.get('location', ''))
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([SearchThrottle])
@require_service_enabled('hotels')
def property_search_api(request):
    """
    GET /api/v1/search/

    Text search with OTA-grade multi-field scoring.

    Additional params (same as list) plus:
      q  - free-text search query (name, city, area, landmark)
    """
    start = timezone.now()

    query = (request.GET.get('q') or request.GET.get('location') or '').strip()
    params = request.GET.copy()
    if query and 'location' not in params:
        params['location'] = query

    qs = _base_queryset()
    qs = apply_search_filters(qs, params)
    qs = apply_date_inventory_filter(qs, params)
    qs = apply_sorting(qs, params.get('sort', 'popular'))

    paginator = HotelPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = PropertyCardSerializer(page, many=True, context={'request': request})

    query_ms = round((timezone.now() - start).total_seconds() * 1000, 2)
    logger.debug("property_search_api: q=%s %d results in %sms", query, len(page), query_ms)

    filter_counts = get_filter_counts(qs)
    response = paginator.get_paginated_response(serializer.data)
    response.data['meta'] = {'query': query, 'query_time_ms': query_ms}
    response.data['filter_counts'] = filter_counts
    response.data['popular_areas'] = get_popular_areas(qs, query or request.GET.get('location', ''))
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('hotels')
def property_detail_api(request, property_id):
    """
    GET /api/v1/properties/<id>/

    <id> can be either a numeric pk or a slug string.
    Cached for 5 minutes per property.
    Never returns 500 — handles missing intelligence records safely.
    """
    from django.core.cache import cache as _cache
    cache_key = f'property_detail:{property_id}'
    cached = _safe_cache_get(cache_key)
    if cached:
        return Response({'success': True, 'data': cached})

    property_obj = get_property_detail(property_id)
    if not property_obj:
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'not_found',
                    'message': 'Property not found or not available.',
                    'detail': None,
                }
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        serializer = PropertyDetailSerializer(property_obj, context={'request': request})
        data = serializer.data
    except Exception as exc:
        logger.exception("property_detail_api: serialization error for %s: %s", property_id, exc)
        return Response(
            {
                'success': False,
                'error': {
                    'code': 'server_error',
                    'message': 'Unable to load property details. Please try again.',
                    'detail': None,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    _safe_cache_set(cache_key, data, 300)  # 5-minute TTL
    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([AllowAny])
@require_service_enabled('hotels')
def property_availability_api(request, property_id):
    """
    GET /api/v1/properties/<id>/availability/

    Returns available room types with per-night prices for a date range.

    Query params:
      checkin   (required) YYYY-MM-DD
      checkout  (required) YYYY-MM-DD
      rooms     (optional, default=1) number of rooms needed

    Response:
      {
        "success": true,
        "data": {
          "property_id": 1,
          "checkin": "...",
          "checkout": "...",
          "nights": 3,
          "rooms": [
            {
              "room_type_id": 1,
              "name": "Deluxe Double",
              "base_price": 2500,
              "available_count": 4,
              "meal_plan": "breakfast",
              "capacity": 2,
              "bed_type": "King",
              "pricing": { "final_price": 2960, ... }
            }
          ]
        }
      }
    """
    from datetime import datetime
    from apps.rooms.models import RoomType, RoomInventory
    from apps.pricing.price_engine import PriceEngine

    # Validate property
    property_obj = get_property_detail(property_id)
    if not property_obj:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Property not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Parse and validate dates
    checkin_str = request.GET.get('checkin')
    checkout_str = request.GET.get('checkout')
    try:
        rooms_needed = max(1, min(10, int(request.GET.get('rooms', 1))))
    except (ValueError, TypeError):
        rooms_needed = 1

    if not checkin_str or not checkout_str:
        return Response(
            {'success': False, 'error': {'code': 'missing_dates', 'message': 'checkin and checkout are required.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        checkin = datetime.strptime(checkin_str, '%Y-%m-%d').date()
        checkout = datetime.strptime(checkout_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'success': False, 'error': {'code': 'invalid_date', 'message': 'Dates must be in YYYY-MM-DD format.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if checkin >= checkout:
        return Response(
            {'success': False, 'error': {'code': 'invalid_dates', 'message': 'Checkout must be after check-in.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.utils import timezone as tz
    today = tz.now().date()
    if checkin < today:
        return Response(
            {'success': False, 'error': {'code': 'past_date', 'message': 'Check-in date cannot be in the past.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    nights = (checkout - checkin).days

    # Get room types for this property
    room_types = list(RoomType.objects.filter(
        property=property_obj
    ).prefetch_related('amenities', 'images', 'meal_plans'))

    # PERF: Batch-fetch ALL inventory for ALL room types in ONE query (fixes N+1)
    from datetime import timedelta
    date_range = [checkin + timedelta(days=i) for i in range(nights)]
    all_room_type_ids = [rt.id for rt in room_types]
    all_inventories = RoomInventory.objects.filter(
        room_type_id__in=all_room_type_ids,
        date__in=date_range,
        is_closed=False,
    ).values_list('room_type_id', 'date', 'available_rooms')

    # Build nested map: room_type_id → date → available_rooms
    inv_map = {}
    for rt_id, inv_date, avail in all_inventories:
        inv_map.setdefault(rt_id, {})[inv_date] = avail

    available_rooms = []

    for room_type in room_types:
        # Use batched inventory map instead of per-room query
        rt_inventory = inv_map.get(room_type.id, {})
        min_availability = room_type.available_count  # fallback if no RoomInventory exists
        if rt_inventory:
            min_availability = min(rt_inventory.get(d, 0) for d in date_range)

        if min_availability < rooms_needed:
            continue  # Skip fully unavailable rooms

        # Calculate pricing
        pricing = PriceEngine.calculate(
            room_type=room_type,
            nights=nights,
            rooms=rooms_needed,
        )

        # Meal plans from RoomMealPlan table; use prefetched data (avoid N+1)
        meal_plans_qs = sorted(
            [mp for mp in room_type.meal_plans.all() if mp.is_available],
            key=lambda mp: getattr(mp, 'display_order', 0),
        )
        if meal_plans_qs:
            meal_plans_data = [
                {
                    'code': mp.code,
                    'name': mp.name,
                    'price_modifier': str(mp.price_modifier),
                    'description': mp.description,
                    'is_available': True,   # already filtered to is_available=True above
                    'display_order': mp.display_order,
                }
                for mp in meal_plans_qs
            ]
        else:
            # Legacy single meal_plan field — expose as single-item list
            meal_plans_data = [{
                'code': room_type.meal_plan,
                'name': dict(room_type._meta.get_field('meal_plan').choices).get(room_type.meal_plan, room_type.meal_plan),
                'price_modifier': '0',
                'description': '',
                'is_available': True,
                'display_order': 0,
            }]

        room_data = {
            'room_type_id': room_type.id,
            'uuid': str(room_type.uuid),
            'name': room_type.name,
            'description': room_type.description or '',
            'capacity': room_type.capacity,
            'max_occupancy': room_type.max_occupancy,
            'max_guests': room_type.max_guests,
            'bed_type': room_type.bed_type or '',
            'meal_plan': room_type.meal_plan,  # legacy field (kept for compat)
            'meal_plans': meal_plans_data,
            'base_price': str(room_type.base_price),
            'available_count': min_availability,
            'amenities': [{'name': a.name, 'icon': a.icon} for a in room_type.amenities.all()],
            'images': [
                {'url': img.image_url or '', 'alt_text': img.alt_text or room_type.name, 'is_primary': img.is_primary}
                for img in sorted(room_type.images.all(), key=lambda x: (not x.is_primary, x.display_order))
            ],
            'pricing': {
                'base_price': str(pricing['base_price']),
                'property_discount': str(pricing['property_discount']),
                'platform_discount': str(pricing['platform_discount']),
                'service_fee': str(pricing['service_fee']),
                'gst': str(pricing['gst']),
                'gst_percent': pricing['breakdown']['gst_percent'],
                'final_price': str(pricing['final_price']),
            },
        }
        available_rooms.append(room_data)

    # Sort by price ascending
    available_rooms.sort(key=lambda r: float(r['pricing']['final_price']))

    return Response({
        'success': True,
        'data': {
            'property_id': property_obj.id,
            'property_name': property_obj.name,
            'checkin': checkin_str,
            'checkout': checkout_str,
            'nights': nights,
            'rooms_requested': rooms_needed,
            'available_room_types': available_rooms,
            'total_types_available': len(available_rooms),
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@require_service_enabled('hotels')
def pricing_quote_api(request):
    """
    POST /api/v1/pricing/quote/

    Returns a full itemised pricing breakdown for given booking parameters.

    Body:
      {
        "room_type_id": 1,
        "nights": 3,
        "rooms": 1,
        "promo_code": "SAVE10"   (optional)
      }

    Response:
      {
        "success": true,
        "data": {
          "base_price": "7500.00",
          "property_discount": "0.00",
          "platform_discount": "0.00",
          "coupon_discount": "750.00",
          "service_fee": "338.00",
          "gst": "404.86",
          "final_price": "7493.86",
          "breakdown": { ... }
        }
      }
    """
    from apps.rooms.models import RoomType

    room_type_id = request.data.get('room_type_id')
    nights = int(request.data.get('nights', 1))
    rooms = int(request.data.get('rooms', 1))
    promo_code = request.data.get('promo_code', '').strip()

    if not room_type_id:
        return Response(
            {'success': False, 'error': {'code': 'missing_param', 'message': 'room_type_id is required.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if nights < 1 or rooms < 1:
        return Response(
            {'success': False, 'error': {'code': 'invalid_param', 'message': 'nights and rooms must be >= 1.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        room_type = RoomType.objects.select_related('property').get(
            id=room_type_id,
            property__status='approved',
            property__agreement_signed=True,
        )
    except RoomType.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Room type not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Apply promo discount if code provided
    coupon_discount_pct = 0
    if promo_code:
        try:
            from apps.promos.models import Promo
            promo = Promo.objects.get(code__iexact=promo_code, is_active=True)
            if promo.is_valid():
                if promo.discount_type == 'percent':
                    coupon_discount_pct = float(promo.value)
                else:
                    # flat amount — convert to percent of base price for PriceEngine compat
                    base = float(room_type.base_price) * nights * rooms
                    coupon_discount_pct = (float(promo.value) / base * 100) if base > 0 else 0
        except Exception:
            pass  # Invalid promo — ignore silently (price quote still valid)

    from apps.pricing.price_engine import PriceEngine
    pricing = PriceEngine.calculate(
        room_type=room_type,
        nights=nights,
        rooms=rooms,
        coupon_discount_percent=coupon_discount_pct,
    )

    return Response({
        'success': True,
        'data': {
            'room_type_id': room_type.id,
            'room_type_name': room_type.name,
            'property_id': room_type.property.id,
            'property_name': room_type.property.name,
            'nights': nights,
            'rooms': rooms,
            'base_price': str(pricing['base_price']),
            'property_discount': str(pricing['property_discount']),
            'platform_discount': str(pricing['platform_discount']),
            'coupon_discount': str(pricing['coupon_discount']),
            'service_fee': str(pricing['service_fee']),
            'gst': str(pricing['gst']),
            'final_price': str(pricing['final_price']),
            'gst_percent': pricing['breakdown'].get('gst_percent', '18'),
            'promo_code_applied': promo_code if coupon_discount_pct > 0 else '',
            'breakdown': pricing['breakdown'],
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def autosuggest_api(request):
    """
    GET /api/v1/hotels/autosuggest/?q=coorg&limit=8

    Returns flat list of suggestion items in SuggestionItem format:
    {
      "success": true,
      "results": [
        { "type": "city",     "label": "Coorg", "sublabel": "Karnataka · 5 properties", "count": 5 },
        { "type": "area",     "label": "Madikeri", "sublabel": "Coorg, Karnataka · 3 properties", "count": 3 },
        { "type": "property", "label": "Evolve Back Coorg", "sublabel": "Coorg, Karnataka", "slug": "evolve-back-coorg", "id": 1 }
      ]
    }
    """
    from apps.hotels.autosuggest_service import AutosuggestService

    query = (request.GET.get('q') or '').strip()
    limit = min(int(request.GET.get('limit', 8)), 20)

    if not query or len(query) < 2:
        return Response({'success': True, 'results': [], 'query': query})

    raw = AutosuggestService.get_suggestions(query, limit)

    # Build separate arrays per type, then interleave for balanced results
    city_items = []
    bus_items = []
    cab_items = []
    area_items = []
    prop_items = []
    landmark_items = []

    # Cities
    for city in raw.get('cities', []):
        count = city.get('count', 0)
        state = city.get('state', '')
        district = city.get('district', '')
        # Build sublabel like Goibibo: "Anantapur District, Andhra Pradesh · 2 properties"
        parts = []
        if district and district.lower() != city['name'].lower():
            parts.append(f"{district} District")
        if state:
            parts.append(state)
        location_text = ', '.join(parts)
        if count > 0:
            sublabel = f"{location_text} · {count} {'property' if count == 1 else 'properties'}" if location_text else f"{count} properties"
        else:
            sublabel = location_text or ''
        city_items.append({
            'type': 'city',
            'label': city['name'],
            'sublabel': sublabel,
            'count': count,
            'slug': None,
            'id': None,
        })

    # Bus route cities
    for bc in raw.get('bus_cities', []):
        bus_items.append({
            'type': 'bus_city',
            'label': bc['name'],
            'sublabel': f"{bc.get('route_count', 0)} bus routes available",
            'count': bc.get('route_count', 0),
            'slug': None,
            'id': None,
        })

    # Cab cities
    for cc in raw.get('cab_cities', []):
        cab_items.append({
            'type': 'cab_city',
            'label': cc['name'],
            'sublabel': f"{cc.get('cab_count', 0)} cabs available",
            'count': cc.get('cab_count', 0),
            'slug': None,
            'id': None,
        })

    # Areas
    for area in raw.get('areas', []):
        count = area.get('count', 0)
        city_name = area.get('city', '')
        state = area.get('state', '')
        sublabel_parts = [p for p in [city_name, state] if p]
        sublabel = (', '.join(sublabel_parts) + f' · {count} properties') if sublabel_parts else f'{count} properties'
        area_items.append({
            'type': 'area',
            'label': area['name'],
            'sublabel': sublabel,
            'count': count,
            'slug': None,
            'id': None,
        })

    # Properties
    for prop in raw.get('properties', []):
        city_name = prop.get('city', '')
        state = prop.get('state', '')
        sublabel_parts = [p for p in [city_name, state] if p]
        sublabel = ', '.join(sublabel_parts)
        prop_items.append({
            'type': 'property',
            'label': prop['name'],
            'sublabel': sublabel,
            'count': None,
            'slug': prop.get('slug'),
            'id': None,
        })

    # Landmarks
    for lm in raw.get('landmarks', []):
        locality = lm.get('locality', '')
        city_name = lm.get('city', '')
        sublabel_parts = [p for p in [locality, city_name] if p]
        sublabel = ', '.join(sublabel_parts)
        landmark_items.append({
            'type': 'landmark',
            'label': lm['name'],
            'sublabel': sublabel,
            'count': None,
            'slug': None,
            'id': None,
        })

    # Interleave: cities first, then bus/cab (transport), then areas, properties, landmarks
    # This ensures bus/cab results are visible even when there are many hotel results
    results = city_items + bus_items + cab_items + area_items + prop_items + landmark_items

    # If local DB returned very few results, supplement with Google Places
    if len(results) < 3:
        try:
            from apps.core.google_places import is_enabled, autocomplete, normalize_to_location_type

            if is_enabled():
                predictions = autocomplete(query=query, types="(cities)", language="en")
                for p in predictions:
                    g_label = p.get("structured_formatting", {}).get("main_text", "")
                    g_sublabel = p.get("structured_formatting", {}).get("secondary_text", "")
                    g_types = p.get("types", [])
                    if g_label:
                        results.append({
                            "type": normalize_to_location_type(g_types),
                            "label": g_label,
                            "sublabel": g_sublabel,
                            "count": None,
                            "slug": None,
                            "id": None,
                            "place_id": p.get("place_id", ""),
                            "source": "google",
                        })
        except Exception as e:
            logger.warning("Google Places autosuggest supplement failed: %s", e)

    # Deduplicate by (type, normalised label) — prevents duplicate cities from multiple DB rows
    seen: set = set()
    deduped = []
    for item in results:
        key = (item['type'], item['label'].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    results = deduped

    # Cap at limit
    if len(results) > limit:
        results = results[:limit]

    logger.debug("autosuggest_api: q=%s → %d results", query, len(results))
    return Response({'success': True, 'results': results, 'query': query})


@api_view(['GET'])
@permission_classes([AllowAny])
def aggregations_api(request):
    """
    GET /api/v1/hotels/aggregations/

    Returns property counts grouped by city and area.
    {
      "success": true,
      "data": {
        "cities": [{ "name": "Coorg", "count": 5, "slug": "coorg" }],
        "areas":  [{ "name": "Madikeri", "city": "Coorg", "count": 3 }],
        "total":  16
      }
    }
    """
    from django.db.models import Count as DBCount
    from django.utils.text import slugify as dj_slugify

    qs = _base_queryset()

    cities = (
        qs.values('city__name')
        .annotate(count=DBCount('id', distinct=True))
        .filter(city__name__isnull=False)
        .order_by('-count')
        .values_list('city__name', 'count')
    )

    areas = (
        qs.values('area', 'city__name')
        .annotate(count=DBCount('id', distinct=True))
        .filter(area__isnull=False)
        .exclude(area='')
        .order_by('-count')
        .values_list('area', 'city__name', 'count')
    )

    city_list = [
        {'name': name, 'count': cnt, 'slug': dj_slugify(name)}
        for name, cnt in cities
    ]
    area_list = [
        {'name': area, 'city': city, 'count': cnt}
        for area, city, cnt in areas
    ]
    total = qs.count()

    return Response({
        'success': True,
        'data': {
            'cities': city_list,
            'areas': area_list,
            'total': total,
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def pricing_intelligence_api(request, property_uuid):
    """
    GET /api/v1/pricing/intelligence/<property_uuid>/

    Returns competitor price benchmarking for a property.
    Open to anonymous users (guest booking flow).
    Protected by global rate limiting + device fingerprint scoring.
    Data is populated by the daily update_competitor_prices management command.

    Response:
      {
        "success": true,
        "data": {
          "property_uuid": "...",
          "property_name": "...",
          "our_min_price": 3500,
          "competitors": [
            {
              "name": "Booking.com",
              "price_per_night": 3800,
              "date": "2026-03-05",
              "is_available": true,
              "fetched_at": "2026-03-03T10:00:00Z",
              "price_delta": 300,
              "price_delta_pct": 8.57
            }
          ],
          "summary": {
            "avg_competitor_price": 3750,
            "min_competitor_price": 3600,
            "max_competitor_price": 4200,
            "our_advantage_pct": 6.25
          }
        }
      }
    """
    from decimal import Decimal
    from django.db.models import Avg, Min, Max
    from apps.hotels.models import Property
    from apps.pricing.models import CompetitorPrice

    # Lookup property by uuid
    try:
        property_obj = Property.objects.prefetch_related('room_types').get(
            uuid=property_uuid,
            status='approved',
            agreement_signed=True,
        )
    except Property.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Property not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Our minimum room price
    from django.db.models import Min as DBMin
    our_min_price = property_obj.room_types.aggregate(min_p=DBMin('base_price'))['min_p'] or 0

    # Fetch competitor prices (latest record per competitor)
    competitors_qs = (
        CompetitorPrice.objects
        .filter(property=property_obj)
        .order_by('competitor_name', '-date')
        .distinct('competitor_name')
        if hasattr(CompetitorPrice.objects, 'distinct') else
        CompetitorPrice.objects.filter(property=property_obj).order_by('-fetched_at')
    )

    # Fallback: get latest per competitor via Python
    from django.db.models import Prefetch
    all_comp = list(
        CompetitorPrice.objects
        .filter(property=property_obj)
        .order_by('competitor_name', '-date')
    )
    seen_names = set()
    latest_per_competitor = []
    for cp in all_comp:
        if cp.competitor_name not in seen_names:
            seen_names.add(cp.competitor_name)
            latest_per_competitor.append(cp)

    comp_prices = [cp.price_per_night for cp in latest_per_competitor if cp.is_available]

    # Summary stats
    if comp_prices:
        avg_price = sum(comp_prices) / len(comp_prices)
        min_comp = min(comp_prices)
        max_comp = max(comp_prices)
        our_price = Decimal(str(our_min_price))
        our_advantage = float((avg_price - our_price) / avg_price * 100) if avg_price > 0 else 0
    else:
        avg_price = min_comp = max_comp = 0
        our_advantage = 0

    competitors_data = []
    for cp in latest_per_competitor:
        delta = float(cp.price_per_night) - float(our_min_price)
        delta_pct = (delta / float(cp.price_per_night) * 100) if cp.price_per_night else 0
        competitors_data.append({
            'name': cp.competitor_name,
            'source': cp.source,
            'price_per_night': float(cp.price_per_night),
            'date': str(cp.date),
            'is_available': cp.is_available,
            'fetched_at': cp.fetched_at.isoformat(),
            'price_delta': round(delta, 2),
            'price_delta_pct': round(delta_pct, 2),
            'notes': cp.notes,
        })

    return Response({
        'success': True,
        'data': {
            'property_uuid': str(property_obj.uuid),
            'property_name': property_obj.name,
            'our_min_price': float(our_min_price),
            'competitors': competitors_data,
            'summary': {
                'total_competitors': len(competitors_data),
                'avg_competitor_price': round(float(avg_price), 2),
                'min_competitor_price': float(min_comp),
                'max_competitor_price': float(max_comp),
                'our_advantage_pct': round(our_advantage, 2),
                'is_cheapest': float(our_min_price) <= float(min_comp) if comp_prices else None,
            },
            # Safe intelligence fallbacks (Phase 4 hardening)
            'quality_score': _safe_quality_score(property_obj),
            'demand_forecast': _safe_demand_forecast(property_obj),
        },
    })


# ============================================================================
# Step 5/8/9/10 — Booking.com Style Fast Search + Availability Cache + Geo + Price Calendar
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def booking_search_api(request):
    """
    GET /api/v1/booking-search/

    Booking.com-style fast search on denormalized PropertySearchIndex.
    Target: <150ms.  Supports geo, price range, amenity, star filters.

    Query params:
      city, city_id, q, checkin, checkout, min_price, max_price,
      stars (comma-sep), amenities (comma-sep), property_type (comma-sep),
      free_cancellation (bool), pay_at_hotel (bool),
      lat, lng, radius_km,
      sort (recommended|price_asc|price_desc|rating|popularity|newest),
      page, page_size
    """
    from apps.search.engine.booking_search import booking_search_engine
    from datetime import datetime

    params = request.GET

    # Parse comma-separated filters
    stars = [int(s) for s in params.get('stars', '').split(',') if s.isdigit()] or None
    amenities_list = [a.strip() for a in params.get('amenities', '').split(',') if a.strip()] or None
    ptypes = [t.strip() for t in params.get('property_type', '').split(',') if t.strip()] or None

    # Parse booleans
    def _bool(v):
        if v in ('true', '1', 'yes'):
            return True
        return None

    # Parse geo
    lat = float(params['lat']) if 'lat' in params else None
    lng = float(params['lng']) if 'lng' in params else None
    radius = float(params.get('radius_km', 25))

    result = booking_search_engine.search(
        city=params.get('city'),
        city_id=int(params['city_id']) if params.get('city_id') else None,
        query=params.get('q'),
        min_price=float(params['min_price']) if params.get('min_price') else None,
        max_price=float(params['max_price']) if params.get('max_price') else None,
        star_categories=stars,
        amenities=amenities_list,
        property_types=ptypes,
        free_cancellation=_bool(params.get('free_cancellation')),
        pay_at_hotel=_bool(params.get('pay_at_hotel')),
        latitude=lat,
        longitude=lng,
        radius_km=radius,
        sort=params.get('sort', 'recommended'),
        page=int(params.get('page', 1)),
        page_size=min(int(params.get('page_size', 20)), 100),
    )

    return Response({'success': True, **result})


@api_view(['GET'])
@permission_classes([AllowAny])
def booking_search_facets_api(request):
    """
    GET /api/v1/booking-search/facets/

    Returns filter-chip counts (star categories, price buckets, amenities).
    """
    from apps.search.engine.booking_search import booking_search_engine

    params = request.GET
    facets = booking_search_engine.get_facets(
        city=params.get('city'),
        city_id=int(params['city_id']) if params.get('city_id') else None,
    )
    return Response({'success': True, 'data': facets})


@api_view(['GET'])
@permission_classes([AllowAny])
def price_calendar_api(request, property_id):
    """
    GET /api/v1/properties/<id>/price-calendar/?start=YYYY-MM-DD&days=30

    Returns 30-day nightly price calendar.
    """
    from apps.pricing.calendar_api import get_price_calendar_payload

    payload, status_code = get_price_calendar_payload(property_id, request.GET)
    if status_code != status.HTTP_200_OK:
        message = payload.get('error', 'Price calendar request failed.')
        error_code = 'not_found' if status_code == status.HTTP_404_NOT_FOUND else 'invalid_request'
        return Response(
            {'success': False, 'error': {'code': error_code, 'message': message}},
            status=status_code,
        )

    return Response({
        'success': True,
        'data': {
            'property_id': payload['property_id'],
            'property_name': payload['property_name'],
            'days': payload['days'],
            'start_date': payload['start_date'],
            'end_date': payload['end_date'],
            'cached': payload['cached'],
            'calendar': payload['dates'],
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def conversion_signals_api(request, property_id):
    """
    GET /api/v1/properties/<id>/signals/

    Returns real-time conversion signals: scarcity, social proof,
    price trend, trust badges.
    """
    from apps.core.intelligence import ConversionSignals
    from apps.hotels.selectors import get_property_detail

    property_obj = get_property_detail(property_id)
    if not property_obj:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Property not found.'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    checkin_str = request.GET.get('checkin')
    checkout_str = request.GET.get('checkout')
    check_in = check_out = None
    if checkin_str and checkout_str:
        from datetime import datetime
        try:
            check_in = datetime.strptime(checkin_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(checkout_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    try:
        signals = ConversionSignals.get_signals(property_obj, check_in, check_out)
    except Exception:
        logger.exception("conversion_signals_api error for %s", property_id)
        signals = {}

    return Response({
        'success': True,
        'data': {
            'property_id': property_obj.id,
            'signals': signals,
        },
    })
