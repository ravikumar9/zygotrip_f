"""
Google Places API integration for global location search.

Provides:
  1. Autocomplete suggestions (Places Autocomplete)
  2. Place details (geocoding, place_id → lat/lng)
  3. Geocoding (address → lat/lng)
  4. Reverse geocoding (lat/lng → address)

Falls back gracefully to local DB search when API key is not configured.
"""
import logging
import requests
from functools import lru_cache
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("zygotrip")

# Google API endpoints
PLACES_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Cache TTLs
AUTOCOMPLETE_CACHE_TTL = 300    # 5 minutes
PLACE_DETAILS_CACHE_TTL = 86400  # 24 hours
GEOCODE_CACHE_TTL = 86400        # 24 hours


def is_enabled() -> bool:
    """Check if Google Places API is configured."""
    return bool(getattr(settings, "GOOGLE_MAPS_API_KEY", ""))


def _get_api_key() -> str:
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "")


def autocomplete(
    query: str,
    types: str = "(regions)",
    language: str = "en",
    components: str = "",
    session_token: str = "",
    location_bias: Optional[tuple] = None,
) -> list[dict]:
    """
    Google Places Autocomplete.

    Args:
        query: User's search input
        types: Place types filter.
               '(regions)' - cities/states/countries
               '(cities)' - cities only
               'establishment' - businesses/landmarks
               'geocode' - all geocoding results
               '' - no filter (all results)
        language: Response language
        components: Country restriction (e.g. 'country:in')
        session_token: For billing session grouping
        location_bias: (lat, lng) to bias results toward

    Returns:
        List of prediction dicts:
        [
            {
                'place_id': 'ChIJ...',
                'description': 'Paris, France',
                'structured_formatting': {
                    'main_text': 'Paris',
                    'secondary_text': 'France'
                },
                'types': ['locality', 'political', 'geocode'],
                'matched_substrings': [...]
            }
        ]
    """
    if not is_enabled():
        return []

    cache_key = f"gp:ac:{query}:{types}:{components}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "input": query,
        "key": _get_api_key(),
        "language": language,
    }
    if types:
        params["types"] = types
    if components:
        params["components"] = components
    if session_token:
        params["sessiontoken"] = session_token
    if location_bias:
        params["location"] = f"{location_bias[0]},{location_bias[1]}"
        params["radius"] = 50000  # 50km bias radius

    try:
        resp = requests.get(PLACES_AUTOCOMPLETE_URL, params=params, timeout=3)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            logger.warning("Places Autocomplete status=%s for query=%s", data.get("status"), query)
            return []

        predictions = data.get("predictions", [])
        cache.set(cache_key, predictions, AUTOCOMPLETE_CACHE_TTL)
        return predictions

    except requests.RequestException as e:
        logger.error("Places Autocomplete request failed: %s", e)
        return []


