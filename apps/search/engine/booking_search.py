"""
Step 5 & 8 — Booking.com Style Search Architecture + Availability Cache.

Uses the denormalized PropertySearchIndex for <150ms queries.
Incorporates geo distance, availability cache, quality signals,
and faceted filter counts.
"""
import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.core.cache import cache as redis_cache
from django.db.models import Q, F, Value, FloatField, ExpressionWrapper
from django.db.models.functions import Radians, Sin, Cos, ACos

logger = logging.getLogger('zygotrip.search.booking')

# -------------------------------------------------------------------
# AVAILABILITY CACHE (Step 8): 5-min Redis TTL
# -------------------------------------------------------------------

_AVAIL_CACHE_TTL = 300  # 5 minutes


def _avail_key(property_id: int, checkin: date, checkout: date) -> str:
    return f'avail:{property_id}:{checkin}:{checkout}'


def get_cached_availability(property_id: int, checkin: date, checkout: date):
    """Read availability from Redis cache."""
    return redis_cache.get(_avail_key(property_id, checkin, checkout))


def set_cached_availability(property_id: int, checkin: date, checkout: date, data: dict):
    """Store availability in Redis cache."""
    redis_cache.set(_avail_key(property_id, checkin, checkout), data, _AVAIL_CACHE_TTL)


def invalidate_availability(property_id: int):
    """Invalidate all cached availability for a property (on booking/cancellation)."""
    # Pattern delete not universally supported; delete known recent dates
    today = date.today()
    keys = [
        _avail_key(property_id, today + timedelta(days=i), today + timedelta(days=i + d))
        for i in range(60)
        for d in (1, 2, 3, 5, 7)
    ]
    redis_cache.delete_many(keys)


# -------------------------------------------------------------------
# BOOKING.COM FAST SEARCH (Step 5)
# -------------------------------------------------------------------

