"""
User Search Profile — Server-side personalization signal aggregator.

Caches per-user behavioral signals for search ranking personalization:
  - preferred cities (from bookings + searches)
  - average booking price range
  - preferred star category
  - recent search destinations
  - booking count + frequency

Updated by Celery task every 2 hours. Used by SearchRankingV2._load_user_history()
as a fast lookup instead of hitting Booking table every search request.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.search.personalization')

PROFILE_CACHE_TTL = 3600  # 1 hour Redis cache per user profile


class UserSearchProfile(TimeStampedModel):
    """
    Aggregated personalization profile for a user.

    Computed from booking history, search history, and click patterns.
    Used as a fast lookup for search ranking personalization instead of
    running expensive aggregation queries per search request.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='search_profile',
    )

    # Preferred cities (JSON list of city IDs, ordered by frequency)
    preferred_cities = models.JSONField(
        default=list,
        help_text='City IDs ordered by booking frequency',
    )

    # Recent search destinations (JSON list of city names, last 30 days)
    recent_search_cities = models.JSONField(
        default=list,
        help_text='Recent search destination names (last 30 days)',
    )

    # Price preferences
    avg_booking_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Average booking amount',
    )
    min_price_range = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )
    max_price_range = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )

    # Star preference
    preferred_star = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Most frequently booked star category',
    )

    # Booking behavior
    total_bookings = models.PositiveIntegerField(default=0)
    total_cancellations = models.PositiveIntegerField(default=0)
    booking_frequency_days = models.FloatField(
        default=0.0,
        help_text='Average days between bookings',
    )

    # Traveler type (most frequent)
    traveller_type = models.CharField(
        max_length=20, blank=True,
        help_text='Most frequent traveler type from reviews',
    )

    # Last aggregation timestamp
    last_aggregated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'search'
        indexes = [
            models.Index(fields=['user'], name='usp_user_idx'),
        ]

    def __str__(self):
        return f"SearchProfile for user {self.user_id} ({self.total_bookings} bookings)"

    def to_ranking_dict(self) -> dict:
        """Convert to the dict format expected by SearchRankingV2._personalization_score."""
        return {
            'booked_cities': self.preferred_cities or [],
            'avg_booking_price': float(self.avg_booking_price or 0),
            'preferred_star': self.preferred_star,
            'booking_count': self.total_bookings,
            'recent_search_cities': self.recent_search_cities or [],
            'min_price': float(self.min_price_range or 0),
            'max_price': float(self.max_price_range or 0),
            'traveller_type': self.traveller_type,
        }


def get_user_profile_for_ranking(user_id: int) -> dict:
    """
    Fast lookup: get user personalization data for search ranking.

    1. Check Redis cache
    2. Check UserSearchProfile in DB
    3. Fall back to empty dict (no personalization)

    Called by SearchRankingV2._load_user_history().
    """
    if not user_id:
        return {}

    cache_key = f'usp:{user_id}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        profile = UserSearchProfile.objects.get(user_id=user_id)
        data = profile.to_ranking_dict()
        cache.set(cache_key, data, PROFILE_CACHE_TTL)
        return data
    except UserSearchProfile.DoesNotExist:
        return {}


def aggregate_user_profile(user_id: int) -> UserSearchProfile:
    """
    Recompute a user's search profile from booking + search history.

    Called by Celery task `refresh_user_search_profiles`.
    """
    from apps.booking.models import Booking

    profile, _ = UserSearchProfile.objects.get_or_create(user_id=user_id)

    # ── Booking aggregations ──────────────────────────────────────
    cutoff = timezone.now() - timedelta(days=365)
    bookings = Booking.objects.filter(
        user_id=user_id,
        created_at__gte=cutoff,
    ).select_related('property')

    completed = bookings.filter(
        status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
    )
    cancelled = bookings.filter(
        status__in=['cancelled', 'cancelled_by_hotel', 'refunded'],
    )

    profile.total_bookings = completed.count()
    profile.total_cancellations = cancelled.count()

    if completed.exists():
        # City frequency
        city_counts = (
            completed
            .values('property__city_id')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        profile.preferred_cities = [
            row['property__city_id']
            for row in city_counts[:15]
            if row['property__city_id']
        ]

        # Price range
        price_agg = completed.aggregate(
            avg=Avg('total_amount'),
            mn=models.Min('total_amount'),
            mx=models.Max('total_amount'),
        )
        profile.avg_booking_price = Decimal(str(price_agg['avg'] or 0)).quantize(Decimal('0.01'))
        profile.min_price_range = Decimal(str(price_agg['mn'] or 0)).quantize(Decimal('0.01'))
        profile.max_price_range = Decimal(str(price_agg['mx'] or 0)).quantize(Decimal('0.01'))

        # Star preference (mode)
        star_counts = (
            completed.filter(property__star_category__isnull=False)
            .values('property__star_category')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        if star_counts:
            profile.preferred_star = int(star_counts[0]['property__star_category'])

        # Booking frequency
        dates = list(completed.order_by('created_at').values_list('created_at', flat=True))
        if len(dates) >= 2:
            total_span = (dates[-1] - dates[0]).days
            profile.booking_frequency_days = round(total_span / (len(dates) - 1), 1)

    # ── Recent searches ──────────────────────────────────────────
    try:
        from apps.hotels.models import RecentSearch
        search_cutoff = timezone.now() - timedelta(days=30)
        recent = (
            RecentSearch.objects.filter(
                user_id=user_id,
                created_at__gte=search_cutoff,
            )
            .values_list('destination', flat=True)
            .distinct()[:10]
        )
        profile.recent_search_cities = list(recent)
    except Exception:
        pass

    # ── Traveler type (from reviews) ─────────────────────────────
    try:
        from apps.hotels.review_models import Review
        type_counts = (
            Review.objects.filter(user_id=user_id)
            .exclude(traveller_type='')
            .values('traveller_type')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        if type_counts:
            profile.traveller_type = type_counts[0]['traveller_type']
    except Exception:
        pass

    profile.save()

    # Invalidate cache
    cache.delete(f'usp:{user_id}')

    return profile