def place_details(place_id: str, session_token: str = "") -> Optional[dict]:
    """
    Get place details (lat/lng, address components, name) from place_id.

    Returns:
        {
            'place_id': 'ChIJ...',
            'name': 'Eiffel Tower',
            'formatted_address': 'Champ de Mars, 5 Av. Anatole France, 75007 Paris, France',
            'latitude': 48.8583701,
            'longitude': 2.2944813,
            'types': ['tourist_attraction', 'point_of_interest'],
            'address_components': [...],
            'city': 'Paris',
            'state': 'Île-de-France',
            'country': 'France',
            'country_code': 'FR',
            'postal_code': '75007',
        }
    """
    if not is_enabled() or not place_id:
        return None

    cache_key = f"gp:pd:{place_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "place_id": place_id,
        "key": _get_api_key(),
        "fields": "place_id,name,formatted_address,geometry,types,address_components",
    }
    if session_token:
        params["sessiontoken"] = session_token

    try:
        resp = requests.get(PLACE_DETAILS_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            logger.warning("Place Details status=%s for place_id=%s", data.get("status"), place_id)
            return None

        result = data["result"]
        geo = result.get("geometry", {}).get("location", {})

        # Parse address components
        components = {}
        for comp in result.get("address_components", []):
            types = comp.get("types", [])
            if "locality" in types:
                components["city"] = comp["long_name"]
            elif "administrative_area_level_2" in types:
                components["district"] = comp["long_name"]
            elif "administrative_area_level_1" in types:
                components["state"] = comp["long_name"]
            elif "country" in types:
                components["country"] = comp["long_name"]
                components["country_code"] = comp["short_name"]
            elif "postal_code" in types:
                components["postal_code"] = comp["long_name"]

        parsed = {
            "place_id": result.get("place_id", place_id),
            "name": result.get("name", ""),
            "formatted_address": result.get("formatted_address", ""),
            "latitude": geo.get("lat"),
            "longitude": geo.get("lng"),
            "types": result.get("types", []),
            **components,
        }

        cache.set(cache_key, parsed, PLACE_DETAILS_CACHE_TTL)
        return parsed

    except requests.RequestException as e:
        logger.error("Place Details request failed: %s", e)
        return None


def geocode(address: str) -> Optional[dict]:
    """
    Convert address string to lat/lng coordinates.

    Returns:
        {
            'latitude': float,
            'longitude': float,
            'formatted_address': str,
            'place_id': str,
            'types': list,
            'city': str,
            'state': str,
            'country': str,
            'country_code': str,
        }
    """
    if not is_enabled() or not address:
        return None

    cache_key = f"gp:gc:{address.lower().strip()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "address": address,
        "key": _get_api_key(),
    }

    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            logger.warning("Geocode status=%s for address=%s", data.get("status"), address)
            return None

        result = data["results"][0]
        geo = result.get("geometry", {}).get("location", {})

        components = {}
        for comp in result.get("address_components", []):
            types = comp.get("types", [])
            if "locality" in types:
                components["city"] = comp["long_name"]
            elif "administrative_area_level_1" in types:
                components["state"] = comp["long_name"]
            elif "country" in types:
                components["country"] = comp["long_name"]
                components["country_code"] = comp["short_name"]

        parsed = {
            "latitude": geo.get("lat"),
            "longitude": geo.get("lng"),
            "formatted_address": result.get("formatted_address", ""),
            "place_id": result.get("place_id", ""),
            "types": result.get("types", []),
            **components,
        }

        cache.set(cache_key, parsed, GEOCODE_CACHE_TTL)
        return parsed

    except requests.RequestException as e:
        logger.error("Geocode request failed: %s", e)
        return None


def reverse_geocode(lat: float, lng: float) -> Optional[dict]:
    """
    Convert lat/lng to address/city/country.

    Returns same structure as geocode().
    """
    if not is_enabled():
        return None

    cache_key = f"gp:rgc:{lat:.6f},{lng:.6f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "latlng": f"{lat},{lng}",
        "key": _get_api_key(),
    }

    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None

        result = data["results"][0]
        geo = result.get("geometry", {}).get("location", {})

        components = {}
        for comp in result.get("address_components", []):
            types = comp.get("types", [])
            if "locality" in types:
                components["city"] = comp["long_name"]
            elif "administrative_area_level_1" in types:
                components["state"] = comp["long_name"]
            elif "country" in types:
                components["country"] = comp["long_name"]
                components["country_code"] = comp["short_name"]

        parsed = {
            "latitude": geo.get("lat", lat),
            "longitude": geo.get("lng", lng),
            "formatted_address": result.get("formatted_address", ""),
            "place_id": result.get("place_id", ""),
            "types": result.get("types", []),
            **components,
        }

        cache.set(cache_key, parsed, GEOCODE_CACHE_TTL)
        return parsed

    except requests.RequestException as e:
        logger.error("Reverse geocode request failed: %s", e)
        return None


def normalize_to_location_type(types: list[str]) -> str:
    """
    Map Google Place types to internal location categories.

    Returns: 'city' | 'airport' | 'landmark' | 'neighborhood' | 'region'
    """
    type_set = set(types) if types else set()

    if "airport" in type_set:
        return "airport"
    if type_set & {"tourist_attraction", "point_of_interest", "museum", "church",
                   "hindu_temple", "mosque", "synagogue", "stadium", "amusement_park",
                   "park", "zoo", "aquarium"}:
        return "landmark"
    if type_set & {"neighborhood", "sublocality", "sublocality_level_1"}:
        return "neighborhood"
    if type_set & {"locality", "postal_town"}:
        return "city"
    if type_set & {"administrative_area_level_1", "administrative_area_level_2",
                   "country"}:
        return "region"
    return "city"  # default
