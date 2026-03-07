"""Cache manager for search, pricing, and inventory payloads.

Redis-safe: all operations catch exceptions and fall back gracefully
so the system continues functioning if Redis is unavailable.

Cache tiers:
  search:*         — 15 min  (search result pages)
  autocomplete:*   — 15 min  (typeahead suggestions)
  filters          — 30 min  (filter aggregations)
  price:*          — 5 min   (price calculations)
  availability:*   — 2 min   (inventory availability)
"""

import hashlib
import json
import logging
from django.core.cache import cache

logger = logging.getLogger('zygotrip.search.cache')

# TTL constants (seconds)
TTL_SEARCH = 900           # 15 min
TTL_AUTOCOMPLETE = 900     # 15 min
TTL_FILTERS = 1800         # 30 min
TTL_PRICE = 300            # 5 min  — balance freshness vs DB load
TTL_AVAILABILITY = 120     # 2 min  — short to avoid stale inventory


class CacheManager:
    """Cache helper for search engine payloads. Redis-failure-safe."""

    def __init__(self, prefix: str = "search"):
        self.prefix = prefix

    def _key(self, suffix: str) -> str:
        return f"{self.prefix}:{suffix}"

    def get(self, key):
        try:
            return cache.get(self._key(key))
        except Exception:
            logger.warning("Redis unavailable for cache.get(%s), returning None", key)
            return None

    def set(self, key, value, ttl=None):
        try:
            cache.set(self._key(key), value, ttl)
        except Exception:
            logger.warning("Redis unavailable for cache.set(%s), skipping", key)

    def delete(self, key):
        try:
            cache.delete(self._key(key))
        except Exception:
            logger.warning("Redis unavailable for cache.delete(%s), skipping", key)

    def clear(self):
        # No global clear to avoid nuking unrelated cache entries.
        return None

    # ── Search caching ───────────────────────────────────────────────────
    def get_search_results(self, query, filters=None):
        key = self._search_key(query, filters)
        return self.get(key)

    def set_search_results(self, query, payload, filters=None, ttl=TTL_SEARCH):
        key = self._search_key(query, filters)
        self.set(key, payload, ttl)

    def get_autocomplete_results(self, query):
        return self.get(f"autocomplete:{query.lower()}")

    def set_autocomplete_results(self, query, payload, ttl=TTL_AUTOCOMPLETE):
        self.set(f"autocomplete:{query.lower()}", payload, ttl)

    def get_filters(self):
        return self.get("filters")

    def set_filters(self, payload, ttl=TTL_FILTERS):
        self.set("filters", payload, ttl)

    # ── Pricing cache ────────────────────────────────────────────────────
    def get_price(self, room_type_id, nights, rooms=1, meal_plan_code='',
                  checkin_date=None, promo_discount=0):
        key = self._price_key(room_type_id, nights, rooms, meal_plan_code,
                              checkin_date, promo_discount)
        return self.get(key)

    def set_price(self, room_type_id, nights, rooms, meal_plan_code,
                  checkin_date, payload, ttl=TTL_PRICE, promo_discount=0):
        key = self._price_key(room_type_id, nights, rooms, meal_plan_code,
                              checkin_date, promo_discount)
        self.set(key, payload, ttl)

    def invalidate_price(self, room_type_id):
        """Invalidate cached prices for a room type.
        Uses django-redis delete_pattern if available, otherwise TTL expiry."""
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            prefix = self._key(f'rate:{room_type_id}:')
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = conn.scan(cursor, match=f'{prefix}*', count=100)
                if keys:
                    conn.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            if deleted:
                logger.info('Invalidated %d rate cache keys for room_type=%s', deleted, room_type_id)
        except Exception:
            # Fallback: TTL expiry handles it within 5 minutes
            logger.debug('Rate cache pattern delete unavailable for room_type=%s, relying on TTL', room_type_id)

    # ── Inventory / Availability cache ───────────────────────────────────
    def get_availability(self, room_type_id, check_in, check_out, quantity):
        key = self._availability_key(room_type_id, check_in, check_out, quantity)
        return self.get(key)

    def set_availability(self, room_type_id, check_in, check_out, quantity,
                         payload, ttl=TTL_AVAILABILITY):
        key = self._availability_key(room_type_id, check_in, check_out, quantity)
        self.set(key, payload, ttl)

    def invalidate_availability(self, room_type_id):
        """Invalidate cached availability (called on hold/booking/release)."""
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            prefix = self._key(f'avail:{room_type_id}:')
            cursor = 0
            while True:
                cursor, keys = conn.scan(cursor, match=f'{prefix}*', count=100)
                if keys:
                    conn.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            self.delete(f"avail:{room_type_id}:*")

    # ── Key builders ─────────────────────────────────────────────────────
    @staticmethod
    def _search_key(query, filters=None):
        """
        Build structured search cache key.
        Format: search:{city}:{checkin}:{checkout}:{guests}:{filter_hash}
        Falls back to search:{query}:{filter_hash} if structured params missing.
        """
        if filters:
            city = filters.get('city', query).lower().replace(' ', '_')
            checkin = filters.get('check_in', filters.get('checkin', 'any'))
            checkout = filters.get('check_out', filters.get('checkout', 'any'))
            guests = filters.get('guests', filters.get('adults', 'any'))
            # Hash remaining filters for uniqueness
            extra = {k: v for k, v in sorted(filters.items())
                     if k not in ('city', 'check_in', 'checkin', 'check_out',
                                  'checkout', 'guests', 'adults')}
            if extra:
                normalized = []
                for key, value in sorted(extra.items()):
                    if isinstance(value, list):
                        normalized.append((key, tuple(value)))
                    else:
                        normalized.append((key, value))
                filter_hash = hashlib.md5(
                    json.dumps(normalized, sort_keys=True, default=str).encode()
                ).hexdigest()[:8]
            else:
                filter_hash = 'all'
            return f"search:{city}:{checkin}:{checkout}:{guests}:{filter_hash}"
        return f"search:{query.lower()}"

    def invalidate_city_cache(self, city: str):
        """Invalidate all cached search results for a city via TTL expiry.
        Django's cache backend doesn't support pattern deletion, so we rely on
        short TTLs (15 min). This method is a hook for Redis-native backends."""
        # If we ever switch to django-redis, use: cache.delete_pattern(f"*:search:{city}:*")
        logger.info("Cache invalidation requested for city=%s (relying on TTL expiry)", city)

    @staticmethod
    def _price_key(room_type_id, nights, rooms, meal_plan_code, checkin_date, promo_discount=0):
        """Build rate cache key in structured format: rate:{hotel}:{room_type}:{date}
        Falls back to hash for composite lookups with meal plans / promos."""
        date_str = str(checkin_date) if checkin_date else 'any'
        if not meal_plan_code and promo_discount == 0 and nights == 1 and rooms == 1:
            # Clean single-night lookup: use structured key
            return f"rate:{room_type_id}:{date_str}"
        # Composite key: hash for uniqueness
        raw = f"{room_type_id}:{nights}:{rooms}:{meal_plan_code}:{date_str}:{promo_discount}"
        return f"rate:{room_type_id}:{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    @staticmethod
    def _availability_key(room_type_id, check_in, check_out, quantity):
        raw = f"{room_type_id}:{check_in}:{check_out}:{quantity}"
        return f"avail:{hashlib.md5(raw.encode()).hexdigest()[:16]}"


