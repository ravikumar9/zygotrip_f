"""
Geo Search Engine — Production-Grade.

Implements:
  - Bounding box viewport search (map integration)
  - Nearby radius search with haversine
  - Distance-sorted results
  - City context loading (CTXCR pattern)
  - Locality-level search with popularity scoring
  - GeoJSON cluster aggregation for map tiles
  - Google Places resolve → radius search pipeline
  - Multi-sort: distance, price, ranking, rating
  - Database index recommendations (see GeoSearchIndex model)

DB Indexes required (applied via migration):
  - Property(latitude, longitude) — compound for bounding box
  - PropertySearchIndex(latitude, longitude) — for denormalized search table
"""
import math
from math import radians, cos, sin, asin, sqrt
from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from decimal import Decimal
import logging

from apps.core.models import TimeStampedModel

logger = logging.getLogger("zygotrip")


def _get_property_model():
    return apps.get_model('hotels', 'Property')


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points (km)
    Haversine formula: accurate for short distances
    """
    lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c  # Earth radius
    return round(km, 1)


def hotels_in_bounding_box(ne_lat, ne_lng, sw_lat, sw_lng):
    """
    Return hotels within map viewport
    
    Args:
        ne_lat: North-east corner latitude
        ne_lng: North-east corner longitude
        sw_lat: South-west corner latitude
        sw_lng: South-west corner longitude
    
    Returns:
        QuerySet of Property objects
    """
    Property = _get_property_model()
    return Property.objects.filter(
        latitude__gte=sw_lat,
        latitude__lte=ne_lat,
        longitude__gte=sw_lng,
        longitude__lte=ne_lng
    )


def hotels_near_point(lat, lng, radius_km=10, limit=50):
    """
    Return hotels within radius of point
    
    Uses bounding box approximation first (fast),
    then calculates exact distance (accurate)
    """
    Property = _get_property_model()
    # Rough bounding box (1 degree ≈ 111 km)
    lat_delta = Decimal(radius_km) / Decimal(111)
    lng_delta = Decimal(radius_km) / Decimal(111 * cos(radians(float(lat))))
    
    # Fast filter: bounding box
    candidates = Property.objects.filter(
        latitude__gte=lat - lat_delta,
        latitude__lte=lat + lat_delta,
        longitude__gte=lng - lng_delta,
        longitude__lte=lng + lng_delta
    )
    
    # Accurate filter: calculate exact distance
    results = []
    for hotel in candidates:
        distance = haversine_distance(lat, lng, hotel.latitude, hotel.longitude)
        if distance <= radius_km:
            hotel.distance = distance  # Attach for sorting
            results.append(hotel)
    
    # Sort by distance
    results.sort(key=lambda h: h.distance)
    return results[:limit]


def sort_hotels_by_distance(hotels, reference_lat, reference_lng):
    """
    Sort hotels by distance from reference point
    Attaches .distance attribute to each hotel
    """
    for hotel in hotels:
        hotel.distance = haversine_distance(
            reference_lat, reference_lng,
            hotel.latitude, hotel.longitude
        )
    
    return sorted(hotels, key=lambda h: h.distance)


def get_city_context(city_code):
    """
    Load entire city context (CTXCR pattern)
    
    Returns:
        {
            'city': City object,
            'localities': QuerySet of Locality,
            'bounding_box': {'ne': {...}, 'sw': {...}, 'centre': {...}},
            'hotel_count': int
        }
    """
    from apps.core.location_models import City, Locality
    Property = _get_property_model()
    
    try:
        city = City.objects.get(code=city_code)
    except City.DoesNotExist:
        return None
    
    localities = Locality.objects.filter(city=city, is_active=True)
    hotel_count = Property.objects.filter(city=city).count()
    
    return {
        'city': city,
        'localities': localities,
        'bounding_box': {
            'ne': {'lat': city.ne_lat, 'lng': city.ne_lng},
            'sw': {'lat': city.sw_lat, 'lng': city.sw_lng},
            'centre': {'lat': city.latitude, 'lng': city.longitude}
        },
        'hotel_count': hotel_count
    }


# ── Advanced Geo Functions ─────────────────────────────────────────────────────


def map_search(ne_lat, ne_lng, sw_lat, sw_lng, filters=None, limit=100):
    """
    Full map-search endpoint: bounding box + optional filters.
    Returns lightweight hotel pins optimized for map rendering.
    Includes price and nearest landmark label for map overlays.

    Args:
        ne_lat/ne_lng/sw_lat/sw_lng: viewport corners
        filters: dict with optional keys: min_price, max_price, star_rating, amenities, zoom
        limit: max results
    """
    Property = _get_property_model()

    qs = Property.objects.filter(
        latitude__gte=sw_lat,
        latitude__lte=ne_lat,
        longitude__gte=sw_lng,
        longitude__lte=ne_lng,
        is_active=True,
    )

    if filters:
        if 'min_price' in filters:
            qs = qs.filter(min_rate__gte=filters['min_price'])
        if 'max_price' in filters:
            qs = qs.filter(min_rate__lte=filters['max_price'])
        if 'star_rating' in filters:
            qs = qs.filter(star_rating__in=filters['star_rating'])

    qs = qs.only(
        'id', 'name', 'slug', 'latitude', 'longitude', 'city',
        'star_rating', 'rating', 'review_count', 'landmark',
        'has_free_cancellation', 'is_trending',
    )[:limit]

    # Try to get pre-computed landmark labels from GeoIndex
    geo_index_map = {}
    try:
        prop_ids = [h.pk for h in qs]
        for gi in GeoIndex.objects.filter(property_id__in=prop_ids).values('property_id', 'nearest_landmark', 'min_rate'):
            geo_index_map[gi['property_id']] = gi
    except Exception:
        pass

    results = []
    for h in qs:
        gi = geo_index_map.get(h.pk, {})
        results.append({
            'id': h.pk,
            'name': h.name,
            'slug': getattr(h, 'slug', ''),
            'lat': float(h.latitude) if h.latitude else None,
            'lng': float(h.longitude) if h.longitude else None,
            'star': getattr(h, 'star_rating', None),
            'rating': float(h.rating) if h.rating else None,
            'reviews': getattr(h, 'review_count', 0) or 0,
            'price': float(gi.get('min_rate')) if gi.get('min_rate') else None,
            'landmark_label': gi.get('nearest_landmark', '') or getattr(h, 'landmark', '') or '',
            'free_cancel': bool(getattr(h, 'has_free_cancellation', False)),
            'trending': bool(getattr(h, 'is_trending', False)),
        })

    return results


def cluster_for_zoom(ne_lat, ne_lng, sw_lat, sw_lng, grid_size=0.05, zoom_level=None):
    """
    Group hotels into clusters for map zoom levels.
    Uses simple grid clustering (performant).

    When zoom_level is provided, grid_size is auto-computed.
    Returns list of clusters: [{lat, lng, count, representative_name, avg_price, avg_rating}]
    """
    from apps.core.geo_utils import grid_size_for_zoom

    if zoom_level is not None:
        grid_size = grid_size_for_zoom(zoom_level)

    Property = _get_property_model()

    hotels = Property.objects.filter(
        latitude__gte=sw_lat,
        latitude__lte=ne_lat,
        longitude__gte=sw_lng,
        longitude__lte=ne_lng,
        is_active=True,
    ).values_list('id', 'name', 'latitude', 'longitude', 'rating')

    grid = {}
    for hid, name, lat, lng, rating in hotels:
        if lat is None or lng is None:
            continue
        lat_f, lng_f = float(lat), float(lng)
        cell = (round(lat_f / grid_size), round(lng_f / grid_size))
        if cell not in grid:
            grid[cell] = {
                'lat_sum': 0, 'lng_sum': 0, 'count': 0,
                'name': name, 'rating_sum': 0, 'ids': [],
            }
        grid[cell]['lat_sum'] += lat_f
        grid[cell]['lng_sum'] += lng_f
        grid[cell]['count'] += 1
        grid[cell]['rating_sum'] += float(rating or 0)
        grid[cell]['ids'].append(hid)

    return [
        {
            'lat': data['lat_sum'] / data['count'],
            'lng': data['lng_sum'] / data['count'],
            'count': data['count'],
            'representative_name': data['name'],
            'avg_rating': round(data['rating_sum'] / data['count'], 1) if data['count'] else 0,
            'property_ids': data['ids'][:10],  # Cap for response size
        }
        for data in grid.values()
    ]


def nearby_localities(lat, lng, radius_km=5, limit=20):
    """
    Find localities near a coordinate.
    Useful for "explore nearby" feature.
    """
    from apps.core.location_models import Locality

    lat_delta = Decimal(radius_km) / Decimal(111)
    lng_delta = Decimal(radius_km) / Decimal(111 * cos(radians(float(lat))))

    return list(
        Locality.objects.filter(
            latitude__gte=lat - lat_delta,
            latitude__lte=lat + lat_delta,
            longitude__gte=lng - lng_delta,
            longitude__lte=lng + lng_delta,
            is_active=True,
        )[:limit]
    )


# ── Geo Index Model (for migration) ───────────────────────────────────────────


class GeoIndex(TimeStampedModel):
    """
    Lightweight denormalized geo index for fast spatial queries.
    Rebuilt nightly or on property change via signal.

    Includes geohash for prefix-based spatial queries:
      - geohash6 (~1.2km precision) for city-level clustering
      - geohash4 (~39km precision) for region-level grouping
    """
    property = models.OneToOneField(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='geo_index',
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7, db_index=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, db_index=True)
    geohash6 = models.CharField(
        max_length=6, blank=True, db_index=True,
        help_text="Geohash precision 6 (~1.2km) for spatial prefix queries",
    )
    geohash4 = models.CharField(
        max_length=4, blank=True, db_index=True,
        help_text="Geohash precision 4 (~39km) for region-level clustering",
    )
    city_code = models.CharField(max_length=20, db_index=True)
    locality_slug = models.CharField(max_length=100, blank=True, db_index=True)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    min_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    # Pre-computed nearest landmark label (updated on rebuild)
    nearest_landmark = models.CharField(
        max_length=200, blank=True,
        help_text="Pre-computed label like '500m from MG Road'",
    )

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['latitude', 'longitude'], name='geo_idx_latlon'),
            models.Index(fields=['city_code', 'is_active'], name='geo_idx_city_active'),
            models.Index(fields=['latitude', 'longitude', 'is_active'],
                         name='geo_idx_latlon_active'),
            models.Index(fields=['geohash6', 'is_active'], name='geo_idx_ghash6_active'),
            models.Index(fields=['geohash4'], name='geo_idx_ghash4'),
        ]

    def __str__(self):
        return f'GeoIndex({self.property_id}, {self.latitude}, {self.longitude}, gh={self.geohash6})'


def rebuild_geo_index(property_id=None):
    """Rebuild geo index from Property records. Populates geohash + landmark labels."""
    from apps.core.geo_utils import geohash_encode, get_nearby_landmarks_for_property

    Property = _get_property_model()

    qs = Property.objects.all()
    if property_id:
        qs = qs.filter(pk=property_id)

    count = 0
    for prop in qs.select_related('city').iterator():
        if not prop.latitude or not prop.longitude:
            continue

        lat_f = float(prop.latitude)
        lng_f = float(prop.longitude)
        gh6 = geohash_encode(lat_f, lng_f, precision=6)
        gh4 = geohash_encode(lat_f, lng_f, precision=4)

        # Compute nearest landmark label
        nearest_label = ''
        try:
            landmarks = get_nearby_landmarks_for_property(prop, radius_km=5, limit=1)
            if landmarks:
                nearest_label = landmarks[0].get('label', '')
        except Exception:
            pass

        GeoIndex.objects.update_or_create(
            property=prop,
            defaults={
                'latitude': prop.latitude,
                'longitude': prop.longitude,
                'geohash6': gh6,
                'geohash4': gh4,
                'city_code': getattr(prop, 'city_code', '') or '',
                'locality_slug': getattr(prop, 'locality_slug', '') or '',
                'star_rating': getattr(prop, 'star_rating', None),
                'min_rate': getattr(prop, 'min_rate', None),
                'rating': getattr(prop, 'rating', None),
                'is_active': bool(getattr(prop, 'is_active', True)),
                'nearest_landmark': nearest_label[:200],
            },
        )
        count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED GEO SEARCH — Google Places Pipeline + Multi-Sort
# ═══════════════════════════════════════════════════════════════════════════════


def radius_search(lat, lng, radius_km=None, sort_by="distance", limit=50, filters=None):
    """
    Search properties within radius with advanced sorting.

    Args:
        lat/lng: Center point coordinates
        radius_km: Search radius (default from settings)
        sort_by: 'distance' | 'price' | 'ranking' | 'rating'
        limit: Max results
        filters: Optional dict: min_price, max_price, star_rating, property_type

    Returns:
        List of dicts with distance_km attached.
    """
    Property = _get_property_model()

    if radius_km is None:
        radius_km = getattr(settings, "GEO_SEARCH_DEFAULT_RADIUS_KM", 10)
    radius_km = min(radius_km, getattr(settings, "GEO_SEARCH_MAX_RADIUS_KM", 50))

    lat_delta = Decimal(radius_km) / Decimal(111)
    lng_delta = Decimal(radius_km) / Decimal(111 * cos(radians(float(lat))))

    qs = Property.objects.filter(
        latitude__gte=lat - lat_delta,
        latitude__lte=lat + lat_delta,
        longitude__gte=lng - lng_delta,
        longitude__lte=lng + lng_delta,
    )

    # Apply filters
    if filters:
        if filters.get("min_price"):
            qs = qs.filter(base_price__gte=filters["min_price"])
        if filters.get("max_price"):
            qs = qs.filter(base_price__lte=filters["max_price"])
        if filters.get("star_rating"):
            qs = qs.filter(star_rating__gte=filters["star_rating"])
        if filters.get("property_type"):
            qs = qs.filter(property_type=filters["property_type"])

    results = []
    for prop in qs.select_related("city", "city__state")[:limit * 3]:
        if not prop.latitude or not prop.longitude:
            continue
        dist = haversine_distance(lat, lng, prop.latitude, prop.longitude)
        if dist <= radius_km:
            results.append({
                "id": prop.pk,
                "name": prop.name,
                "slug": getattr(prop, "slug", ""),
                "property_type": getattr(prop, "property_type", ""),
                "star_rating": getattr(prop, "star_rating", None),
                "base_price": float(prop.base_price) if getattr(prop, "base_price", None) else 0,
                "latitude": float(prop.latitude),
                "longitude": float(prop.longitude),
                "city": prop.city.name if prop.city else "",
                "state": prop.city.state.name if prop.city and prop.city.state else "",
                "address": getattr(prop, "address", "") or "",
                "distance_km": dist,
                "rating_average": float(getattr(prop, "rating_average", 0) or 0),
                "review_count": getattr(prop, "review_count", 0) or 0,
            })

    # Sort
    sort_keys = {
        "distance": lambda r: r["distance_km"],
        "price": lambda r: r["base_price"],
        "rating": lambda r: -r["rating_average"],
        "ranking": lambda r: _ranking_score(r),
    }
    key_fn = sort_keys.get(sort_by, sort_keys["distance"])
    results.sort(key=key_fn)
    return results[:limit]


def resolve_and_search(query, radius_km=None, sort_by="distance", limit=50, filters=None):
    """
    Full pipeline: query → geocode → radius search.

    Tries:
    1. Google Geocoding (if API key configured)
    2. Local DB city lookup
    3. Returns empty if location cannot be resolved

    Returns:
        {
            'query': str,
            'resolved_location': {lat, lng, name, type, source} | None,
            'results': [...],
            'total': int,
            'radius_km': float,
            'sort_by': str,
        }
    """
    from apps.core import google_places
    from apps.core.location_models import City

    resolved = None
    default_radius = radius_km or getattr(settings, "GEO_SEARCH_DEFAULT_RADIUS_KM", 10)

    # Try Google Geocoding
    if google_places.is_enabled():
        geo = google_places.geocode(query)
        if geo and geo.get("latitude") and geo.get("longitude"):
            loc_type = google_places.normalize_to_location_type(geo.get("types", []))
            resolved = {
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "name": geo.get("formatted_address", query),
                "city": geo.get("city", ""),
                "state": geo.get("state", ""),
                "country": geo.get("country", ""),
                "type": loc_type,
                "source": "google",
            }

    # Fallback: local DB
    if not resolved:
        city = (
            City.objects.filter(
                Q(name__iexact=query) | Q(alternate_names__icontains=query),
                is_active=True,
            )
            .select_related("state")
            .first()
        )
        if city and city.latitude and city.longitude:
            resolved = {
                "latitude": float(city.latitude),
                "longitude": float(city.longitude),
                "name": city.name,
                "city": city.name,
                "state": city.state.name if city.state else "",
                "country": "India",
                "type": "city",
                "source": "local_db",
            }

    if not resolved:
        return {
            "query": query,
            "resolved_location": None,
            "results": [],
            "total": 0,
            "radius_km": default_radius,
            "sort_by": sort_by,
            "error": "Could not resolve location",
        }

    results = radius_search(
        resolved["latitude"], resolved["longitude"],
        radius_km=default_radius, sort_by=sort_by, limit=limit, filters=filters,
    )

    return {
        "query": query,
        "resolved_location": resolved,
        "results": results,
        "total": len(results),
        "radius_km": default_radius,
        "sort_by": sort_by,
    }


def _ranking_score(prop):
    """
    Composite ranking score for geo search results.

    Signals (weighted):
    - Distance relevance (30%) — closer = better
    - Rating quality (20%)
    - Review volume (10%)
    - Price competitiveness (15%)
    - Popularity (25%)
    """
    dist = prop.get("distance_km", 10)
    rating = prop.get("rating_average", 0)
    reviews = prop.get("review_count", 0)
    price = prop.get("base_price", 0)

    distance_score = max(0, 1.0 - dist / 50)
    rating_score = rating / 5.0 if rating else 0
    review_score = min(1.0, math.log1p(reviews) / 5.0) if reviews else 0
    price_score = max(0, 1.0 - abs(price - 3000) / 10000) if price > 0 else 0.5
    popularity_score = review_score

    return -(
        0.30 * distance_score
        + 0.20 * rating_score
        + 0.10 * review_score
        + 0.15 * price_score
        + 0.25 * popularity_score
    )