"""
Search Ranking v2 — OTA Production-Grade.

Implements the mandated scoring formula:
  score = review_score_weight
        + conversion_rate_weight
        + price_competitiveness
        + margin_weight
        + location_score
        + personalization

Wraps the existing EnhancedRankingEngine and adds:
  - margin_score (OTA commission optimization)
  - personalization (user history, device, time-of-day, past searches)
  - price competitiveness (vs. competitor rates)
  - Redis search cache with configurable TTL
"""
import hashlib
import json
import logging
import math
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('zygotrip.search.ranking_v2')

# Weight configuration — OTA-style multi-signal production formula
RANKING_V2_WEIGHTS = {
    'review_score': 0.15,
    'conversion_rate': 0.12,
    'price_competitiveness': 0.18,
    'margin': 0.07,
    'booking_velocity': 0.10,
    'distance_relevance': 0.10,
    'location': 0.08,
    'personalization': 0.10,
    'cancellation_rate': 0.05,
    'availability_reliability': 0.05,
}


class SearchRankingV2:
    """
    Production search ranking with the 6-factor mandated formula.

    All factors return 0.0–1.0. Final score is weighted sum × 100.
    """

    def __init__(self, weights=None):
        cfg = getattr(settings, 'SEARCH_RANKING_V2_WEIGHTS', None) or {}
        w = {**RANKING_V2_WEIGHTS, **(cfg or {}), **(weights or {})}
        self.weights = w

    def rank(self, items, query=None, user_context=None):
        """
        Rank a list of PropertySearchIndex or Property objects.

        Args:
            items: queryset or list
            query: search query string
            user_context: dict with keys:
                user_id, user_lat, user_lng, device, past_cities,
                past_price_range, preferred_star, time_of_day, currency
        """
        items = list(items)
        if not items:
            return items

        user_context = user_context or {}

        # Pre-compute normalization values
        prices = [float(getattr(i, 'price_min', 0) or getattr(i, 'base_price', 0) or 0) for i in items]
        max_price = max(prices) if prices else 1
        min_price = min((p for p in prices if p > 0), default=1)

        # Pre-compute competitor data (batch)
        competitor_data = self._batch_competitor_lookup(items)

        # User history for personalization
        user_history = self._load_user_history(user_context.get('user_id'))

        for idx, item in enumerate(items):
            r = self._review_score(item)
            c = self._conversion_score(item)
            p = self._price_competitiveness(item, prices[idx], min_price, max_price, competitor_data)
            m = self._margin_score(item)
            v = self._booking_velocity_score(item)
            d = self._distance_relevance_score(item, user_context)
            l = self._location_score(item, user_context)
            per = self._personalization_score(item, user_context, user_history)
            canc = self._cancellation_score(item)
            avail = self._availability_reliability_score(item)

            score = (
                r * self.weights['review_score']
                + c * self.weights['conversion_rate']
                + p * self.weights['price_competitiveness']
                + m * self.weights['margin']
                + v * self.weights['booking_velocity']
                + d * self.weights['distance_relevance']
                + l * self.weights['location']
                + per * self.weights['personalization']
                + canc * self.weights['cancellation_rate']
                + avail * self.weights['availability_reliability']
            ) * 100

            item.ranking_score = round(score, 4)
            item._ranking_breakdown = {
                'review': round(r, 4),
                'conversion': round(c, 4),
                'price_comp': round(p, 4),
                'margin': round(m, 4),
                'booking_velocity': round(v, 4),
                'distance_relevance': round(d, 4),
                'location': round(l, 4),
                'personalization': round(per, 4),
                'cancellation': round(canc, 4),
                'availability': round(avail, 4),
            }

        items.sort(key=lambda x: x.ranking_score, reverse=True)
        return items

    # ── Component scorers ──────────────────────────────────────────────

    @staticmethod
    def _review_score(item):
        """
        Review score: combination of average rating + review volume.
        rating (0-5) normalized to 0-1, weighted with review count confidence.
        """
        rating = float(getattr(item, 'rating', 0) or 0)
        review_count = int(getattr(item, 'review_count', 0) or 0)
        review_score = float(getattr(item, 'review_score', 0) or 0)

        # Use review_score directly if available (0-10 scale)
        if review_score > 0:
            base = min(1.0, review_score / 10.0)
        else:
            base = rating / 5.0

        # Confidence: more reviews = more reliable score
        # Bayesian: blend with prior (0.5) using review count
        confidence = min(1.0, review_count / 50.0)  # 50+ reviews = full confidence
        return base * confidence + 0.5 * (1 - confidence)

    @staticmethod
    def _conversion_score(item):
        """
        Booking conversion rate: views → bookings ratio.
        Higher conversion signals better value/experience.
        """
        views = getattr(item, 'total_views', 0) or 0
        bookings = (
            getattr(item, 'total_bookings', 0)
            or getattr(item, 'booking_count', 0)
            or getattr(item, 'bookings_this_week', 0)
            or 0
        )

        if views >= 20:
            rate = bookings / views
            return min(1.0, rate / 0.12)  # 12% conversion = 1.0

        # Fallback: use bookings_today proxy
        today = getattr(item, 'bookings_today', 0) or 0
        if today >= 5:
            return 0.9
        elif today >= 2:
            return 0.6
        elif today >= 1:
            return 0.4
        return 0.3

    @staticmethod
    def _price_competitiveness(item, price, min_price, max_price, competitor_data):
        """
        Price competitiveness: how this property's price compares to
        competitors and the local market.
        """
        if max_price == min_price or price <= 0:
            return 0.5

        # Market position score: lower relative price = higher score
        market_position = 1.0 - ((price - min_price) / (max_price - min_price))

        # Competitor comparison
        prop_id = getattr(item, 'property_id', None) or getattr(item, 'id', None)
        comp = competitor_data.get(prop_id)
        if comp and comp.get('avg_competitor_price'):
            avg_comp = float(comp['avg_competitor_price'])
            if avg_comp > 0:
                ratio = price / avg_comp
                if ratio <= 0.90:
                    comp_score = 1.0  # 10%+ cheaper
                elif ratio <= 1.0:
                    comp_score = 0.8  # at parity
                elif ratio <= 1.05:
                    comp_score = 0.5  # within 5%
                else:
                    comp_score = max(0.1, 1.0 - (ratio - 1.0))
                return market_position * 0.5 + comp_score * 0.5
            
        return market_position

    @staticmethod
    def _margin_score(item):
        """
        Margin score: prioritize properties with higher OTA commission.
        commission_percentage field on Property model.
        Balanced with user value to avoid pure revenue optimization.
        """
        commission = float(getattr(item, 'commission_percentage', 15) or 15)
        # Normalize: 10% = 0.3, 15% = 0.6, 20%+ = 1.0
        return min(1.0, max(0.0, (commission - 5) / 15.0))

    @staticmethod
    def _booking_velocity_score(item):
        """
        Booking velocity signal for OTA-style popularity ranking.

        Uses recent bookings first, then same-day bookings, then total bookings
        as progressively weaker proxies.
        """
        recent = float(getattr(item, 'recent_bookings', 0) or 0)
        today = float(getattr(item, 'bookings_today', 0) or 0)
        total = float(getattr(item, 'total_bookings', 0) or 0)

        if recent > 0:
            return min(1.0, recent / 12.0)
        if today > 0:
            return min(0.95, today / 8.0)
        if total > 0:
            return min(0.75, total / 40.0)
        return 0.2

    @staticmethod
    def _distance_relevance_score(item, user_context):
        """
        Distance relevance as a direct ranking factor.

        If user coordinates are available, use haversine distance.
        Otherwise fall back to precomputed distance_km where present.
        """
        user_lat = user_context.get('user_lat')
        user_lng = user_context.get('user_lng')

        if user_lat is not None and user_lng is not None:
            lat = float(getattr(item, 'latitude', 0) or getattr(item, 'lat', 0) or 0)
            lng = float(getattr(item, 'longitude', 0) or getattr(item, 'lng', 0) or 0)
            if lat and lng:
                dist = _haversine(user_lat, user_lng, lat, lng)
                return max(0.0, min(1.0, math.exp(-dist / 8.0)))

        known_distance = float(getattr(item, 'distance_km', 0) or 0)
        if known_distance > 0:
            return max(0.0, min(1.0, 1.0 - (known_distance / 25.0)))

        return 0.5

    @staticmethod
    def _location_score(item, user_context):
        """
        Location score based on:
          1. Locality popularity
          2. City-centre distance proxy
        """
        score = 0.5  # default baseline

        # Boost popular localities
        locality_pop = float(getattr(item, 'locality_popularity', 0) or 0)
        if locality_pop > 0:
            score = score * 0.7 + min(1.0, locality_pop / 100.0) * 0.3

        distance_km = float(getattr(item, 'distance_km', 0) or 0)
        if distance_km > 0:
            center_proximity = max(0.0, min(1.0, 1.0 - (distance_km / 30.0)))
            score = score * 0.6 + center_proximity * 0.4

        return min(1.0, score)

    @staticmethod
    def _personalization_score(item, user_context, user_history):
        """
        Personalization based on:
          1. Past booking cities (repeat visitor boost)
          2. Past price range (match user's budget)
          3. Preferred star category
          4. Time-of-day (business vs. leisure)
          5. Device type (mobile users prefer different properties)
        """
        if not user_history:
            return 0.5  # no personalization data

        score = 0.5
        boosts = []

        # 1. City affinity: boost if user has booked in same city before
        city_id = getattr(item, 'city_id', None)
        if city_id and city_id in user_history.get('booked_cities', []):
            boosts.append(0.15)

        # 2. Price range match
        price = float(getattr(item, 'price_min', 0) or getattr(item, 'base_price', 0) or 0)
        avg_price = user_history.get('avg_booking_price', 0)
        if avg_price > 0 and price > 0:
            ratio = price / avg_price
            if 0.7 <= ratio <= 1.3:
                boosts.append(0.10)  # within ±30% of user's usual spend

        # 3. Star preference
        preferred_star = user_history.get('preferred_star')
        item_star = getattr(item, 'star_category', 0) or 0
        if preferred_star and item_star:
            if abs(int(item_star) - int(preferred_star)) <= 1:
                boosts.append(0.10)

        # 4. Past search cities
        past_cities = user_context.get('past_cities', [])
        if city_id and city_id in past_cities:
            boosts.append(0.05)

        # 5. Device preference
        device = user_context.get('device', 'desktop')
        if device == 'mobile':
            # Mobile users tend to prefer lower-priced, centrally located
            if price < avg_price * 1.1 if avg_price else 5000:
                boosts.append(0.05)

        score += sum(boosts)
        return min(1.0, score)

    # ── New signal scorers ─────────────────────────────────────────

    @staticmethod
    def _cancellation_score(item):
        """
        Cancellation rate signal: lower cancellation rate = higher score.
        Hotels with high clicks but low bookings (frequent cancellations)
        get ranking decrease. Inverse mapping: 0% cancel = 1.0, 50%+ = 0.0
        """
        rate = float(getattr(item, 'cancellation_rate', 0) or 0)
        # rate is 0-1 where 0 = no cancellations, 1 = 100% cancelled
        return max(0.0, min(1.0, 1.0 - (rate * 2.0)))

    @staticmethod
    def _availability_reliability_score(item):
        """
        Availability reliability: how often rooms are actually available
        when listed. Penalizes properties with frequent overbooking or
        inventory errors. 1.0 = perfectly reliable, 0.0 = always wrong.
        """
        reliability = float(getattr(item, 'availability_reliability', 1) or 1)
        return max(0.0, min(1.0, reliability))

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _batch_competitor_lookup(items):
        """Batch load competitor price data for all items."""
        data = {}
        try:
            from apps.pricing.models import CompetitorPrice
            from django.db.models import Avg

            prop_ids = [
                getattr(i, 'property_id', None) or getattr(i, 'id', None)
                for i in items
            ]
            prop_ids = [p for p in prop_ids if p]

            if not prop_ids:
                return data

            avg_prices = (
                CompetitorPrice.objects.filter(
                    property_id__in=prop_ids,
                    is_available=True,
                )
                .values('property_id')
                .annotate(avg_price=Avg('price_per_night'))
            )

            for row in avg_prices:
                data[row['property_id']] = {'avg_competitor_price': row['avg_price']}

        except Exception as exc:
            logger.debug('competitor batch lookup failed: %s', exc)

        return data

    @staticmethod
    def _load_user_history(user_id):
        """Load user booking/search history for personalization.

        Uses cached UserSearchProfile when available (fast path).
        Falls back to direct DB aggregation (slow path, first-time users).
        """
        if not user_id:
            return {}

        # Fast path: cached profile
        try:
            from apps.search.personalization import get_user_profile_for_ranking
            profile = get_user_profile_for_ranking(user_id)
            if profile:
                return profile
        except Exception:
            pass

        # Slow path: direct aggregation (fallback)
        try:
            from apps.booking.models import Booking
            from django.db.models import Avg

            bookings = Booking.objects.filter(
                user_id=user_id,
                status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
            ).select_related('property__city')

            if not bookings.exists():
                return {}

            cities = set()
            stars = []
            for b in bookings[:50]:
                if b.property and b.property.city_id:
                    cities.add(b.property.city_id)
                if b.property and b.property.star_category:
                    stars.append(int(b.property.star_category))

            avg_price = bookings.aggregate(avg=Avg('total_amount'))['avg']

            return {
                'booked_cities': list(cities),
                'avg_booking_price': float(avg_price or 0),
                'preferred_star': round(sum(stars) / len(stars)) if stars else None,
                'booking_count': bookings.count(),
            }
        except Exception:
            return {}


