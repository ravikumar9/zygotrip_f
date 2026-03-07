"""
Enhanced Search Ranking with Intelligence Signals.

OTA-grade ranking engine with 9 weighted factors:
  match_relevance, quality_score, rating_score, popularity_score,
  price_score, freshness_score, ctr_score, geo_distance_score,
  conversion_score.

Weights are configurable at instantiation time and via Django settings.
Comparable to MakeMyTrip/Agoda/Goibibo ranking systems.
"""
import logging
import math
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('zygotrip.search.ranking')

# Default weights — can be overridden in settings.SEARCH_RANKING_WEIGHTS
DEFAULT_WEIGHTS = {
    'match': 0.18,
    'quality': 0.14,
    'rating': 0.14,
    'popularity': 0.10,
    'price': 0.10,
    'freshness': 0.06,
    'ctr': 0.10,
    'geo': 0.10,
    'conversion': 0.08,
}


class EnhancedRankingEngine:
    """
    OTA-grade ranking with intelligence signals.

    Score formula (0-100):
      match_relevance   * W_MATCH
      quality_score     * W_QUALITY
      rating_score      * W_RATING
      popularity_score  * W_POPULARITY
      price_score       * W_PRICE
      freshness_score   * W_FRESHNESS
      ctr_score         * W_CTR
      geo_distance      * W_GEO
      conversion_score  * W_CONVERSION   (NEW: booking conversion rate)

    Weights are configurable via constructor or settings.SEARCH_RANKING_WEIGHTS.
    """

    def __init__(self, weights: dict | None = None):
        """
        Args:
            weights: Optional dict overriding default weights.
                     Keys: match, quality, rating, popularity, price,
                           freshness, ctr, geo, conversion.
        """
        cfg = getattr(settings, 'SEARCH_RANKING_WEIGHTS', None) or {}
        w = {**DEFAULT_WEIGHTS, **(cfg or {}), **(weights or {})}
        self.W_MATCH = w['match']
        self.W_QUALITY = w['quality']
        self.W_RATING = w['rating']
        self.W_POPULARITY = w['popularity']
        self.W_PRICE = w['price']
        self.W_FRESHNESS = w['freshness']
        self.W_CTR = w['ctr']
        self.W_GEO = w['geo']
        self.W_CONVERSION = w['conversion']

    def rank(self, items, query: str | None = None, user_context: dict | None = None) -> list:
        """
        Rank a list of PropertySearchIndex rows (or Property objects).

        Args:
            items: queryset / list of objects
            query: optional search query for relevance scoring
            user_context: optional dict with user_lat, user_lng, device, etc.

        Returns:
            sorted list with ``ranking_score`` attribute set
        """
        items = list(items)
        if not items:
            return items

        user_context = user_context or {}

        # Normalisation denominators
        max_pop = max((getattr(i, 'popularity_score', 0) or 0) for i in items) or 1
        max_reviews = max((getattr(i, 'review_count', 0) or 0) for i in items) or 1
        prices = [float(getattr(i, 'price_min', 0) or getattr(i, 'base_price', 0) or 0) for i in items]
        max_price = max(prices) if prices else 1
        min_price = min(p for p in prices if p > 0) if any(p > 0 for p in prices) else 1

        # Geo: compute distances if user location is provided
        user_lat = user_context.get('user_lat')
        user_lng = user_context.get('user_lng')
        distances = []
        if user_lat is not None and user_lng is not None:
            for item in items:
                lat = float(getattr(item, 'latitude', 0) or 0)
                lng = float(getattr(item, 'longitude', 0) or 0)
                distances.append(self._haversine(user_lat, user_lng, lat, lng) if lat and lng else 999)
        else:
            distances = [0] * len(items)
        max_dist = max(distances) if distances else 1
        max_dist = max_dist if max_dist > 0 else 1

        for idx, item in enumerate(items):
            m = self._match_score(item, query)
            q = self._quality_score(item)
            r = self._rating_score(item, max_reviews)
            p = self._popularity_score(item, max_pop)
            pr = self._price_score(prices[idx], min_price, max_price)
            f = self._freshness_score(item)
            ctr = self._ctr_score(item)
            geo = self._geo_distance_score(distances[idx], max_dist)
            conv = self._conversion_score(item)

            score = (
                m   * self.W_MATCH
                + q   * self.W_QUALITY
                + r   * self.W_RATING
                + p   * self.W_POPULARITY
                + pr  * self.W_PRICE
                + f   * self.W_FRESHNESS
                + ctr * self.W_CTR
                + geo * self.W_GEO
                + conv * self.W_CONVERSION
            ) * 100

            item.ranking_score = round(score, 4)

        items.sort(key=lambda x: x.ranking_score, reverse=True)
        return items

    # ----- Component scorers -----

    @staticmethod
    def _match_score(item, query: str | None) -> float:
        if not query:
            return 0.5
        q = query.lower()
        candidates = [
            getattr(item, 'property_name', '') or getattr(item, 'name', ''),
            getattr(item, 'city_name', '') or str(getattr(item, 'city', '')),
            getattr(item, 'locality_name', '') or str(getattr(item, 'locality', '')),
        ]
        best = 0.0
        for c in candidates:
            c = (c or '').lower()
            if not c:
                continue
            if q in c:
                return 1.0
            best = max(best, SequenceMatcher(None, q, c).ratio())
        return best

    @staticmethod
    def _quality_score(item) -> float:
        """Read HotelQualityScore if available."""
        qs = getattr(item, 'quality_score', None)
        if qs is not None:
            try:
                return min(1.0, float(qs) / 100)
            except (TypeError, ValueError):
                pass
        # Fallback: use review_score
        rs = float(getattr(item, 'review_score', 0) or 0)
        return min(1.0, rs / 10) if rs else 0.5

    @staticmethod
    def _rating_score(item, max_reviews: int) -> float:
        rating = float(getattr(item, 'rating', 0) or 0) / 5.0
        cnt = (getattr(item, 'review_count', 0) or 0) / max_reviews
        return rating * 0.7 + cnt * 0.3

    @staticmethod
    def _popularity_score(item, max_pop: int) -> float:
        pop = getattr(item, 'popularity_score', 0) or 0
        trending = 0.2 if getattr(item, 'is_trending', False) else 0
        return (pop / max_pop) * 0.8 + trending

    @staticmethod
    def _price_score(price: float, min_price: float, max_price: float) -> float:
        """Lower price = higher score (value for money)."""
        if max_price == min_price:
            return 0.5
        return 1.0 - ((price - min_price) / (max_price - min_price))

    @staticmethod
    def _freshness_score(item) -> float:
        updated = getattr(item, 'updated_at', None) or getattr(item, 'modified_at', None)
        if not updated:
            return 0.5
        try:
            age_days = (timezone.now() - updated).days
            if age_days <= 1:
                return 1.0
            elif age_days <= 7:
                return 0.8
            elif age_days <= 30:
                return 0.5
            return 0.2
        except Exception:
            return 0.5

    @staticmethod
    def _ctr_score(item) -> float:
        """
        Click-through rate score.
        Uses impressions and clicks if available, otherwise falls back to
        bookings_today or booking_count as a proxy.
        """
        impressions = getattr(item, 'impressions', 0) or 0
        clicks = getattr(item, 'clicks', 0) or 0
        if impressions > 0:
            ctr = clicks / impressions
            # Normalize: 5% CTR = 0.5 score, 10%+ = 1.0
            return min(1.0, ctr / 0.10)

        # Fallback: use bookings_today as a CTR proxy
        bookings_today = getattr(item, 'bookings_today', 0) or 0
        if bookings_today >= 5:
            return 1.0
        elif bookings_today >= 2:
            return 0.7
        elif bookings_today >= 1:
            return 0.4
        return 0.2

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine distance in km between two lat/lng points."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _conversion_score(item) -> float:
        """
        Booking conversion rate score (views → bookings).
        Higher conversion = better ranking.
        Falls back to 0.5 if data unavailable.
        """
        views = getattr(item, 'total_views', 0) or 0
        bookings = getattr(item, 'total_bookings', 0) or getattr(item, 'booking_count', 0) or 0
        if views >= 10:
            rate = bookings / views
            # Normalize: 5% conversion = 0.5 score, 15%+ = 1.0
            return min(1.0, rate / 0.15)
        # Not enough data — neutral
        return 0.5

    @staticmethod
    def _geo_distance_score(distance_km: float, max_distance_km: float) -> float:
        """
        Closer = higher score.
        0 km → 1.0, max distance → 0.0.
        Uses inverse exponential decay for natural distance weighting.
        """
        if max_distance_km <= 0:
            return 0.5
        if distance_km <= 0:
            return 1.0
        # Exponential decay: e^(-distance/scale)
        scale = max_distance_km / 3.0  # score drops to ~0.05 at max distance
        return min(1.0, math.exp(-distance_km / scale))
