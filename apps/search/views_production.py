"""Production search view using ViewModel architecture.

This view demonstrates:
- Service layer usage (never pass ORM to templates)
- ViewModel builders (transform data)
- Advanced search with scoring
- API response pattern
- Fragment caching
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, F, Count
import json
import logging

from apps.hotels.models import Property
from .models import SearchIndex
from apps.core.models import City, Locality
from apps.hotels.viewmodels import HotelCardVM
from apps.hotels.services import _build_detail_url, _build_stay_params
from .engine import search_engine

logger = logging.getLogger('zygotrip.search')


def _extract_user_context(request) -> dict:
    """Extract user context from request for personalized ranking.

    Pulls user profile data, device info, geolocation, and past search
    history to feed into SearchRankingV2's personalization scorer (20% weight).
    """
    ctx = {}

    # 1. Authenticated user ID
    if request.user.is_authenticated:
        ctx['user_id'] = request.user.id

    # 2. Device type from User-Agent
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    if any(k in ua for k in ('mobile', 'android', 'iphone', 'ipad')):
        ctx['device'] = 'mobile'
    else:
        ctx['device'] = 'desktop'

    # 3. Geolocation (from header set by Cloudflare / nginx / frontend)
    try:
        lat = request.GET.get('lat') or request.META.get('HTTP_X_USER_LAT')
        lng = request.GET.get('lng') or request.META.get('HTTP_X_USER_LNG')
        if lat and lng:
            ctx['user_lat'] = float(lat)
            ctx['user_lng'] = float(lng)
    except (TypeError, ValueError):
        pass

    # 4. Past search cities (from RecentSearch model)
    try:
        from apps.hotels.models import RecentSearch
        from apps.core.models import City as CityModel

        if request.user.is_authenticated:
            recent = RecentSearch.objects.filter(
                user=request.user,
            ).values_list('search_text', flat=True).distinct()[:10]
        else:
            session_key = request.session.session_key
            if session_key:
                recent = RecentSearch.objects.filter(
                    session_key=session_key,
                ).values_list('search_text', flat=True).distinct()[:10]
            else:
                recent = []

        if recent:
            city_ids = list(
                CityModel.objects.filter(
                    name__in=list(recent),
                    is_active=True,
                ).values_list('id', flat=True)
            )
            if city_ids:
                ctx['past_cities'] = city_ids
    except Exception:
        pass

    # 5. Time of day (for business vs leisure heuristic)
    from django.utils import timezone as tz
    hour = tz.localtime().hour
    if 6 <= hour < 12:
        ctx['time_of_day'] = 'morning'
    elif 12 <= hour < 17:
        ctx['time_of_day'] = 'afternoon'
    elif 17 <= hour < 22:
        ctx['time_of_day'] = 'evening'
    else:
        ctx['time_of_day'] = 'night'

    return ctx


def build_hotel_card_vm(property_obj, stay_params) -> HotelCardVM:
    """Convert Property ORM object to HotelCardVM.

    PERFORMANCE RULES (N+1 prevention):
    - Use annotated `min_room_price` instead of calling property.base_price (N+1)
    - Use prefetched images list instead of .filter() on images (N+1)
    - Use prefetched amenities list instead of .all() in a loop (already fine)
    """
    from decimal import Decimal

    # FIX N+1: Use annotated field from ota_visible_properties() queryset.
    # property_obj.base_price fires one SQL query per hotel — never call it in a loop.
    # ota_visible_properties() annotates `min_room_price` for exactly this purpose.
    try:
        raw_price = (
            getattr(property_obj, 'min_room_price', None)
            or getattr(property_obj, 'min_price', None)
        )
        base_price = int(raw_price) if raw_price else 0
    except (TypeError, ValueError):
        base_price = 0

    # Get amenities — already prefetched, safe to iterate
    amenities_qs = property_obj.amenities.all() if hasattr(property_obj, 'amenities') else []
    amenities_list = [a.name for a in amenities_qs]

    # FIX N+1: Use prefetched images cache instead of .filter(is_featured=True).
    # .filter() bypasses the prefetch cache and fires a new query per hotel.
    try:
        prefetched_images = list(property_obj.images.all())  # uses prefetch cache
        primary_image = next((img for img in prefetched_images if img.is_featured), None)
        if not primary_image and prefetched_images:
            primary_image = prefetched_images[0]
        image_url = primary_image.resolved_url if primary_image else ''
    except Exception:
        image_url = ''

    rating = property_obj.rating
    if rating and float(rating) >= 4.5:
        rating_tier = 'excellent'
    elif rating and float(rating) >= 3.5:
        rating_tier = 'good'
    else:
        rating_tier = 'average'

    return HotelCardVM(
        id=property_obj.id,
        name=property_obj.name,
        slug=property_obj.slug,
        city=property_obj.city.name if property_obj.city else '',
        area=property_obj.area or '',
        landmark=property_obj.landmark or '',
        latitude=float(property_obj.latitude) if property_obj.latitude else 0,
        longitude=float(property_obj.longitude) if property_obj.longitude else 0,
        image_url=image_url,
        image_alt=f"{property_obj.name} - {property_obj.area}",
        price_current=Decimal(str(base_price)),
        price_original=None,
        discount_percent=0,
        savings_amount=Decimal('0'),
        rating_value=float(rating) if rating else None,
        rating_count=property_obj.review_count or 0,
        rating_tier=rating_tier,
        rooms_left=getattr(property_obj, 'available_rooms', 5),
        booked_today=property_obj.bookings_today or 0,
        viewers_now=0,
        is_verified=True,
        is_best_rating=False,
        is_lowest_price=False,
        is_best_deal=False,
        is_best_value=False,
        amenities=amenities_list,
        free_cancellation=getattr(property_obj, 'has_free_cancellation', False),
        pay_at_hotel=getattr(property_obj, 'pay_at_hotel', False),
        property_type=property_obj.property_type or 'hotel',
        cta_url=_build_detail_url(property_obj, stay_params),
        relevance_score=float(getattr(property_obj, 'relevance_score', 0) or 0),
    )


@require_http_methods(['GET', 'POST'])
def search_list(request):
    """Production search endpoint with unified engine + personalized ranking.
    
    Supports:
    - Text search with multi-field scoring
    - Personalized ranking via user_context (CTR, past searches, geo)
    - Impression tracking for CTR pipeline
    - Pagination  
    - JSON API response
    """
    try:
        # Extract search parameters
        query = (request.GET.get('q') or request.GET.get('location') or '').strip()
        page = request.GET.get('page', 1)
        format_type = request.GET.get('format', 'html')
        
        # Build user context for personalized ranking
        user_context = _extract_user_context(request)
        
        # Use unified search engine
        search_results = search_engine.search_hotels(query=query, limit=50)
        results_qs = search_results.results
        total_count = search_results.count
        stay_params = _build_stay_params(request.GET)
        
        # Apply personalized ranking via ranking_v2 if user_context present
        if results_qs and user_context:
            try:
                from .engine.ranking_v2 import SearchRankingV2
                ranker = SearchRankingV2()
                results_qs = ranker.rank(list(results_qs), query, user_context)
            except Exception as e:
                logger.warning('Personalized ranking failed, using default: %s', e)
        
        # Convert to ViewModels
        hotel_cards = [build_hotel_card_vm(prop, stay_params) for prop in results_qs]
        
        # Track impressions for CTR pipeline (async, non-blocking)
        _track_search_impressions(results_qs)
        
        # Pagination
        paginator = Paginator(hotel_cards, 20)
        page_obj = paginator.get_page(page)
        
        # Return format
        if format_type == 'json':
            return JsonResponse({
                'status': 'success',
                'total_count': total_count,
                'page': page,
                'results': [
                    {
                        'id': card.id,
                        'name': card.name,
                        'city': card.city,
                        'image': card.image_url,
                        'price': str(card.price_current),
                        'rating': card.rating_value,
                        'url': card.cta_url,
                    }
                    for card in page_obj.object_list
                ],
            }, safe=False)
        
        # HTML response
        context = {
            'query': query,
            'results': page_obj.object_list,
            'page_obj': page_obj,
            'total_count': total_count,
            'title': f"Search results for '{query}'" if query else 'Hotel Search',
        }
        
        return render(request, 'search/list_simple.html', context)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Search error: {str(e)}", exc_info=True)
        
        if request.GET.get('format') == 'json':
            return JsonResponse({'status': 'error', 'results': []}, status=500)
        
        context = {'query': '', 'results': [], 'page_obj': None, 'total_count': 0}
        return render(request, 'search/list_simple.html', context, status=500)


@require_http_methods(['GET'])
def search_autocomplete(request):
    """Autocomplete endpoint for search suggestions.
    
    Uses unified search engine for consistency.
    Returns JSON with results key containing suggestions.
    Minimum 2 chars, max 8 results, case insensitive.
    """
    try:
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 8))
        
        # Use unified engine
        result = search_engine.autocomplete(query, limit=limit)
        return JsonResponse(result)
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Autocomplete error: {str(e)}")
        return JsonResponse({'results': []}, status=500)


@require_http_methods(['GET'])
def search_api(request):
    """Public API endpoint for search.
    
    Used by mobile apps, external integrations, etc.
    
    Example:
        GET /api/search?q=mumbai&price_min=1000&price_max=5000&page=1
        
    Response:
        {
          "status": "success",
          "total": 256,
          "page": 1,
          "page_size": 20,
          "results": [
            {
              "id": 1,
              "name": "Hotel Name",
              "city": "Mumbai",
              "area": "Bandra",
              "price": 2500,
              "original_price": 3000,
              "discount_percent": 17,
              "rating": 4.5,
              "image": "https://...",
              "url": "/hotels/hotel-name/"
            },
            ...
          ],
          "filters": {
            "price": {"min": 500, "max": 25000},
            "ratings": [{"label": "5 Star", "count": 45}, ...],
            "amenities": [{"label": "WiFi", "count": 150}, ...]
          }
        }
    """
    search_list_response = search_list(request)
    
    if isinstance(search_list_response, JsonResponse):
        return search_list_response
    
    return JsonResponse({'error': 'Invalid format'}, status=400)


@require_http_methods(['GET'])
def search_index_api(request):
    """Unified autocomplete API for city/area/property suggestions.
    
    NEW PHASE 2 FORMAT: Returns slug-based routing for canonical URLs.
    Example response:
        [
            {
                "type": "city",
                "name": "Coorg",
                "slug": "coorg",
                "property_count": 45
            },
            {
                "type": "locality",
                "name": "Madikeri",
                "slug": "madikeri",
                "city_slug": "coorg",
                "property_count": 12
            },
            {
                "type": "property",
                "name": "Coorg Grand Stay",
                "slug": "coorg-grand-stay",
                "city_slug": "coorg",
                "locality_slug": "madikeri",
                "property_count": null
            }
        ]
    """
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    results_list = []
    
    # Cities - use slug routing
    cities = (
        City.objects.filter(is_active=True, name__icontains=query)
        .select_related('state')
        .order_by('-popularity_score', 'name')
        [:5]
    )
    for city in cities:
        # Use new clean approval system: status='approved' AND agreement_signed=True
        property_count = Property.objects.filter(
            city=city,
            status='approved',
            agreement_signed=True
        ).count()
        results_list.append({
            'type': 'city',
            'name': city.name,
            'slug': city.slug,
            'property_count': property_count,
        })
    
    # Localities - use slug routing with city_slug
    from apps.core.location_models import Locality
    localities = (
        Locality.objects.filter(is_active=True, name__icontains=query)
        .select_related('city')
        .order_by('-popularity_score', 'name')
        [:5]
    )
    for loc in localities:
        # Use new clean system: status='approved' AND agreement_signed=True
        property_count = Property.objects.filter(
            locality=loc,
            status='approved',
            agreement_signed=True
        ).count()
        results_list.append({
            'type': 'locality',
            'name': loc.name,
            'slug': loc.slug,
            'city_slug': loc.city.slug if loc.city else None,
            'property_count': property_count,
        })
    
    # Properties - use slug routing
    properties = (
        Property.objects.filter(
            name__icontains=query,
            status='approved',
            agreement_signed=True
        )
        .select_related('city', 'locality')
        .order_by('-rating', 'name')
        [:5]
    )
    for prop in properties:
        results_list.append({
            'type': 'property',
            'name': prop.name,
            'slug': prop.slug or f"property-{prop.id}",
            'city_slug': prop.city.slug if prop.city else None,
            'locality_slug': prop.locality.slug if prop.locality else None,
        })
    
    # Sort by type (city > locality > property) then by name
    type_order = {'city': 0, 'locality': 1, 'property': 2}
    results_list.sort(key=lambda x: (type_order.get(x['type'], 3), x['name']))
    
    return JsonResponse(results_list[:15], safe=False)


@require_http_methods(['GET'])
def cities_autocomplete(request):
    """Lightweight city autocomplete for /api/cities endpoint.
    
    PHASE 2: Returns slug for canonical routing.
    """
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    cities = (
        City.objects.filter(is_active=True, name__icontains=query)
        .select_related('state')
        .order_by('-popularity_score', 'name')
        [:8]
    )

    results = [
        {
            'name': city.name,
            'slug': city.slug,
            'state': city.state.name if city.state else '',
        }
        for city in cities
    ]

    return JsonResponse(results, safe=False)


@require_http_methods(['GET'])
def location_autocomplete(request):
    """Location autocomplete for the global search bar."""
    query = (request.GET.get('q') or '').strip()
    limit = int(request.GET.get('limit', 8))

    if len(query) < 2:
        return JsonResponse({"cities": [], "areas": [], "hotels": []})

    cities = City.objects.filter(
        is_active=True,
        name__icontains=query,
    ).annotate(count=Count("hotels")).order_by('-popularity_score', 'name')[:5]

    localities = Locality.objects.filter(
        is_active=True,
        name__icontains=query,
        city__is_active=True,
    ).annotate(count=Count("hotels")).select_related('city').order_by('-popularity_score', 'name')[:5]

    from apps.hotels.selectors import public_properties_queryset

    properties_qs = public_properties_queryset()
    properties = properties_qs.filter(
        Q(name__icontains=query)
    ).select_related('city')[:5]

    city_results = [
        {
            'label': city.display_name or city.name,
            'value': city.display_name or city.name,
            'count': city.count,
            'meta': city.state.name if city.state else 'City',
        }
        for city in cities
    ]

    area_results = []
    for locality in localities:
        label = locality.display_name or locality.name
        area_results.append({
            'label': label,
            'value': label,
            'count': locality.count,
            'meta': locality.city.name if locality.city else '',
        })

    hotel_results = [
        {
            'label': prop.name,
            'value': prop.name,
            'count': 1,
            'meta': prop.city.name if prop.city else '',
        }
        for prop in properties
    ]

    return JsonResponse({
        "cities": city_results[:limit],
        "areas": area_results[:limit],
        "hotels": hotel_results[:limit],
    })


# ── CTR Tracking Helpers ────────────────────────────────────────────

def _track_search_impressions(results):
    """Increment impression counters for properties shown in search results.
    Uses bulk update for efficiency. Non-blocking — failures are logged, not raised.
    """
    try:
        from .models import PropertySearchIndex
        prop_ids = [
            getattr(r, 'id', None) or getattr(r, 'property_id', None)
            for r in results
        ]
        prop_ids = [p for p in prop_ids if p]
        if prop_ids:
            PropertySearchIndex.objects.filter(
                property_id__in=prop_ids,
            ).update(total_impressions=F('total_impressions') + 1)
    except Exception as e:
        logger.debug('Impression tracking failed: %s', e)


@csrf_exempt
@require_http_methods(['POST'])
def track_search_click(request):
    """API endpoint to record a click from search results.

    Called by the frontend when a user clicks a hotel card in search results.
    POST /api/search/track-click/ with JSON body: {"property_id": 123}

    This feeds the CTR pipeline which updates click_through_rate on
    PropertySearchIndex, used by both ranking engines (10-20% weight).
    """
    try:
        body = json.loads(request.body) if request.body else {}
        property_id = body.get('property_id')

        if property_id:
            from .models import PropertySearchIndex
            updated = PropertySearchIndex.objects.filter(
                property_id=property_id,
            ).update(
                total_clicks=F('total_clicks') + 1,
                total_views=F('total_views') + 1,
            )

            if updated:
                from apps.core.analytics import track_event_async

                track_event_async(
                    event_type='hotel_click',
                    request=request,
                    property_id=property_id,
                    properties={
                        'source': body.get('source', 'search_results'),
                        'rank_position': body.get('position'),
                        'query_id': body.get('query_id'),
                    },
                )
        else:
            logger.warning('track_search_click called without property_id')

        return JsonResponse({'success': True}, status=200)

    except Exception as e:
        logger.error('Click tracking error: %s', e)
        return JsonResponse({'success': True}, status=200)


@require_http_methods(['GET'])
def nearby_hotels_api(request):
    """Geospatial search: find hotels near a lat/lng coordinate.

    GET /api/search/nearby/?lat=12.97&lng=77.59&radius=5&limit=20

    Returns PropertySearchIndex results sorted by distance.
    Use cases: "Hotels near airport", "Hotels within 2 km".
    """
    try:
        lat = float(request.GET.get('lat', 0))
        lng = float(request.GET.get('lng', 0))
        radius = float(request.GET.get('radius', 5.0))
        limit = int(request.GET.get('limit', 20))

        if not lat or not lng:
            return JsonResponse({'error': 'lat and lng are required'}, status=400)

        radius = min(radius, 50.0)  # cap at 50 km
        limit = min(limit, 50)

        from .tasks import geospatial_search
        results = geospatial_search(lat, lng, radius_km=radius, limit=limit)

        hotels = []
        for r in results:
            hotels.append({
                'id': r.property_id,
                'name': r.property_name,
                'slug': r.slug,
                'city': r.city_name,
                'area': r.locality_name,
                'rating': float(r.rating),
                'review_count': r.review_count,
                'price_min': float(r.price_min),
                'star_category': r.star_category,
                'distance_km': round(r.distance_km, 2) if hasattr(r, 'distance_km') else None,
                'image': r.featured_image_url,
                'has_free_cancellation': r.has_free_cancellation,
                'rooms_left': r.rooms_left,
            })

        return JsonResponse({'results': hotels, 'count': len(hotels)})

    except Exception as e:
        logger.error('Nearby search error: %s', e)
        return JsonResponse({'error': 'Search failed'}, status=500)


@require_http_methods(['GET'])
def geo_viewport_search(request):
    """Bounding-box search for map viewport — returns all hotels visible in the map area.

    GET /api/search/geo/?lat_min=12.9&lat_max=13.1&lng_min=77.5&lng_max=77.7
        &check_in=2026-06-01&check_out=2026-06-04&guests=2&limit=100

    Used by PropertyMap when the user pans/zooms — returns lightweight pins data.
    Results are cached per viewport bucket (rounded to 2 dp) for 5 minutes.
    """
    import time
    from django.core.cache import cache

    try:
        try:
            lat_min = float(request.GET['lat_min'])
            lat_max = float(request.GET['lat_max'])
            lng_min = float(request.GET['lng_min'])
            lng_max = float(request.GET['lng_max'])
        except (KeyError, ValueError):
            return JsonResponse(
                {'error': 'lat_min, lat_max, lng_min, lng_max are required floats'},
                status=400,
            )

        # Sanity bounds
        if not (-90 <= lat_min < lat_max <= 90) or not (-180 <= lng_min < lng_max <= 180):
            return JsonResponse({'error': 'Invalid coordinate bounds'}, status=400)

        # Cap viewport size to prevent full-table scans on extreme zoom-out
        if (lat_max - lat_min) > 10 or (lng_max - lng_min) > 10:
            return JsonResponse({'error': 'Viewport too large — zoom in to see results'}, status=400)

        limit = min(int(request.GET.get('limit', 100)), 200)
        check_in  = request.GET.get('check_in', '')
        check_out = request.GET.get('check_out', '')
        guests    = int(request.GET.get('guests', 2))

        # Cache key: rounded to 2dp so nearby viewports share cache entries
        cache_key = (
            f"geo_vp:{lat_min:.2f}:{lat_max:.2f}:{lng_min:.2f}:{lng_max:.2f}"
            f":{check_in}:{check_out}:{guests}:{limit}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse({**cached, 'cache_hit': True})

        start = time.monotonic()

        from .models import PropertySearchIndex
        qs = (
            PropertySearchIndex.objects
            .filter(
                is_active=True,
                latitude__gte=lat_min,
                latitude__lte=lat_max,
                longitude__gte=lng_min,
                longitude__lte=lng_max,
            )
            .order_by('-composite_score')
            .values(
                'property_id', 'property_name', 'slug',
                'latitude', 'longitude',
                'price_min', 'star_category', 'rating',
                'review_count', 'featured_image_url',
                'has_free_cancellation', 'rooms_left',
                'city_name', 'locality_name',
            )[:limit]
        )

        pins = []
        for p in qs:
            pins.append({
                'id':          p['property_id'],
                'name':        p['property_name'],
                'slug':        p['slug'],
                'lat':         float(p['latitude']),
                'lng':         float(p['longitude']),
                'price':       float(p['price_min']) if p['price_min'] else None,
                'stars':       p['star_category'],
                'rating':      float(p['rating']) if p['rating'] else None,
                'reviews':     p['review_count'],
                'image':       p['featured_image_url'],
                'free_cancel': p['has_free_cancellation'],
                'rooms_left':  p['rooms_left'],
                'city':        p['city_name'],
                'area':        p['locality_name'],
            })

        latency_ms = (time.monotonic() - start) * 1000
        result = {
            'pins':       pins,
            'count':      len(pins),
            'latency_ms': round(latency_ms, 1),
            'cache_hit':  False,
            'bounds': {
                'lat_min': lat_min, 'lat_max': lat_max,
                'lng_min': lng_min, 'lng_max': lng_max,
            },
        }

        # Cache for 5 minutes
        cache.set(cache_key, result, timeout=300)

        # OTel span attribute
        try:
            from apps.core.telemetry import record_search_event
            record_search_event(
                query=f"viewport:{lat_min:.2f},{lng_min:.2f}-{lat_max:.2f},{lng_max:.2f}",
                result_count=len(pins),
                cache_hit=False,
                latency_ms=latency_ms,
            )
        except Exception:
            pass

        return JsonResponse(result)

    except Exception as e:
        logger.error('Geo viewport search error: %s', e)
        return JsonResponse({'error': 'Search failed'}, status=500)