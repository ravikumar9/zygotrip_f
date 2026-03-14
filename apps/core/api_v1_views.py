"""
Core API v1 — Places, Currency, Geo Search, Map, Analytics, Route, Email endpoints.

These endpoints power the global OTA frontend:
  - Google Places autocomplete + details (hybrid with local DB)
  - Multi-currency conversion + supported currencies
  - Radius-based geo search for hotels/properties
  - Map-based discovery (bounding box, clustering, zoom-aware)
  - Analytics dashboard (funnel, popular destinations, user behavior)
  - Cab route distance calculation
  - Transactional email triggers (internal use)
"""

import json
import logging
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Sum, F
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

logger = logging.getLogger("zygotrip")


# ═══════════════════════════════════════════════════════════════════════
# PLACES — Google Places API + Local DB hybrid
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def places_autocomplete(request):
    """
    GET /api/v1/places/autocomplete/?q=...&types=geocode&lang=en

    Returns Google Places predictions merged with local DB matches.
    Falls back to local-only when Google API key is not configured.
    """
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse({"results": [], "source": "none"}, status=200)

    types = request.GET.get("types", "")  # e.g. "geocode", "(cities)", "establishment"
    language = request.GET.get("lang", "en")
    components = request.GET.get("components", "")  # e.g. "country:in"
    session_token = request.GET.get("session_token", "")

    results = []
    source = "local"

    # Try Google Places first
    from apps.core.google_places import is_enabled, autocomplete, normalize_to_location_type

    if is_enabled():
        predictions = autocomplete(
            query=query,
            types=types or None,
            language=language,
            components=components or None,
            session_token=session_token or None,
        )
        for p in predictions:
            google_types = p.get("types", [])
            results.append({
                "place_id": p.get("place_id", ""),
                "label": p.get("structured_formatting", {}).get("main_text", p.get("description", "")),
                "sublabel": p.get("structured_formatting", {}).get("secondary_text", ""),
                "description": p.get("description", ""),
                "type": normalize_to_location_type(google_types),
                "source": "google",
            })
        source = "google"

    # Merge local DB results
    try:
        from apps.hotels.autosuggest_service import get_autosuggest_results

        local = get_autosuggest_results(query)
        # Flatten all categories into results list
        for category in ("cities", "areas", "properties", "landmarks", "bus_cities", "cab_cities"):
            for item in local.get(category, []):
                results.append({
                    "place_id": "",
                    "label": item.get("label", item.get("name", "")),
                    "sublabel": item.get("sublabel", ""),
                    "description": item.get("label", ""),
                    "type": item.get("type", category.rstrip("s")),
                    "source": "local",
                    "id": item.get("id"),
                    "slug": item.get("slug", ""),
                })
        if not source == "google":
            source = "local"
        else:
            source = "hybrid"
    except Exception as e:
        logger.warning("Local autosuggest fallback failed: %s", e)

    # Deduplicate by label (case-insensitive)
    seen = set()
    deduped = []
    for r in results:
        key = r["label"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return JsonResponse({"results": deduped[:20], "source": source})


@require_GET
def places_details(request):
    """
    GET /api/v1/places/details/?place_id=ChIJ...&session_token=...

    Returns lat/lng, address components, normalized type for a Google place_id.
    """
    place_id = request.GET.get("place_id", "").strip()
    session_token = request.GET.get("session_token", "")
    if not place_id:
        return JsonResponse({"error": "place_id required"}, status=400)

    from apps.core.google_places import is_enabled, place_details

    if not is_enabled():
        return JsonResponse({"error": "Google Places API not configured"}, status=503)

    details = place_details(place_id, session_token=session_token or None)
    if not details:
        return JsonResponse({"error": "Place not found"}, status=404)

    return JsonResponse({"result": details})


@require_GET
def places_geocode(request):
    """
    GET /api/v1/places/geocode/?address=Eiffel+Tower,+Paris
    GET /api/v1/places/geocode/?lat=48.8584&lng=2.2945  (reverse)

    Returns coordinates and parsed address components.
    """
    address = request.GET.get("address", "").strip()
    lat = request.GET.get("lat", "")
    lng = request.GET.get("lng", "")

    from apps.core.google_places import is_enabled, geocode, reverse_geocode

    if not is_enabled():
        return JsonResponse({"error": "Google Places API not configured"}, status=503)

    if lat and lng:
        try:
            result = reverse_geocode(float(lat), float(lng))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid lat/lng"}, status=400)
    elif address:
        result = geocode(address)
    else:
        return JsonResponse({"error": "Provide address or lat+lng"}, status=400)

    if not result:
        return JsonResponse({"error": "Location not found"}, status=404)

    return JsonResponse({"result": result})


# ═══════════════════════════════════════════════════════════════════════
# CURRENCY — Exchange rates + conversion
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def currency_rates(request):
    """
    GET /api/v1/currency/rates/?base=INR

    Returns exchange rates for all supported currencies.
    """
    base = request.GET.get("base", "INR").upper()

    from apps.core.currency_service import get_exchange_rates, get_supported_currencies

    rates = get_exchange_rates(base)
    supported = get_supported_currencies()

    return JsonResponse({
        "base": base,
        "rates": {k: float(v) for k, v in rates.items()},
        "supported_currencies": supported,
    })


@require_GET
def currency_convert(request):
    """
    GET /api/v1/currency/convert/?amount=1000&from=INR&to=USD

    Returns converted amount with formatted string.
    """
    try:
        amount = Decimal(request.GET.get("amount", "0"))
    except InvalidOperation:
        return JsonResponse({"error": "Invalid amount"}, status=400)

    from_cur = request.GET.get("from", "INR").upper()
    to_cur = request.GET.get("to", "USD").upper()

    from apps.core.currency_service import convert_amount, format_currency

    converted = convert_amount(amount, from_cur, to_cur)
    return JsonResponse({
        "amount": float(amount),
        "from_currency": from_cur,
        "to_currency": to_cur,
        "converted_amount": float(converted),
        "formatted": format_currency(converted, to_cur),
        "original_formatted": format_currency(amount, from_cur),
    })


@require_GET
def currency_supported(request):
    """
    GET /api/v1/currency/supported/

    Returns list of supported currencies for the frontend picker.
    """
    from apps.core.currency_service import get_supported_currencies

    return JsonResponse({"currencies": get_supported_currencies()})


@require_GET
def currency_detect(request):
    """
    GET /api/v1/currency/detect/

    Auto-detect user's preferred currency from IP/locale/preference.
    """
    ip_country = request.GET.get("country", "")
    locale = request.GET.get("locale", "")
    preference = request.GET.get("preference", "")

    from apps.core.currency_service import detect_user_currency

    detected = detect_user_currency(
        ip_country=ip_country or None,
        browser_locale=locale or None,
        user_preference=preference or None,
    )
    return JsonResponse({"currency": detected})


# ═══════════════════════════════════════════════════════════════════════
# GEO SEARCH — Radius-based property search
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def geo_search(request):
    """
    GET /api/v1/geo-search/?q=Eiffel+Tower&radius=5&sort=distance&limit=20

    Resolve a query to coordinates, then search properties within radius.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "q parameter required"}, status=400)

    try:
        radius = float(request.GET.get("radius", 10))
    except ValueError:
        radius = 10.0

    sort_by = request.GET.get("sort", "ranking")
    try:
        limit = int(request.GET.get("limit", 20))
    except ValueError:
        limit = 20

    # Collect filters
    filters = {}
    if request.GET.get("min_price"):
        try:
            filters["min_price"] = float(request.GET["min_price"])
        except ValueError:
            pass
    if request.GET.get("max_price"):
        try:
            filters["max_price"] = float(request.GET["max_price"])
        except ValueError:
            pass
    if request.GET.get("star_rating"):
        try:
            filters["star_rating"] = int(request.GET["star_rating"])
        except ValueError:
            pass
    if request.GET.get("property_type"):
        filters["property_type"] = request.GET["property_type"]

    from apps.core.geo_search import resolve_and_search

    result = resolve_and_search(
        query=query,
        radius_km=radius,
        sort_by=sort_by,
        limit=limit,
        filters=filters,
    )

    return JsonResponse(result)


@require_GET
def geo_search_nearby(request):
    """
    GET /api/v1/geo-search/nearby/?lat=28.6139&lng=77.2090&radius=5&sort=distance

    Search properties near a specific lat/lng (e.g., user's location).
    """
    try:
        lat = float(request.GET.get("lat", 0))
        lng = float(request.GET.get("lng", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Valid lat and lng required"}, status=400)

    if not lat or not lng:
        return JsonResponse({"error": "lat and lng required"}, status=400)

    try:
        radius = float(request.GET.get("radius", 10))
    except ValueError:
        radius = 10.0

    sort_by = request.GET.get("sort", "distance")
    try:
        limit = int(request.GET.get("limit", 20))
    except ValueError:
        limit = 20

    filters = {}
    if request.GET.get("min_price"):
        try:
            filters["min_price"] = float(request.GET["min_price"])
        except ValueError:
            pass
    if request.GET.get("max_price"):
        try:
            filters["max_price"] = float(request.GET["max_price"])
        except ValueError:
            pass

    from apps.core.geo_search import radius_search

    results = radius_search(
        lat=lat,
        lng=lng,
        radius_km=radius,
        sort_by=sort_by,
        limit=limit,
        filters=filters,
    )

    return JsonResponse({
        "lat": lat,
        "lng": lng,
        "radius_km": radius,
        "sort_by": sort_by,
        "results": results,
        "total": len(results),
    })


# ═══════════════════════════════════════════════════════════════════════
# CAB ROUTE — Distance calculation for cab bookings
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def cab_route_calculate(request):
    """
    GET /api/v1/route/calculate/?from=28.6139,77.2090&to=28.5355,77.3910

    Calculate driving distance, duration, toll, and fare estimate.
    Uses OSRM (free) → GraphHopper → Google Maps with caching.
    """
    from_loc = request.GET.get("from", "").strip()
    to_loc = request.GET.get("to", "").strip()
    vehicle_type = request.GET.get("vehicle", "car")

    if not from_loc or not to_loc:
        return JsonResponse({"error": "from and to parameters required"}, status=400)

    from apps.cabs.routing_engine import get_default_distance_engine

    engine = get_default_distance_engine()
    result = engine.calculate_distance(from_loc, to_loc, vehicle_type=vehicle_type)

    return JsonResponse({"route": result})


# ═══════════════════════════════════════════════════════════════════════
# EMAIL — Trigger transactional emails (staff/internal only)
# ═══════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
def send_test_email(request):
    """
    POST /api/v1/email/test/  (staff only)
    Body: {"to": "user@example.com", "type": "welcome", "name": "John"}

    Send a test email. Requires staff auth or a secret header.
    """
    # Simple auth check: staff user or internal header
    if not (request.user.is_authenticated and request.user.is_staff):
        api_key = request.headers.get("X-Internal-Key", "")
        if api_key != getattr(request, "_internal_key", None):
            return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    to_email = body.get("to", "")
    email_type = body.get("type", "welcome")

    if not to_email:
        return JsonResponse({"error": "to email required"}, status=400)

    from apps.core.email_service import send_welcome_email, send_otp_email

    if email_type == "otp":
        success = send_otp_email(to_email, body.get("otp", "123456"))
    else:
        success = send_welcome_email(to_email, body.get("name", "User"))

    return JsonResponse({"sent": success, "type": email_type, "to": to_email})


@require_GET
def gateway_services(request):
    """
    GET /api/v1/gateway/services/

    Returns the public gateway registry, including service boundaries,
    API version, and extraction readiness metadata.
    """
    from apps.core.gateway_registry import build_gateway_registry_payload

    return JsonResponse(build_gateway_registry_payload(request.path))


# ═══════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS — Similar, Popular, Best Value, Trending
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def recommendations_similar(request, hotel_id):
    """
    GET /api/v1/recommendations/similar/<hotel_id>/?limit=8

    Returns hotels similar to the given hotel based on content-based scoring
    (location proximity, star match, price band, amenity overlap).
    """
    limit = min(int(request.GET.get('limit', 8)), 20)
    try:
        from apps.core.recommendation_engine import RecommendationEngine
        results = RecommendationEngine.similar_hotels(hotel_id, limit=limit)
        return JsonResponse({'results': results, 'count': len(results)})
    except Exception as exc:
        logger.error('Recommendations similar failed: %s', exc)
        return JsonResponse({'results': [], 'count': 0})


@require_GET
def recommendations_popular(request):
    """
    GET /api/v1/recommendations/popular/?city=Goa&limit=10

    Returns most popular hotels, optionally filtered by city.
    """
    city = request.GET.get('city', '')
    limit = min(int(request.GET.get('limit', 10)), 30)
    try:
        from apps.core.recommendation_engine import RecommendationEngine
        results = RecommendationEngine.popular_hotels(city=city, limit=limit)
        return JsonResponse({'results': results, 'count': len(results)})
    except Exception as exc:
        logger.error('Recommendations popular failed: %s', exc)
        return JsonResponse({'results': [], 'count': 0})


@require_GET
def recommendations_best_value(request):
    """
    GET /api/v1/recommendations/best-value/?city=Mumbai&limit=10

    Returns best value hotels (Pareto front of price vs. rating).
    """
    city = request.GET.get('city', '')
    limit = min(int(request.GET.get('limit', 10)), 30)
    try:
        from apps.core.recommendation_engine import RecommendationEngine
        results = RecommendationEngine.best_value(city=city, limit=limit)
        return JsonResponse({'results': results, 'count': len(results)})
    except Exception as exc:
        logger.error('Recommendations best_value failed: %s', exc)
        return JsonResponse({'results': [], 'count': 0})


@require_GET
def recommendations_trending(request):
    """
    GET /api/v1/recommendations/trending/?city=Delhi&limit=10

    Returns trending hotels based on recent booking velocity and quality score.
    """
    city = request.GET.get('city', '')
    limit = min(int(request.GET.get('limit', 10)), 20)
    try:
        from apps.core.intelligence import HotelQualityScore
        from apps.hotels.models import Property

        qs = HotelQualityScore.objects.filter(
            is_trending=True,
            property__is_active=True,
        ).select_related('property').order_by('-overall_score')

        if city:
            qs = qs.filter(
                Q(property__city__name__iexact=city) |
                Q(property__city__display_name__iexact=city)
            )

        results = []
        for qs_item in qs[:limit]:
            prop = qs_item.property
            results.append({
                'id': prop.id,
                'name': prop.name,
                'slug': getattr(prop, 'slug', ''),
                'city': getattr(prop, 'city_name', ''),
                'rating': float(getattr(prop, 'rating', 0) or 0),
                'quality_score': qs_item.overall_score,
                'is_top_rated': qs_item.is_top_rated,
                'is_value_pick': qs_item.is_value_pick,
            })
        return JsonResponse({'results': results, 'count': len(results)})
    except Exception as exc:
        logger.error('Recommendations trending failed: %s', exc)
        return JsonResponse({'results': [], 'count': 0})


# ═══════════════════════════════════════════════════════════════════════
# MAP DISCOVERY — Bounding box, clustering, zoom-aware search
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def map_bounding_box(request):
    """
    GET /api/v1/map/bounding-box/?ne_lat=28.7&ne_lng=77.3&sw_lat=28.5&sw_lng=77.0&zoom=12

    Returns hotels inside the visible map viewport.
    Automatically clusters when zoomed out with many results.
    Supports filters: min_price, max_price, star_rating (comma-separated).
    """
    try:
        ne_lat = float(request.GET.get('ne_lat', 0))
        ne_lng = float(request.GET.get('ne_lng', 0))
        sw_lat = float(request.GET.get('sw_lat', 0))
        sw_lng = float(request.GET.get('sw_lng', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Valid bounding box coordinates required'}, status=400)

    if not all([ne_lat, ne_lng, sw_lat, sw_lng]):
        return JsonResponse({'error': 'ne_lat, ne_lng, sw_lat, sw_lng required'}, status=400)

    zoom = int(request.GET.get('zoom', 12))
    limit = min(int(request.GET.get('limit', 200)), 500)

    filters = {}
    if request.GET.get('min_price'):
        try:
            filters['min_price'] = float(request.GET['min_price'])
        except ValueError:
            pass
    if request.GET.get('max_price'):
        try:
            filters['max_price'] = float(request.GET['max_price'])
        except ValueError:
            pass
    if request.GET.get('star_rating'):
        try:
            filters['star_rating'] = [int(s) for s in request.GET['star_rating'].split(',')]
        except ValueError:
            pass

    from apps.core.geo_search import map_search, cluster_for_zoom
    from apps.core.geo_utils import should_cluster

    # Get all hotels in viewport
    hotels = map_search(ne_lat, ne_lng, sw_lat, sw_lng, filters=filters, limit=limit)
    hotel_count = len(hotels)

    # Decide: cluster or individual pins
    use_clusters = should_cluster(zoom, hotel_count)

    if use_clusters:
        clusters = cluster_for_zoom(ne_lat, ne_lng, sw_lat, sw_lng, zoom_level=zoom)
        return JsonResponse({
            'mode': 'clustered',
            'zoom': zoom,
            'total_hotels': hotel_count,
            'clusters': clusters,
        })

    return JsonResponse({
        'mode': 'pins',
        'zoom': zoom,
        'total_hotels': hotel_count,
        'hotels': hotels,
    })


@require_GET
def map_hotel_detail(request, hotel_id):
    """
    GET /api/v1/map/hotel/<hotel_id>/

    Lightweight hotel detail for map popup — includes landmark distances.
    """
    try:
        from apps.hotels.models import Property
        from apps.core.geo_utils import get_nearby_landmarks_for_property

        prop = Property.objects.select_related('city').get(pk=hotel_id, is_active=True)

        landmarks = get_nearby_landmarks_for_property(prop, radius_km=5, limit=3)

        return JsonResponse({
            'id': prop.pk,
            'name': prop.name,
            'slug': getattr(prop, 'slug', ''),
            'star_rating': prop.star_category,
            'rating': float(prop.rating or 0),
            'review_count': prop.review_count or 0,
            'lat': float(prop.latitude),
            'lng': float(prop.longitude),
            'address': prop.address or '',
            'area': prop.area or '',
            'landmark': prop.landmark or '',
            'has_free_cancellation': prop.has_free_cancellation,
            'is_trending': prop.is_trending,
            'landmarks': landmarks,
            'city': prop.city.name if prop.city else '',
        })
    except Exception as exc:
        logger.error('Map hotel detail failed for %s: %s', hotel_id, exc)
        return JsonResponse({'error': 'Hotel not found'}, status=404)


# ═══════════════════════════════════════════════════════════════════════
# TRUST SIGNALS — Real-time conversion signals for a property
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def trust_signals(request, hotel_id):
    """
    GET /api/v1/trust-signals/<hotel_id>/?check_in=2026-04-01&check_out=2026-04-03

    Returns urgency/social-proof/scarcity signals for a property.
    Includes: rooms left, bookings today, last booked, price trend, trust badges.
    """
    from datetime import datetime

    check_in = request.GET.get('check_in', '')
    check_out = request.GET.get('check_out', '')

    check_in_date = None
    check_out_date = None
    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        except ValueError:
            pass

    try:
        from apps.hotels.models import Property
        from apps.core.intelligence import ConversionSignals

        prop = Property.objects.get(pk=hotel_id)
        signals = ConversionSignals.get_signals(prop, check_in_date, check_out_date)
        return JsonResponse({'hotel_id': hotel_id, 'signals': signals})
    except Exception as exc:
        logger.error('Trust signals failed for %s: %s', hotel_id, exc)
        return JsonResponse({'hotel_id': hotel_id, 'signals': {}})


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS — Funnel, Popular Destinations, User Behavior
# ═══════════════════════════════════════════════════════════════════════

FUNNEL_STAGE_EVENT_MAP = {
    'search_results_shown': 'search',
    'hotel_page_viewed': 'property_view',
    'room_selected': 'room_select',
    'booking_started': 'booking_context_created',
    'payment_initiated': 'payment_initiated',
    'booking_completed': 'booking_confirmed',
}


@csrf_exempt
@require_POST
def analytics_funnel_track(request):
    """
    POST /api/v1/analytics/funnel/track/

    Accepts anonymous frontend funnel progression events for aggregation.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

    stage = payload.get('stage', '')
    session_id = payload.get('session_id', '')
    event_type = FUNNEL_STAGE_EVENT_MAP.get(stage)

    if not event_type:
        return JsonResponse({'error': 'Unsupported funnel stage'}, status=400)
    if not session_id:
        return JsonResponse({'error': 'session_id is required'}, status=400)

    properties = payload.get('properties')
    if not isinstance(properties, dict):
        properties = {}

    from apps.core.analytics import AnalyticsEvent

    city = properties.get('city') or properties.get('destination', '')
    property_id = properties.get('property_id') or properties.get('propertyId') or properties.get('hotelId')

    AnalyticsEvent.objects.create(
        event_type=event_type,
        user=request.user if request.user.is_authenticated else None,
        session_id=session_id,
        ip_address=request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referrer=request.META.get('HTTP_REFERER', '')[:200],
        properties={
            **properties,
            'funnel_stage': stage,
            'funnel_stage_index': payload.get('stage_index'),
            'funnel_time_since_last_stage': payload.get('time_since_last'),
        },
        city=city,
        property_id=property_id,
    )

    return JsonResponse({'status': 'accepted'}, status=202)

@require_GET
def analytics_funnel(request):
    """
    GET /api/v1/analytics/funnel/?days=30

    Returns booking funnel conversion rates (search → view → select → book).
    Staff-only endpoint.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Staff access required'}, status=403)

    days = min(int(request.GET.get('days', 30)), 365)
    start_date = (timezone.now() - timezone.timedelta(days=days)).date()
    end_date = timezone.now().date()

    from apps.core.analytics import get_funnel_metrics
    metrics = get_funnel_metrics(start_date, end_date)

    return JsonResponse({
        'period_days': days,
        'start_date': str(start_date),
        'end_date': str(end_date),
        **metrics,
    })


@require_GET
def analytics_popular_destinations(request):
    """
    GET /api/v1/analytics/popular-destinations/?limit=20

    Returns most searched/booked destinations with conversion rates.
    """
    limit = min(int(request.GET.get('limit', 20)), 50)

    from apps.core.analytics import AnalyticsEvent

    # Top destinations by search volume + booking conversion
    thirty_days = timezone.now() - timezone.timedelta(days=30)

    search_cities = (
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_SEARCH,
            created_at__gte=thirty_days,
        )
        .exclude(city='')
        .values('city')
        .annotate(
            searches=Count('id'),
        )
        .order_by('-searches')[:limit * 2]
    )

    results = []
    for sc in search_cities[:limit]:
        city = sc['city']
        bookings = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
            city=city,
            created_at__gte=thirty_days,
        ).count()
        conversion = round(bookings / max(sc['searches'], 1) * 100, 1)
        results.append({
            'city': city,
            'searches': sc['searches'],
            'bookings': bookings,
            'conversion_rate': conversion,
        })

    results.sort(key=lambda r: r['searches'], reverse=True)
    return JsonResponse({'destinations': results[:limit]})


@require_GET
def analytics_pricing_competitiveness(request):
    """
    GET /api/v1/analytics/pricing/?city=Goa

    Returns pricing competitiveness analysis: our prices vs competitor averages.
    Staff-only endpoint.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Staff access required'}, status=403)

    city = request.GET.get('city', '')

    from apps.pricing.models import CompetitorPrice
    from apps.hotels.models import Property
    from apps.rooms.models import RoomType

    today = timezone.now().date()
    qs = CompetitorPrice.objects.filter(
        date__gte=today,
        is_available=True,
    )
    if city:
        qs = qs.filter(
            Q(property__city__name__iexact=city) |
            Q(property__city__display_name__iexact=city)
        )

    comp_avg = qs.aggregate(avg_price=Avg('price_per_night'))['avg_price'] or 0

    # Our average price
    room_qs = RoomType.objects.filter(property__is_active=True)
    if city:
        room_qs = room_qs.filter(
            Q(property__city__name__iexact=city) |
            Q(property__city__display_name__iexact=city)
        )
    our_avg = room_qs.aggregate(avg_price=Avg('base_price'))['avg_price'] or 0

    ratio = float(our_avg) / float(comp_avg) if comp_avg else 1.0

    return JsonResponse({
        'city': city or 'all',
        'our_avg_price': round(float(our_avg), 2),
        'competitor_avg_price': round(float(comp_avg), 2),
        'price_ratio': round(ratio, 3),
        'assessment': (
            'competitive' if ratio <= 1.05 else
            'slightly_expensive' if ratio <= 1.15 else
            'expensive'
        ),
    })


@require_GET
def analytics_user_behavior(request):
    """
    GET /api/v1/analytics/user-behavior/?days=7

    Returns user behavior segmentation: device mix, time patterns, bounce rates.
    Staff-only endpoint.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Staff access required'}, status=403)

    days = min(int(request.GET.get('days', 7)), 90)
    cutoff = timezone.now() - timezone.timedelta(days=days)

    from apps.core.analytics import AnalyticsEvent

    events = AnalyticsEvent.objects.filter(created_at__gte=cutoff)

    total_sessions = events.values('session_id').distinct().count()
    searching_sessions = events.filter(
        event_type=AnalyticsEvent.EVENT_SEARCH,
    ).values('session_id').distinct().count()
    booking_sessions = events.filter(
        event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
    ).values('session_id').distinct().count()

    # Device segmentation (from user_agent)
    mobile_count = events.filter(
        user_agent__icontains='mobile',
    ).values('session_id').distinct().count()
    desktop_count = total_sessions - mobile_count

    # Hourly distribution
    hour_dist = (
        events.filter(event_type=AnalyticsEvent.EVENT_SEARCH)
        .extra(select={'hour': "EXTRACT(HOUR FROM created_at)"})
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )

    return JsonResponse({
        'period_days': days,
        'total_sessions': total_sessions,
        'searching_sessions': searching_sessions,
        'booking_sessions': booking_sessions,
        'overall_conversion': round(
            booking_sessions / max(total_sessions, 1) * 100, 2
        ),
        'device_split': {
            'mobile': mobile_count,
            'desktop': desktop_count,
            'mobile_pct': round(mobile_count / max(total_sessions, 1) * 100, 1),
        },
        'hourly_search_distribution': list(hour_dist),
    })


# ═══════════════════════════════════════════════════════════════════════
# A/B TESTING — Experiment assignment + reporting
# ═══════════════════════════════════════════════════════════════════════

@require_GET
def ab_test_assign(request):
    """
    GET /api/v1/ab-test/assign/?experiment=ranking_v2&variants=control,treatment

    Assigns a user/session to an A/B test variant (sticky assignment).
    Returns the assigned variant for the frontend to use.
    """
    experiment = request.GET.get('experiment', '').strip()
    variants_str = request.GET.get('variants', 'control,treatment')
    if not experiment:
        return JsonResponse({'error': 'experiment parameter required'}, status=400)

    variants = [v.strip() for v in variants_str.split(',') if v.strip()]
    if len(variants) < 2:
        variants = ['control', 'treatment']

    from apps.core.analytics import ABTestVariant, _get_session_id
    import hashlib

    session_id = _get_session_id(request) if request else ''
    user = request.user if request.user.is_authenticated else None

    # Check for existing assignment
    existing = ABTestVariant.objects.filter(
        experiment_name=experiment,
        session_id=session_id,
    ).first()

    if existing:
        return JsonResponse({
            'experiment': experiment,
            'variant': existing.variant,
            'is_new': False,
        })

    # Deterministic assignment based on session hash
    hash_input = f'{experiment}:{session_id}'
    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    variant = variants[hash_val % len(variants)]

    ABTestVariant.objects.create(
        experiment_name=experiment,
        variant=variant,
        user=user,
        session_id=session_id,
    )

    return JsonResponse({
        'experiment': experiment,
        'variant': variant,
        'is_new': True,
    })


@require_GET
def ab_test_results(request):
    """
    GET /api/v1/ab-test/results/?experiment=ranking_v2

    Returns A/B test results with conversion rates per variant.
    Staff-only endpoint.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Staff access required'}, status=403)

    experiment = request.GET.get('experiment', '').strip()
    if not experiment:
        return JsonResponse({'error': 'experiment parameter required'}, status=400)

    from apps.core.analytics import ABTestVariant

    variants = (
        ABTestVariant.objects.filter(experiment_name=experiment)
        .values('variant')
        .annotate(
            total=Count('id'),
            conversions=Count('id', filter=Q(converted=True)),
            revenue=Sum('conversion_value', filter=Q(converted=True)),
        )
        .order_by('variant')
    )

    results = []
    for v in variants:
        results.append({
            'variant': v['variant'],
            'total_users': v['total'],
            'conversions': v['conversions'],
            'conversion_rate': round(v['conversions'] / max(v['total'], 1) * 100, 2),
            'total_revenue': float(v['revenue'] or 0),
            'avg_revenue_per_user': round(
                float(v['revenue'] or 0) / max(v['conversions'], 1), 2
            ),
        })

    return JsonResponse({
        'experiment': experiment,
        'variants': results,
    })
