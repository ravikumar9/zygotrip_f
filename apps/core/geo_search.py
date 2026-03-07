"""
Geo Search Engine — Production-Grade.

Implements:
  - Bounding box viewport search (map integration)
  - Nearby radius search with haversine
  - Distance-sorted results
  - City context loading (CTXCR pattern)
  - Locality-level search with popularity scoring
  - GeoJSON cluster aggregation for map tiles
  - Database index recommendations (see GeoSearchIndex model)

DB Indexes required (applied via migration):
  - Property(latitude, longitude) — compound for bounding box
  - PropertySearchIndex(latitude, longitude) — for denormalized search table
"""
from math import radians, cos, sin, asin, sqrt
from django.apps import apps
from django.db import models
from django.db.models import Q, F
from decimal import Decimal

from apps.core.models import TimeStampedModel


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

    Args:
        ne_lat/ne_lng/sw_lat/sw_lng: viewport corners
        filters: dict with optional keys: min_price, max_price, star_rating, amenities
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
        'id', 'name', 'latitude', 'longitude', 'city',
        'star_rating', 'rating', 'review_count',
    )[:limit]

    return [
        {
            'id': h.pk,
            'name': h.name,
            'lat': float(h.latitude) if h.latitude else None,
            'lng': float(h.longitude) if h.longitude else None,
            'star': getattr(h, 'star_rating', None),
            'rating': float(h.rating) if h.rating else None,
            'reviews': getattr(h, 'review_count', 0) or 0,
        }
        for h in qs
    ]


def cluster_for_zoom(ne_lat, ne_lng, sw_lat, sw_lng, grid_size=0.05):
    """
    Group hotels into clusters for map zoom levels.
    Uses simple grid clustering (performant).

    Returns list of clusters: [{lat, lng, count, representative_name}]
    """
    Property = _get_property_model()

    hotels = Property.objects.filter(
        latitude__gte=sw_lat,
        latitude__lte=ne_lat,
        longitude__gte=sw_lng,
        longitude__lte=ne_lng,
        is_active=True,
    ).values_list('id', 'name', 'latitude', 'longitude')

    grid = {}
    for hid, name, lat, lng in hotels:
        if lat is None or lng is None:
            continue
        lat_f, lng_f = float(lat), float(lng)
        cell = (round(lat_f / grid_size), round(lng_f / grid_size))
        if cell not in grid:
            grid[cell] = {'lat_sum': 0, 'lng_sum': 0, 'count': 0, 'name': name}
        grid[cell]['lat_sum'] += lat_f
        grid[cell]['lng_sum'] += lng_f
        grid[cell]['count'] += 1

    return [
        {
            'lat': data['lat_sum'] / data['count'],
            'lng': data['lng_sum'] / data['count'],
            'count': data['count'],
            'representative_name': data['name'],
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
    """
    property = models.OneToOneField(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='geo_index',
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7, db_index=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, db_index=True)
    city_code = models.CharField(max_length=20, db_index=True)
    locality_slug = models.CharField(max_length=100, blank=True, db_index=True)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    min_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['latitude', 'longitude'], name='geo_idx_latlon'),
            models.Index(fields=['city_code', 'is_active'], name='geo_idx_city_active'),
            models.Index(fields=['latitude', 'longitude', 'is_active'],
                         name='geo_idx_latlon_active'),
        ]

    def __str__(self):
        return f'GeoIndex({self.property_id}, {self.latitude}, {self.longitude})'


def rebuild_geo_index(property_id=None):
    """Rebuild geo index from Property records."""
    Property = _get_property_model()

    qs = Property.objects.all()
    if property_id:
        qs = qs.filter(pk=property_id)

    count = 0
    for prop in qs.iterator():
        if not prop.latitude or not prop.longitude:
            continue
        GeoIndex.objects.update_or_create(
            property=prop,
            defaults={
                'latitude': prop.latitude,
                'longitude': prop.longitude,
                'city_code': getattr(prop, 'city_code', '') or '',
                'locality_slug': getattr(prop, 'locality_slug', '') or '',
                'star_rating': getattr(prop, 'star_rating', None),
                'min_rate': getattr(prop, 'min_rate', None),
                'rating': getattr(prop, 'rating', None),
                'is_active': bool(getattr(prop, 'is_active', True)),
            },
        )
        count += 1
    return count