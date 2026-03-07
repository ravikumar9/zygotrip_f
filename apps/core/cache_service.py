"""
Redis caching layer for OTA-grade performance.

Phase 11: Cache hot paths — property detail, search results,
rating aggregates, and pricing calculations.

TTL strategy:
  - Property detail: 5 min (moderate churn)
  - Search results: 2 min (high churn)
  - Rating aggregates: 10 min (low churn)
  - Pricing quote: 1 min (price-sensitive)
  - Inventory availability: 30 sec (critical accuracy)
"""
import json
import hashlib
import logging
from functools import wraps

from django.core.cache import cache

logger = logging.getLogger('zygotrip.cache')

# TTL constants (seconds)
TTL_PROPERTY_DETAIL = 300    # 5 min
TTL_SEARCH_RESULTS = 120     # 2 min
TTL_RATING_AGGREGATE = 600   # 10 min
TTL_PRICING_QUOTE = 60       # 1 min
TTL_INVENTORY = 30           # 30 sec


def _make_key(prefix, *args, **kwargs):
    """Generate deterministic cache key from args."""
    raw = f"{prefix}:{args}:{sorted(kwargs.items())}"
    return f"zygo:{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"


# ============================================================================
# PROPERTY DETAIL CACHE
# ============================================================================

def get_cached_property(property_uuid):
    """Get property detail from cache."""
    key = f"zygo:prop:{property_uuid}"
    return cache.get(key)


def set_cached_property(property_uuid, data):
    """Cache property detail."""
    key = f"zygo:prop:{property_uuid}"
    cache.set(key, data, TTL_PROPERTY_DETAIL)


def invalidate_property_cache(property_uuid):
    """Invalidate property detail cache on update."""
    key = f"zygo:prop:{property_uuid}"
    cache.delete(key)
    # Also invalidate search index for this property
    cache.delete(f"zygo:search_prop:{property_uuid}")


# ============================================================================
# SEARCH RESULTS CACHE
# ============================================================================

def get_cached_search(city_id, filters_hash):
    """Get search results from cache."""
    key = f"zygo:search:{city_id}:{filters_hash}"
    return cache.get(key)


def set_cached_search(city_id, filters_hash, data):
    """Cache search results."""
    key = f"zygo:search:{city_id}:{filters_hash}"
    cache.set(key, data, TTL_SEARCH_RESULTS)


def make_search_hash(**filters):
    """Create deterministic hash from search filters."""
    raw = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


# ============================================================================
# RATING AGGREGATE CACHE
# ============================================================================

def get_cached_rating(property_id):
    """Get rating aggregate from cache."""
    key = f"zygo:rating:{property_id}"
    return cache.get(key)


def set_cached_rating(property_id, data):
    """Cache rating aggregate."""
    key = f"zygo:rating:{property_id}"
    cache.set(key, data, TTL_RATING_AGGREGATE)


def invalidate_rating_cache(property_id):
    """Invalidate on new review approval."""
    cache.delete(f"zygo:rating:{property_id}")
    invalidate_property_cache(property_id)


# ============================================================================
# PRICING QUOTE CACHE
# ============================================================================

def get_cached_pricing(room_type_id, check_in, check_out, rooms):
    """Get pricing quote from cache."""
    key = _make_key('price', room_type_id, str(check_in), str(check_out), rooms)
    return cache.get(key)


def set_cached_pricing(room_type_id, check_in, check_out, rooms, data):
    """Cache pricing quote."""
    key = _make_key('price', room_type_id, str(check_in), str(check_out), rooms)
    cache.set(key, data, TTL_PRICING_QUOTE)


# ============================================================================
# INVENTORY AVAILABILITY CACHE
# ============================================================================

def get_cached_availability(room_type_id, date):
    """Get inventory availability from cache."""
    key = f"zygo:inv:{room_type_id}:{date}"
    return cache.get(key)


def set_cached_availability(room_type_id, date, available_rooms):
    """Cache inventory availability (short TTL for accuracy)."""
    key = f"zygo:inv:{room_type_id}:{date}"
    cache.set(key, available_rooms, TTL_INVENTORY)


def invalidate_inventory_cache(room_type_id, date):
    """Invalidate on booking/hold/release."""
    cache.delete(f"zygo:inv:{room_type_id}:{date}")


# ============================================================================
# DECORATOR: Cache any function result
# ============================================================================

def cached(prefix, ttl=120):
    """
    Decorator to cache function results in Redis.

    Usage:
        @cached('my_func', ttl=300)
        def expensive_query(param1, param2):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(prefix, *args, **kwargs)
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        wrapper.cache_clear = lambda *a, **kw: cache.delete(_make_key(prefix, *a, **kw))
        return wrapper
    return decorator
