"""
Recommendation Engine — Content-Based + Collaborative Filtering.

Provides four recommendation strategies:
  1. Similar Hotels    — content-based (location, star, price band, amenities)
  2. Popular Hotels    — weighted popularity ranking
  3. Best Value        — price/rating Pareto front
  4. Personalized      — user history (collaborative filtering + affinity)

All heavy computation is cached in Redis with sensible TTLs.
"""
import hashlib
import json
import logging
import math
from collections import Counter, defaultdict
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, F, Q
from django.utils import timezone

logger = logging.getLogger('zygotrip.recommendations')


def _redis():
    """Lazy Redis client."""
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception:
        return None


# ============================================================================
# Recommendation Engine
# ============================================================================

class RecommendationEngine:
    """
    Production recommendation service.
    Keeps models decoupled — uses dynamic imports.
    """

    CACHE_PREFIX = 'reco'
    SIMILAR_TTL = 1800       # 30 min
    POPULAR_TTL = 3600       # 1 hr
    BEST_VALUE_TTL = 1800    # 30 min
    PERSONAL_TTL = 900       # 15 min

    # ----------------------------------------------------------------
    # 1. Similar Hotels
    # ----------------------------------------------------------------

    @classmethod
    def similar_hotels(cls, hotel_id, limit=8):
        """
        Content-based similarity: location proximity, star match,
        price band overlap, amenity Jaccard.
        """
        cache_key = f'{cls.CACHE_PREFIX}:similar:{hotel_id}:{limit}'
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        from apps.hotels.models import Property
        try:
            source = Property.objects.select_related().get(pk=hotel_id)
        except Property.DoesNotExist:
            return []

        candidates = Property.objects.filter(
            is_active=True,
            city=source.city,
        ).exclude(pk=hotel_id).select_related()[:200]

        scored = []
        source_amenities = set(cls._get_amenities(source))
        source_price = cls._avg_rate(source)

        for cand in candidates:
            score = cls._similarity_score(source, cand, source_amenities, source_price)
            scored.append((cand, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [cls._hotel_brief(h) for h, _ in scored[:limit]]
        cls._cache_set(cache_key, results, cls.SIMILAR_TTL)
        return results

    @classmethod
    def _similarity_score(cls, source, candidate, source_amenities, source_price):
        """
        Combined similarity:
          - Distance     30% (inverse haversine, max 25 km)
          - Star match   20% (1.0 if same, decay by difference)
          - Price band   25% (closeness within ±50%)
          - Amenities    25% (Jaccard index)
        """
        # Distance score (0-1, 1 = same location)
        dist = cls._haversine(
            getattr(source, 'latitude', 0) or 0,
            getattr(source, 'longitude', 0) or 0,
            getattr(candidate, 'latitude', 0) or 0,
            getattr(candidate, 'longitude', 0) or 0,
        )
        dist_score = max(0.0, 1.0 - dist / 25.0)

        # Star match score
        s_star = getattr(source, 'star_rating', 3) or 3
        c_star = getattr(candidate, 'star_rating', 3) or 3
        star_score = max(0.0, 1.0 - abs(s_star - c_star) / 4.0)

        # Price band score
        cand_price = cls._avg_rate(candidate)
        if source_price and cand_price:
            ratio = min(source_price, cand_price) / max(source_price, cand_price)
            price_score = ratio
        else:
            price_score = 0.5

        # Amenity Jaccard
        cand_amenities = set(cls._get_amenities(candidate))
        if source_amenities or cand_amenities:
            jaccard = len(source_amenities & cand_amenities) / max(
                len(source_amenities | cand_amenities), 1
            )
        else:
            jaccard = 0.5

        return (0.30 * dist_score
                + 0.20 * star_score
                + 0.25 * price_score
                + 0.25 * jaccard)

    # ----------------------------------------------------------------
    # 2. Popular Hotels
    # ----------------------------------------------------------------

    @classmethod
    def popular_hotels(cls, city=None, limit=12):
        """
        Popularity ranking:
          - bookings_last_30d  40%
          - views_last_7d      20%
          - rating              25%
          - review_count        15%
        """
        cache_key = f'{cls.CACHE_PREFIX}:popular:{city or "all"}:{limit}'
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        from apps.hotels.models import Property
        from apps.booking.models import Booking

        qs = Property.objects.filter(is_active=True)
        if city:
            qs = qs.filter(city__iexact=city)

        thirty_days_ago = timezone.now() - __import__('datetime').timedelta(days=30)

        # Booking counts
        booking_counts = dict(
            Booking.objects.filter(
                property__in=qs,
                created_at__gte=thirty_days_ago,
                status__in=['confirmed', 'completed'],
            ).values('property_id').annotate(
                cnt=Count('id')
            ).values_list('property_id', 'cnt')
        )

        max_bookings = max(booking_counts.values(), default=1) or 1

        scored = []
        for prop in qs[:500]:
            bookings = booking_counts.get(prop.pk, 0)
            rating = float(getattr(prop, 'rating', 0) or 0)
            review_count = getattr(prop, 'review_count', 0) or 0

            pop_score = (
                0.40 * (bookings / max_bookings)
                + 0.20 * min(1.0, (getattr(prop, 'view_count', 0) or 0) / 10000)
                + 0.25 * (rating / 5.0)
                + 0.15 * min(1.0, review_count / 100)
            )
            scored.append((prop, pop_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [cls._hotel_brief(h) for h, _ in scored[:limit]]
        cls._cache_set(cache_key, results, cls.POPULAR_TTL)
        return results

    # ----------------------------------------------------------------
    # 3. Best Value
    # ----------------------------------------------------------------

    @classmethod
    def best_value(cls, city=None, max_budget=None, limit=12):
        """
        Pareto-optimal on price/rating.
        Value = rating / normalized_price, boosted by review confidence.
        """
        cache_key = f'{cls.CACHE_PREFIX}:value:{city or "all"}:{max_budget}:{limit}'
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        from apps.hotels.models import Property

        qs = Property.objects.filter(is_active=True)
        if city:
            qs = qs.filter(city__iexact=city)

        properties = list(qs.select_related()[:500])
        if not properties:
            return []

        # Compute avg rate for each
        price_map = {}
        for p in properties:
            rate = cls._avg_rate(p)
            if rate and rate > 0:
                if max_budget and rate > max_budget:
                    continue
                price_map[p.pk] = (p, float(rate))

        if not price_map:
            return []

        max_price = max(v[1] for v in price_map.values()) or 1

        scored = []
        for pid, (prop, price) in price_map.items():
            rating = float(getattr(prop, 'rating', 0) or 0)
            review_count = getattr(prop, 'review_count', 0) or 0
            confidence = min(1.0, review_count / 50) if review_count else 0.5

            norm_price = price / max_price  # 0-1
            value_score = (rating / 5.0) / max(0.1, norm_price)
            value_score *= (0.7 + 0.3 * confidence)

            scored.append((prop, value_score, price))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [
            {**cls._hotel_brief(h), 'rate': price, 'value_score': round(score, 3)}
            for h, score, price in scored[:limit]
        ]
        cls._cache_set(cache_key, results, cls.BEST_VALUE_TTL)
        return results

    # ----------------------------------------------------------------
    # 4. Personalized Recommendations
    # ----------------------------------------------------------------

    @classmethod
    def personalized(cls, user_id, city=None, limit=12):
        """
        User-specific recommendations based on booking history:
          - City affinity
          - Star rating preference
          - Price range preference
          - Amenity preference
          - Highly rated un-booked hotels in preferred cities
        """
        cache_key = f'{cls.CACHE_PREFIX}:personal:{user_id}:{city or "all"}:{limit}'
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        profile = cls._build_user_profile(user_id)
        if not profile or not profile.get('cities'):
            # Cold start — fall back to popular
            return cls.popular_hotels(city=city, limit=limit)

        from apps.hotels.models import Property

        # Find hotels in user's preferred cities they haven't booked
        preferred_cities = [c for c, _ in profile['cities'][:5]]
        if city:
            preferred_cities = [city] + [c for c in preferred_cities if c != city]

        booked_ids = set(profile.get('booked_property_ids', []))
        qs = Property.objects.filter(
            is_active=True,
            city__in=preferred_cities,
        ).exclude(pk__in=booked_ids).select_related()[:300]

        avg_star = profile.get('avg_star', 3)
        avg_price = profile.get('avg_price', 3000)
        preferred_amenities = set(profile.get('top_amenities', []))

        scored = []
        for prop in qs:
            score = cls._personalization_score(
                prop, avg_star, avg_price, preferred_amenities, preferred_cities,
            )
            scored.append((prop, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [
            {**cls._hotel_brief(h), 'affinity_score': round(score, 3)}
            for h, score in scored[:limit]
        ]
        cls._cache_set(cache_key, results, cls.PERSONAL_TTL)
        return results

    @classmethod
    def _build_user_profile(cls, user_id):
        """Build user preference profile from booking history."""
        from apps.booking.models import Booking

        bookings = Booking.objects.filter(
            user_id=user_id,
            status__in=['confirmed', 'completed'],
        ).select_related('property')[:50]

        if not bookings.exists():
            return None

        cities = Counter()
        stars = []
        prices = []
        amenities = Counter()
        property_ids = []

        for b in bookings:
            prop = b.property
            if not prop:
                continue
            property_ids.append(prop.pk)
            if prop.city:
                cities[prop.city] += 1
            star = getattr(prop, 'star_rating', None)
            if star:
                stars.append(star)
            rate = cls._avg_rate(prop)
            if rate:
                prices.append(float(rate))
            for a in cls._get_amenities(prop):
                amenities[a] += 1

        return {
            'cities': cities.most_common(10),
            'avg_star': sum(stars) / len(stars) if stars else 3,
            'avg_price': sum(prices) / len(prices) if prices else 3000,
            'top_amenities': [a for a, _ in amenities.most_common(10)],
            'booked_property_ids': property_ids,
        }

    @classmethod
    def _personalization_score(cls, prop, avg_star, avg_price,
                               preferred_amenities, preferred_cities):
        """Score a property for a specific user profile."""
        rating = float(getattr(prop, 'rating', 0) or 0)
        star = getattr(prop, 'star_rating', 3) or 3
        rate = cls._avg_rate(prop) or avg_price

        # Star preference (0-1)
        star_match = max(0.0, 1.0 - abs(star - avg_star) / 4.0)

        # Price preference (0-1)
        if avg_price:
            price_ratio = min(rate, avg_price) / max(rate, avg_price)
        else:
            price_ratio = 0.5

        # City preference (0-1)
        city = getattr(prop, 'city', '')
        city_idx = None
        for i, c in enumerate(preferred_cities):
            if c.lower() == (city or '').lower():
                city_idx = i
                break
        city_score = 1.0 / (1 + city_idx) if city_idx is not None else 0.2

        # Amenity overlap
        prop_amenities = set(cls._get_amenities(prop))
        if preferred_amenities or prop_amenities:
            amenity_score = len(preferred_amenities & prop_amenities) / max(
                len(preferred_amenities | prop_amenities), 1
            )
        else:
            amenity_score = 0.5

        # Quality boost
        quality = rating / 5.0

        return (
            0.20 * star_match
            + 0.20 * price_ratio
            + 0.25 * city_score
            + 0.15 * amenity_score
            + 0.20 * quality
        )

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Distance in km between two lat/lng pairs."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1))
             * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _get_amenities(prop):
        """Extract amenity names from a property."""
        try:
            return list(
                prop.amenities.values_list('name', flat=True)
            ) if hasattr(prop, 'amenities') else []
        except Exception:
            return []

    @staticmethod
    def _avg_rate(prop):
        """Get average nightly rate for a property."""
        try:
            from apps.hotels.models import RoomType
            agg = RoomType.objects.filter(
                property=prop, is_active=True,
            ).aggregate(avg=Avg('base_rate'))
            return float(agg['avg']) if agg['avg'] else None
        except Exception:
            return None

    @staticmethod
    def _hotel_brief(prop):
        """Compact hotel dict for API responses."""
        return {
            'id': prop.pk,
            'name': getattr(prop, 'name', ''),
            'city': getattr(prop, 'city', ''),
            'star_rating': getattr(prop, 'star_rating', None),
            'rating': float(getattr(prop, 'rating', 0) or 0),
            'review_count': getattr(prop, 'review_count', 0) or 0,
            'image': getattr(prop, 'thumbnail_url', '') or '',
        }

    @classmethod
    def _cache_get(cls, key):
        r = _redis()
        if not r:
            return None
        try:
            val = r.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    @classmethod
    def _cache_set(cls, key, value, ttl):
        r = _redis()
        if not r:
            return
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            pass

    @classmethod
    def invalidate_hotel(cls, hotel_id):
        """Invalidate all recommendation caches for a hotel."""
        r = _redis()
        if not r:
            return
        try:
            for pattern in [f'{cls.CACHE_PREFIX}:similar:{hotel_id}:*',
                            f'{cls.CACHE_PREFIX}:popular:*',
                            f'{cls.CACHE_PREFIX}:value:*']:
                for key in r.scan_iter(pattern, count=100):
                    r.delete(key)
        except Exception:
            pass
