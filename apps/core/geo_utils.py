"""
Geo Utilities — Geohash encoding, landmark distance labels, PostGIS-ready helpers.

Provides:
  - Geohash encoding/decoding (base-32, precision 1-12)
  - Geohash neighbor computation for spatial search
  - Landmark distance labels ("500m from MG Road", "1.2km from Baga Beach")
  - Distance formatting (human-readable)
  - Bounding box utilities for geohash-based indexing
"""
import math
import logging
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger("zygotrip.geo")

# ── Geohash Implementation ────────────────────────────────────────────────────

_BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
_DECODE_MAP = {c: i for i, c in enumerate(_BASE32)}

_NEIGHBORS = {
    'right':  {'even': 'bc01fg45telefonstr89telefonstr', 'odd': 'p0r21436x8zb9dcf5h7kjnmqesgutwvy'},
    'left':   {'even': '238967debc01telefonstr45telefonstr', 'odd': '14telefonstr0365h7k6d8telefonst9n5esgutwvy'},
    'top':    {'even': 'p0r21436x8zb9dcf5h7kjnmqesgutwvy', 'odd': 'bc01fg45telefonstr89telefonstr'},
    'bottom': {'even': '14telefonstr0365h7k6d8telefonst9n5esgutwvy', 'odd': '238967debc01telefonstr45telefonstr'},
}
_BORDERS = {
    'right':  {'even': 'bcfguvyz', 'odd': 'prxz'},
    'left':   {'even': '0145hjnp', 'odd': '028b'},
    'top':    {'even': 'prxz',     'odd': 'bcfguvyz'},
    'bottom': {'even': '028b',     'odd': '0145hjnp'},
}


def geohash_encode(latitude, longitude, precision=6):
    """
    Encode latitude/longitude into a geohash string.

    Args:
        latitude: float, -90 to 90
        longitude: float, -180 to 180
        precision: int, 1-12 (default 6, ~1.2km accuracy)

    Returns:
        Geohash string of given precision.

    Precision table:
        1 → ~5000km    4 → ~39km     7 → ~153m    10 → ~1.2m
        2 → ~1250km    5 → ~4.9km    8 → ~19m     11 → ~0.15m
        3 → ~156km     6 → ~1.2km    9 → ~2.4m    12 → ~0.019m
    """
    lat = float(latitude)
    lng = float(longitude)
    precision = max(1, min(12, int(precision)))

    lat_range = [-90.0, 90.0]
    lng_range = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng > mid:
                ch |= bits[bit]
                lng_range[0] = mid
            else:
                lng_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                ch |= bits[bit]
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[ch])
            bit = 0
            ch = 0

    return ''.join(geohash)


def geohash_decode(geohash_str):
    """
    Decode a geohash string into (latitude, longitude, lat_err, lng_err).

    Returns:
        Tuple of (lat, lng, lat_error, lng_error)
    """
    lat_range = [-90.0, 90.0]
    lng_range = [-180.0, 180.0]
    even = True

    for char in geohash_str:
        cd = _DECODE_MAP.get(char, 0)
        for mask in [16, 8, 4, 2, 1]:
            if even:
                mid = (lng_range[0] + lng_range[1]) / 2
                if cd & mask:
                    lng_range[0] = mid
                else:
                    lng_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if cd & mask:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            even = not even

    lat = (lat_range[0] + lat_range[1]) / 2
    lng = (lng_range[0] + lng_range[1]) / 2
    lat_err = (lat_range[1] - lat_range[0]) / 2
    lng_err = (lng_range[1] - lng_range[0]) / 2

    return lat, lng, lat_err, lng_err


def geohash_neighbors(geohash_str):
    """
    Get all 8 neighboring geohash cells (for spatial expansion queries).

    Returns:
        Dict with keys: top, bottom, left, right, topleft, topright, bottomleft, bottomright
    """
    right = _neighbor(geohash_str, 'right')
    left = _neighbor(geohash_str, 'left')
    top = _neighbor(geohash_str, 'top')
    bottom = _neighbor(geohash_str, 'bottom')

    return {
        'top': top,
        'bottom': bottom,
        'left': left,
        'right': right,
        'topleft': _neighbor(top, 'left'),
        'topright': _neighbor(top, 'right'),
        'bottomleft': _neighbor(bottom, 'left'),
        'bottomright': _neighbor(bottom, 'right'),
    }