class SearchResultCache:
    """
    Redis-backed search result cache with demand-aware TTL.

    Keys:
      search_cache:{hash}  — full search results
      hotel_rate_cache:{hotel_id}:{date} — per-hotel rate
      availability_cache:{room_type}:{date_range} — availability

    TTL Strategy:
      High demand (>85% occupancy): 60s (prices change fast)
      Normal: 300s (5 min)
      Low demand (<50% occupancy): 900s (15 min, stable prices)
    """

    TTL_HIGH_DEMAND = 60
    TTL_NORMAL = 300
    TTL_LOW_DEMAND = 900
    TTL_RATE = 300
    TTL_AVAILABILITY = 120

    def __init__(self):
        self._redis = None

    def _client(self):
        if self._redis is None:
            try:
                import redis as _redis_lib
                url = getattr(settings, 'REDIS_URL', 'redis://127.0.0.1:6379/0')
                self._redis = _redis_lib.Redis.from_url(url, decode_responses=True)
            except Exception:
                self._redis = False
        return self._redis if self._redis is not False else None

    def _demand_ttl(self, city_id=None):
        """Determine TTL based on current demand level."""
        if not city_id:
            return self.TTL_NORMAL
        try:
            from apps.core.intelligence import DemandForecast
            from django.db.models import Avg
            from datetime import date

            avg_occ = DemandForecast.objects.filter(
                property__city_id=city_id,
                date=date.today(),
            ).aggregate(avg=Avg('predicted_occupancy'))['avg']

            if avg_occ and avg_occ >= 0.85:
                return self.TTL_HIGH_DEMAND
            elif avg_occ and avg_occ <= 0.50:
                return self.TTL_LOW_DEMAND
        except Exception:
            pass
        return self.TTL_NORMAL

    def get_search_results(self, query_hash):
        """Get cached search results."""
        client = self._client()
        if not client:
            return None
        try:
            data = client.get(f"search_cache:{query_hash}")
            return json.loads(data) if data else None
        except Exception:
            return None

    def set_search_results(self, query_hash, results, city_id=None):
        """Cache search results with demand-aware TTL."""
        client = self._client()
        if not client:
            return
        try:
            ttl = self._demand_ttl(city_id)
            client.setex(
                f"search_cache:{query_hash}",
                ttl,
                json.dumps(results, default=str),
            )
        except Exception:
            pass

    def get_hotel_rate(self, hotel_id, date):
        """Get cached hotel rate."""
        client = self._client()
        if not client:
            return None
        try:
            val = client.get(f"hotel_rate_cache:{hotel_id}:{date}")
            return json.loads(val) if val else None
        except Exception:
            return None

    def set_hotel_rate(self, hotel_id, date, rate_data):
        """Cache hotel rate."""
        client = self._client()
        if not client:
            return
        try:
            client.setex(
                f"hotel_rate_cache:{hotel_id}:{date}",
                self.TTL_RATE,
                json.dumps(rate_data, default=str),
            )
        except Exception:
            pass

    def invalidate_hotel(self, hotel_id):
        """Invalidate all cached data for a hotel."""
        client = self._client()
        if not client:
            return
        try:
            for pattern in [f"hotel_rate_cache:{hotel_id}:*", f"availability_cache:{hotel_id}:*"]:
                cursor = 0
                while True:
                    cursor, keys = client.scan(cursor, match=pattern, count=100)
                    if keys:
                        client.delete(*keys)
                    if cursor == 0:
                        break
        except Exception:
            pass

    @staticmethod
    def build_query_hash(query, filters=None, page=1, sort=None):
        """Build deterministic hash for a search query + filters."""
        raw = f"{query}|{json.dumps(filters or {}, sort_keys=True)}|{page}|{sort}"
        return hashlib.md5(raw.encode()).hexdigest()


search_result_cache = SearchResultCache()


def _haversine(lat1, lng1, lat2, lng2):
    """Haversine distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
