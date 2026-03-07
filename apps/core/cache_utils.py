"""
Redis caching utilities for hotel search and other querysets.
Provides decorators and helper functions for cache management.
"""

import hashlib
import json
from functools import wraps
from django.apps import apps
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger('zygotrip')


def _safe_cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception as exc:
        logger.warning(f"Cache get failed for {key}: {exc}")
        return default


def _safe_cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as exc:
        logger.warning(f"Cache set failed for {key}: {exc}")
        return False


def _safe_cache_delete(key):
    try:
        cache.delete(key)
        return True
    except Exception as exc:
        logger.warning(f"Cache delete failed for {key}: {exc}")
        return False


def generate_cache_key(prefix, *args, **kwargs):
    """Generate a unique cache key from arguments"""
    key_parts = [prefix]
    
    # Add positional args
    for arg in args:
        if arg is not None:
            key_parts.append(str(arg))
    
    # Add keyword args (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}={v}")
    
    key_string = ":".join(key_parts)
    # Use hash for very long keys
    if len(key_string) > 200:
        return f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    return key_string


def cache_result(timeout=3600, key_prefix='cache', cache_none=False):
    """
    Decorator to cache function results in Redis.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
        cache_none: Whether to cache None results
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = generate_cache_key(key_prefix, *args, **kwargs)
            
            # Try to get from cache
            result = _safe_cache_get(cache_key)
            if result is not None or (result is None and cache_none):
                logger.debug(f"Cache hit: {cache_key}")
                return result
            
            # Call function and cache result
            result = func(*args, **kwargs)
            
            if result is not None or cache_none:
                _safe_cache_set(cache_key, result, timeout)
                logger.debug(f"Cache set: {cache_key} (ttl={timeout}s)")
            
            return result
        
        # Expose cache control methods
        wrapper.cache_key = lambda *args, **kwargs: generate_cache_key(
            key_prefix, *args, **kwargs
        )
        wrapper.invalidate = lambda *args, **kwargs: _safe_cache_delete(
            generate_cache_key(key_prefix, *args, **kwargs)
        )
        wrapper.clear = lambda: invalidate_pattern(f"{key_prefix}:*")
        
        return wrapper
    
    return decorator


def invalidate_pattern(pattern):
    """Invalidate all cache keys matching a pattern"""
    try:
        cache.delete_pattern(pattern)
        logger.debug(f"Invalidated cache pattern: {pattern}")
    except Exception as e:
        logger.warning(f"Error invalidating cache pattern {pattern}: {str(e)}")


def get_or_cache(cache_key, callable_func, timeout=3600):
    """Get value from cache or execute function and cache result"""
    result = _safe_cache_get(cache_key)
    if result is not None:
        return result
    
    result = callable_func()
    if result is not None:
        _safe_cache_set(cache_key, result, timeout)
    
    return result


class CachedQuerySet:
    """
    Wrapper for QuerySet caching with automatic invalidation.
    Useful for frequently accessed database queries.
    """
    
    def __init__(self, queryset, cache_key, timeout=3600):
        self.queryset = queryset
        self.cache_key = cache_key
        self.timeout = timeout
    
    def get(self):
        """Get cached queryset or fetch from DB"""
        result = _safe_cache_get(self.cache_key)
        if result is not None:
            logger.debug(f"Cache hit: {self.cache_key}")
            return result
        
        # Fetch from database
        result = list(self.queryset)
        _safe_cache_set(self.cache_key, result, self.timeout)
        logger.debug(f"Cache set: {self.cache_key}")
        
        return result
    
    def invalidate(self):
        """Invalidate cache"""
        _safe_cache_delete(self.cache_key)
        logger.debug(f"Cache invalidated: {self.cache_key}")


# =============================================
# HOTEL SEARCH CACHING HELPER
# =============================================

def get_hotel_search_cache_key(filters):
    """Generate cache key for hotel search results"""
    key_parts = ['hotel_search']
    
    # Add relevant filters
    for key in ['location', 'check_in', 'check_out', 'guests', 'price_range']:
        if key in filters and filters[key]:
            key_parts.append(f"{key}={filters[key]}")
    
    # Sort for consistency
    key_parts.sort()
    return ":".join(key_parts)


@cache_result(timeout=3600, key_prefix='hotel_search')
def cache_hotel_search(location=None, check_in=None, check_out=None, **kwargs):
    """
    Placeholder for hotel search caching.
    Actual query execution happens in views.
    """
    return {
        'location': location,
        'check_in': check_in,
        'check_out': check_out,
        'cached': True,
    }


def invalidate_hotel_search_cache():
    """Invalidate all hotel search cache entries"""
    invalidate_pattern('hotel_search:*')


# =============================================
# INVENTORY CACHING HELPERS
# =============================================

def cache_operator_inventory(operator_id, resource_type):
    """Cache operator inventory (buses, cabs, packages)"""
    cache_key = f"inventory:{resource_type}:{operator_id}"
    
    try:
        if resource_type == 'bus':
            Bus = apps.get_model('buses', 'Bus')
            inventory = Bus.objects.filter(
                operator_id=operator_id,
                is_active=True
            ).values('id', 'bus_number', 'total_seats', 'available_seats')
        
        elif resource_type == 'cab':
            Cab = apps.get_model('cabs', 'Cab')
            inventory = Cab.objects.filter(
                owner_id=operator_id,
                is_active=True
            ).values('id', 'registration_number', 'base_fare', 'rate_per_km')
        
        elif resource_type == 'package':
            Package = apps.get_model('packages', 'Package')
            inventory = Package.objects.filter(
                provider_id=operator_id,
                is_active=True
            ).values('id', 'name', 'price', 'duration_days')
        
        else:
            return None
        
        inventory_list = list(inventory)
        _safe_cache_set(cache_key, inventory_list, 300)  # 5 min TTL
        
        return inventory_list
    
    except Exception as e:
        logger.error(f"Error caching {resource_type} inventory: {str(e)}")
        return None


def get_operator_inventory(operator_id, resource_type):
    """Get operator inventory from cache or database"""
    cache_key = f"inventory:{resource_type}:{operator_id}"
    
    # Try cache first
    inventory = _safe_cache_get(cache_key)
    if inventory is not None:
        logger.debug(f"Cache hit: {cache_key}")
        return inventory
    
    # Fall back to database and cache
    return cache_operator_inventory(operator_id, resource_type)


def invalidate_operator_inventory(operator_id, resource_type=None):
    """Invalidate operator inventory cache"""
    if resource_type:
        cache_key = f"inventory:{resource_type}:{operator_id}"
        _safe_cache_delete(cache_key)
    else:
        # Invalidate all resource types
        for rtype in ['bus', 'cab', 'package']:
            cache_key = f"inventory:{rtype}:{operator_id}"
            _safe_cache_delete(cache_key)
    
    logger.debug(f"Invalidated inventory cache for operator {operator_id}")