def _neighbor(geohash_str, direction):
    """Compute adjacent geohash in given direction."""
    if not geohash_str:
        return ''
    last_char = geohash_str[-1]
    parent = geohash_str[:-1]
    parity = 'even' if len(geohash_str) % 2 == 0 else 'odd'

    if last_char in _BORDERS.get(direction, {}).get(parity, ''):
        parent = _neighbor(parent, direction)

    neighbors_str = _NEIGHBORS.get(direction, {}).get(parity, '')
    idx = _DECODE_MAP.get(last_char, 0)
    if idx < len(neighbors_str):
        return parent + neighbors_str[idx]
    return parent + last_char


def geohash_bounding_box(geohash_str):
    """
    Get bounding box for a geohash cell.

    Returns:
        Dict with ne_lat, ne_lng, sw_lat, sw_lng
    """
    lat, lng, lat_err, lng_err = geohash_decode(geohash_str)
    return {
        'ne_lat': lat + lat_err,
        'ne_lng': lng + lng_err,
        'sw_lat': lat - lat_err,
        'sw_lng': lng - lng_err,
    }


def geohash_precision_for_radius(radius_km):
    """
    Choose optimal geohash precision for a given search radius.

    Returns precision level (1-8) that best matches the radius.
    """
    # Approximate cell size per precision level (km)
    sizes = {1: 5000, 2: 1250, 3: 156, 4: 39, 5: 4.9, 6: 1.2, 7: 0.15, 8: 0.019}
    for precision, size in sizes.items():
        if size <= radius_km * 2:
            return max(1, precision - 1)
    return 6