# Module-level singleton — importable by pricing/inventory services
price_cache = CacheManager(prefix='zygo')
availability_cache = CacheManager(prefix='zygo')


# ============================================================================
# CACHE WARMING — Popular cities pre-computation
# ============================================================================

POPULAR_CITIES = [
    'Mumbai', 'Delhi', 'Bangalore', 'Goa', 'Jaipur',
    'Manali', 'Shimla', 'Ooty', 'Munnar', 'Udaipur',
    'Rishikesh', 'Coorg', 'Lonavala', 'Darjeeling', 'Varanasi',
    'Kolkata', 'Chennai', 'Hyderabad', 'Pune', 'Kochi',
]


def warm_search_cache(cities=None):
    """
    Pre-warm search cache for popular cities.
    Runs default searches for next 30 days from each popular city.
    Called by Celery task or management command.
    """
    from datetime import date, timedelta

    cities = cities or POPULAR_CITIES
    warmed = 0

    try:
        from apps.search.models import PropertySearchIndex
        from django.db.models import Count

        for city_name in cities:
            # Warm the basic city search result
            results = list(
                PropertySearchIndex.objects.filter(
                    city_name__iexact=city_name,
                    has_availability=True,
                ).order_by('-popularity_score')[:50].values(
                    'property_id', 'property_name', 'slug', 'price_min',
                    'rating', 'featured_image_url', 'city_name',
                    'has_free_cancellation', 'review_count',
                )
            )

            if results:
                cache_key = f"search:{city_name.lower()}"
                price_cache.set(cache_key, results, TTL_SEARCH)
                warmed += 1

        logger.info('Cache warming complete: %d cities warmed', warmed)
    except Exception as exc:
        logger.error('Cache warming failed: %s', exc)

    return warmed


def warm_rate_cache_bulk(property_id=None, days_ahead=30):
    """
    Pre-compute and cache rates for high-demand hotels.
    Generates rate:{hotel_id}:{room_type}:{date} cache entries.

    Args:
        property_id: Optional — warm for specific property, else top 50 by popularity
        days_ahead: Number of days into the future to warm
    """
    from datetime import date, timedelta

    warmed = 0

    try:
        from apps.search.models import PropertySearchIndex
        from apps.rooms.models import RoomType

        if property_id:
            property_ids = [property_id]
        else:
            property_ids = list(
                PropertySearchIndex.objects.filter(
                    has_availability=True,
                ).order_by('-popularity_score')[:50].values_list('property_id', flat=True)
            )

        today = date.today()
        for pid in property_ids:
            room_types = RoomType.objects.filter(
                property_id=pid, is_active=True,
            ).values_list('id', 'base_price', flat=False)

            for rt_id, base_price in room_types:
                for day_offset in range(days_ahead):
                    target_date = today + timedelta(days=day_offset)
                    rate_key = f"rate:{pid}:{rt_id}:{target_date}"

                    # Check if already cached
                    if price_cache.get(rate_key) is not None:
                        continue

                    # Build rate data
                    try:
                        from apps.inventory.models import InventoryCalendar
                        cal = InventoryCalendar.objects.filter(
                            room_type_id=rt_id, date=target_date,
                        ).first()

                        rate = float(cal.rate_override) if cal and cal.rate_override else float(base_price)
                        rate_data = {
                            'base_price': rate,
                            'room_type_id': rt_id,
                            'property_id': pid,
                            'date': str(target_date),
                            'available': cal.available_rooms if cal else 0,
                        }
                        price_cache.set(rate_key, rate_data, TTL_PRICE * 6)  # 30 min for pre-warmed
                        warmed += 1
                    except Exception:
                        pass

        logger.info('Rate cache warming complete: %d entries warmed', warmed)
    except Exception as exc:
        logger.error('Rate cache warming failed: %s', exc)

    return warmed