class BookingSearchEngine:
    """
    Production Booking.com-style search on the denormalized
    PropertySearchIndex.  Single-table scan, zero JOINs.
    Target: <150 ms response.
    """

    # Search cache: 15-minute TTL
    SEARCH_CACHE_TTL = 900

    # -------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------

    def search(
        self,
        *,
        city: str | None = None,
        city_id: int | None = None,
        query: str | None = None,
        checkin: date | None = None,
        checkout: date | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        star_categories: list[int] | None = None,
        amenities: list[str] | None = None,
        property_types: list[str] | None = None,
        free_cancellation: bool | None = None,
        pay_at_hotel: bool | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 25.0,
        sort: str = 'recommended',
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        start = time.time()

        from apps.search.models import PropertySearchIndex

        qs = PropertySearchIndex.objects.filter(has_availability=True)

        # ==== FILTERS ====
        if city_id:
            qs = qs.filter(city_id=city_id)
        elif city:
            qs = qs.filter(city_name__iexact=city)

        if query:
            qs = qs.filter(
                Q(property_name__icontains=query)
                | Q(city_name__icontains=query)
                | Q(locality_name__icontains=query)
                | Q(tags__contains=[query])
            )

        if min_price is not None:
            qs = qs.filter(price_min__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price_min__lte=max_price)

        if star_categories:
            qs = qs.filter(star_category__in=star_categories)

        if amenities:
            for a in amenities:
                qs = qs.filter(amenities__contains=[a])

        if property_types:
            qs = qs.filter(property_type__in=property_types)

        if free_cancellation is True:
            qs = qs.filter(has_free_cancellation=True)

        if pay_at_hotel is True:
            qs = qs.filter(pay_at_hotel=True)

        # ==== GEO (Step 9) ====
        if latitude is not None and longitude is not None:
            qs = self._apply_geo_filter(qs, latitude, longitude, radius_km)

        # ==== SORT ====
        qs = self._apply_sort(qs, sort)

        # ==== PAGINATION ====
        total = qs.count()
        offset = (page - 1) * page_size
        results = list(qs[offset: offset + page_size].values(
            'id', 'property_id', 'property_name', 'slug', 'property_type',
            'city_name', 'locality_name', 'latitude', 'longitude',
            'star_category', 'price_min', 'price_max',
            'rating', 'review_count', 'review_score',
            'popularity_score', 'is_trending',
            'has_free_cancellation', 'pay_at_hotel',
            'amenities', 'tags', 'featured_image_url',
            'has_availability',
        ))

        elapsed_ms = round((time.time() - start) * 1000, 2)
        logger.info("BookingSearch: %d results in %sms (sort=%s)", total, elapsed_ms, sort)

        return {
            'results': results,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': -(-total // page_size),  # ceiling division
            'query_time_ms': elapsed_ms,
            'sort': sort,
        }

    # -------------------------------------------------------------------
    # FACETED FILTER COUNTS
    # -------------------------------------------------------------------

    def get_facets(self, *, city: str | None = None, city_id: int | None = None) -> dict:
        """Return filter-chip counts for the current scope."""
        from apps.search.models import PropertySearchIndex
        from django.db.models import Count, Avg
        from collections import Counter

        qs = PropertySearchIndex.objects.filter(has_availability=True)
        if city_id:
            qs = qs.filter(city_id=city_id)
        elif city:
            qs = qs.filter(city_name__iexact=city)

        total = qs.count()

        star_counts = dict(
            qs.values_list('star_category')
            .annotate(c=Count('id'))
            .values_list('star_category', 'c')
        )

        price_buckets = {
            '0-2000': qs.filter(price_min__lte=2000).count(),
            '2000-5000': qs.filter(price_min__gt=2000, price_min__lte=5000).count(),
            '5000-10000': qs.filter(price_min__gt=5000, price_min__lte=10000).count(),
            '10000+': qs.filter(price_min__gt=10000).count(),
        }

        free_cancel = qs.filter(has_free_cancellation=True).count()
        pay_hotel = qs.filter(pay_at_hotel=True).count()

        # Top amenities
        amenity_counter: Counter = Counter()
        for row in qs.values_list('amenities', flat=True):
            if row:
                for a in row:
                    amenity_counter[a] += 1

        return {
            'total': total,
            'star_categories': star_counts,
            'price_buckets': price_buckets,
            'free_cancellation': free_cancel,
            'pay_at_hotel': pay_hotel,
            'top_amenities': amenity_counter.most_common(15),
        }

    # -------------------------------------------------------------------
    # PRICE CALENDAR (Step 10)
    # -------------------------------------------------------------------

    @staticmethod
    def price_calendar(property_id: int, start_date: date | None = None, days: int = 30) -> list[dict]:
        """
        30-day nightly price calendar for a property.
        Returns list of { date, price, available, rooms_left }.
        """
        from apps.rooms.models import RoomType, RoomInventory

        if start_date is None:
            from django.utils import timezone
            start_date = timezone.now().date()

        date_range = [start_date + timedelta(days=i) for i in range(days)]

        # Cheapest room type
        rt = RoomType.objects.filter(property_id=property_id).order_by('base_price').first()
        if not rt:
            return [{'date': str(d), 'price': None, 'available': False, 'rooms_left': 0} for d in date_range]

        inv_map = {}
        for inv in RoomInventory.objects.filter(room_type=rt, date__in=date_range, is_closed=False):
            inv_map[inv.date] = inv

        calendar = []
        for d in date_range:
            inv = inv_map.get(d)
            if inv:
                calendar.append({
                    'date': str(d),
                    'price': float(inv.price_override or rt.base_price),
                    'available': inv.available_rooms > 0,
                    'rooms_left': inv.available_rooms,
                })
            else:
                calendar.append({
                    'date': str(d),
                    'price': float(rt.base_price),
                    'available': True,
                    'rooms_left': rt.available_count,
                })
        return calendar

    # -------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------

    def _apply_sort(self, qs, sort: str):
        if sort == 'price_asc':
            return qs.order_by('price_min')
        elif sort == 'price_desc':
            return qs.order_by('-price_min')
        elif sort == 'rating':
            return qs.order_by('-rating', '-review_count')
        elif sort == 'newest':
            return qs.order_by('-created_at')
        elif sort == 'popularity':
            return qs.order_by('-popularity_score')
        else:
            # recommended: blend of rating, popularity, trending
            return qs.order_by('-is_trending', '-popularity_score', '-rating')

    @staticmethod
    def _apply_geo_filter(qs, lat: float, lng: float, radius_km: float):
        """
        Haversine-approximate geo filter (Step 9).
        Uses bounding box pre-filter + exact distance annotation.
        """
        # Bounding box (fast pre-filter)
        delta_lat = radius_km / 111.0
        delta_lng = radius_km / (111.0 * abs(Decimal(str(lat)).copy_abs().__float__()) * 0.01745)
        delta_lng = max(delta_lng, delta_lat)  # safety floor

        qs = qs.filter(
            latitude__gte=lat - delta_lat,
            latitude__lte=lat + delta_lat,
            longitude__gte=lng - delta_lng,
            longitude__lte=lng + delta_lng,
        )

        # Annotate with approximate distance (km)
        try:
            qs = qs.annotate(
                distance_km=ExpressionWrapper(
                    Value(6371.0) * ACos(
                        Cos(Radians(Value(lat))) * Cos(Radians(F('latitude')))
                        * Cos(Radians(F('longitude')) - Radians(Value(lng)))
                        + Sin(Radians(Value(lat))) * Sin(Radians(F('latitude')))
                    ),
                    output_field=FloatField(),
                )
            ).filter(distance_km__lte=radius_km).order_by('distance_km')
        except Exception:
            logger.exception("Haversine annotation failed, using bbox only")

        return qs


# Singleton
booking_search_engine = BookingSearchEngine()