# ── Distance & Formatting ─────────────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance in km between two coordinates."""
    lon1, lat1, lon2, lat2 = map(radians, [float(lng1), float(lat1), float(lng2), float(lat2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def format_distance(distance_km):
    """
    Format distance into human-readable label.

    Examples:
        0.3  → "300m"
        0.5  → "500m"
        1.2  → "1.2km"
        0.05 → "50m"
        15.0 → "15km"
    """
    if distance_km is None:
        return ''
    d = float(distance_km)
    if d < 0.01:
        return '<10m'
    if d < 1.0:
        meters = int(round(d * 1000, -1))  # Round to nearest 10m
        if meters < 10:
            meters = 10
        return f'{meters}m'
    if d < 10:
        return f'{d:.1f}km'
    return f'{int(round(d))}km'


def distance_from_landmark_label(hotel_lat, hotel_lng, landmark_name, landmark_lat, landmark_lng):
    """
    Generate a human-readable distance label from a landmark.

    Args:
        hotel_lat, hotel_lng: Hotel coordinates
        landmark_name: e.g. "Baga Beach", "MG Road"
        landmark_lat, landmark_lng: Landmark coordinates

    Returns:
        String like "500m from Baga Beach" or "1.2km from MG Road"
    """
    dist = haversine_km(hotel_lat, hotel_lng, landmark_lat, landmark_lng)
    formatted = format_distance(dist)
    return f'{formatted} from {landmark_name}'


def compute_landmark_distances(hotel_lat, hotel_lng, landmarks, max_results=3):
    """
    Compute distances to multiple landmarks and return the closest ones.

    Args:
        hotel_lat, hotel_lng: Hotel coordinates
        landmarks: List of dicts with keys: name, latitude, longitude
        max_results: Number of closest landmarks to return

    Returns:
        List of dicts: [{name, distance_km, label}, ...]
    """
    if not landmarks or not hotel_lat or not hotel_lng:
        return []

    results = []
    for lm in landmarks:
        try:
            lm_lat = float(lm.get('latitude', 0))
            lm_lng = float(lm.get('longitude', 0))
            if not lm_lat or not lm_lng:
                continue
            dist = haversine_km(hotel_lat, hotel_lng, lm_lat, lm_lng)
            name = lm.get('name', '')
            results.append({
                'name': name,
                'distance_km': round(dist, 2),
                'label': f'{format_distance(dist)} from {name}',
            })
        except (ValueError, TypeError):
            continue

    results.sort(key=lambda r: r['distance_km'])
    return results[:max_results]


def get_nearby_landmarks_for_property(property_obj, radius_km=5, limit=3):
    """
    Find nearby landmarks from the Locality model for a property.
    Returns distance labels like "500m from MG Road".

    Args:
        property_obj: Property instance with latitude/longitude
        radius_km: Search radius
        limit: Max landmarks to return

    Returns:
        List of dicts with name, distance_km, label
    """
    from apps.core.location_models import Locality

    lat = getattr(property_obj, 'latitude', None)
    lng = getattr(property_obj, 'longitude', None)
    if not lat or not lng:
        return []

    lat_f, lng_f = float(lat), float(lng)
    lat_delta = radius_km / 111
    lng_delta = radius_km / (111 * cos(radians(lat_f)))

    localities = Locality.objects.filter(
        latitude__gte=Decimal(str(lat_f - lat_delta)),
        latitude__lte=Decimal(str(lat_f + lat_delta)),
        longitude__gte=Decimal(str(lng_f - lng_delta)),
        longitude__lte=Decimal(str(lng_f + lng_delta)),
        is_active=True,
    ).values('name', 'latitude', 'longitude', 'landmarks')

    all_landmarks = []

    # Add localities themselves as landmarks
    for loc in localities:
        all_landmarks.append({
            'name': loc['name'],
            'latitude': float(loc['latitude']),
            'longitude': float(loc['longitude']),
        })
        # Also parse comma-separated landmarks from the locality
        lm_text = loc.get('landmarks', '') or ''
        if lm_text:
            for lm_name in lm_text.split(','):
                lm_name = lm_name.strip()
                if lm_name:
                    # Use locality coords as proxy for landmark coords
                    all_landmarks.append({
                        'name': lm_name,
                        'latitude': float(loc['latitude']),
                        'longitude': float(loc['longitude']),
                    })

    # Also check the property's own landmark field
    prop_landmark = getattr(property_obj, 'landmark', '')
    if prop_landmark:
        for lm_name in prop_landmark.split(','):
            lm_name = lm_name.strip()
            if lm_name and property_obj.city:
                all_landmarks.append({
                    'name': lm_name,
                    'latitude': float(property_obj.city.latitude) if property_obj.city.latitude else lat_f,
                    'longitude': float(property_obj.city.longitude) if property_obj.city.longitude else lng_f,
                })

    return compute_landmark_distances(lat_f, lng_f, all_landmarks, max_results=limit)


# ── Zoom-Level Helpers ─────────────────────────────────────────────────────────

def grid_size_for_zoom(zoom_level):
    """
    Compute grid size for map clustering based on zoom level.

    Google Maps zoom levels:
        1  → world        8  → city         15 → streets
        3  → continent    10 → city detail  18 → building
        5  → country      12 → neighborhood 20 → most zoomed

    Returns:
        Grid size in degrees for clustering.
    """
    zoom = int(zoom_level or 12)
    # Higher zoom = smaller grid = more detail
    mapping = {
        1: 10.0, 2: 5.0, 3: 3.0, 4: 2.0, 5: 1.0,
        6: 0.5, 7: 0.3, 8: 0.15, 9: 0.08, 10: 0.04,
        11: 0.02, 12: 0.01, 13: 0.005, 14: 0.003,
        15: 0.001, 16: 0.0005, 17: 0.0003, 18: 0.0001,
    }
    return mapping.get(zoom, 0.01)


def should_cluster(zoom_level, hotel_count):
    """
    Decide whether to cluster hotels or show individual pins.

    Clusters when zoomed out with many hotels; shows pins when zoomed in.
    """
    zoom = int(zoom_level or 12)
    if zoom >= 15:
        return False  # Always show individual pins when very zoomed in
    if zoom >= 13 and hotel_count < 30:
        return False
    if zoom >= 10 and hotel_count < 10:
        return False
    return hotel_count > 5
