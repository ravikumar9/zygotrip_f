"""
Analytics Tracking — Booking funnel events and AB testing.

Tracks:
  - Search events (query, filters, results count)
  - Property view events (property_id, source)
  - Room selection events
  - Booking funnel stages (context_created → payment_initiated → confirmed)
  - Conversion metrics

All events are asynchronous (Celery tasks) to avoid adding latency.
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.analytics')


EVENT_TYPE_ALIASES = {
    'hotel_click': 'hotel_click',
    'hotel_view': 'property_view',
    'booking_attempt': 'booking_attempt',
    'booking_created': 'booking_attempt',
}


class AnalyticsEvent(TimeStampedModel):
    """Core analytics event model — append-only event log."""

    # Event types
    EVENT_SEARCH = 'search'
    EVENT_HOTEL_CLICK = 'hotel_click'
    EVENT_PROPERTY_VIEW = 'property_view'
    EVENT_ROOM_SELECT = 'room_select'
    EVENT_BOOKING_CONTEXT = 'booking_context_created'
    EVENT_BOOKING_ATTEMPT = 'booking_attempt'
    EVENT_PAYMENT_INIT = 'payment_initiated'
    EVENT_PAYMENT_SUCCESS = 'payment_success'
    EVENT_PAYMENT_FAIL = 'payment_failed'
    EVENT_BOOKING_CONFIRMED = 'booking_confirmed'
    EVENT_BOOKING_CANCELLED = 'booking_cancelled'
    EVENT_REVIEW_SUBMITTED = 'review_submitted'
    EVENT_PROMO_APPLIED = 'promo_applied'
    EVENT_LOYALTY_REDEEM = 'loyalty_redeemed'

    EVENT_CHOICES = [
        (EVENT_SEARCH, 'Search'),
        (EVENT_HOTEL_CLICK, 'Hotel Click'),
        (EVENT_PROPERTY_VIEW, 'Property View'),
        (EVENT_ROOM_SELECT, 'Room Select'),
        (EVENT_BOOKING_CONTEXT, 'Booking Context Created'),
        (EVENT_BOOKING_ATTEMPT, 'Booking Attempt'),
        (EVENT_PAYMENT_INIT, 'Payment Initiated'),
        (EVENT_PAYMENT_SUCCESS, 'Payment Success'),
        (EVENT_PAYMENT_FAIL, 'Payment Failed'),
        (EVENT_BOOKING_CONFIRMED, 'Booking Confirmed'),
        (EVENT_BOOKING_CANCELLED, 'Booking Cancelled'),
        (EVENT_REVIEW_SUBMITTED, 'Review Submitted'),
        (EVENT_PROMO_APPLIED, 'Promo Applied'),
        (EVENT_LOYALTY_REDEEM, 'Loyalty Redeemed'),
    ]

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)

    # Event-specific data (JSON)
    properties = models.JSONField(default=dict, blank=True)

    # Denormalized fields for fast aggregation
    city = models.CharField(max_length=100, blank=True, db_index=True)
    property_id = models.IntegerField(null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'core'
        db_table = 'core_analytics_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', '-created_at'], name='analytics_type_time_idx'),
            models.Index(fields=['user', '-created_at'], name='analytics_user_time_idx'),
            models.Index(fields=['session_id', '-created_at'], name='analytics_session_idx'),
        ]

    def __str__(self):
        return f'{self.event_type} — {self.session_id[:8]}... — {self.created_at}'


class DailyMetrics(TimeStampedModel):
    """Pre-aggregated daily metrics for dashboard."""
    date = models.DateField(unique=True)
    total_searches = models.IntegerField(default=0)
    total_property_views = models.IntegerField(default=0)
    total_booking_contexts = models.IntegerField(default=0)
    total_bookings_confirmed = models.IntegerField(default=0)
    total_bookings_cancelled = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_payments_failed = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    avg_booking_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        app_label = 'core'
        db_table = 'core_daily_metrics'
        ordering = ['-date']

    def __str__(self):
        return f'Metrics {self.date}: {self.total_bookings_confirmed} bookings, ₹{self.total_revenue}'


class HotelPerformanceMetrics(TimeStampedModel):
    """Pre-aggregated hotel-level performance for owner dashboard."""
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='performance_metrics',
    )
    date = models.DateField(db_index=True)
    impressions = models.IntegerField(default=0, help_text='Times shown in search results')
    views = models.IntegerField(default=0, help_text='Detail page views')
    clicks_to_book = models.IntegerField(default=0, help_text='Room select clicks')
    bookings = models.IntegerField(default=0)
    cancellations = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    avg_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    occupancy_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    avg_review_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    # Conversion funnel
    search_to_view_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    view_to_book_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    class Meta:
        app_label = 'core'
        db_table = 'core_hotel_performance'
        unique_together = ['property', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['property', '-date'], name='hotel_perf_prop_date_idx'),
        ]

    def __str__(self):
        return f'{self.property_id} metrics {self.date}'


class ABTestVariant(TimeStampedModel):
    """A/B test experiment tracking."""
    experiment_name = models.CharField(max_length=100, db_index=True)
    variant = models.CharField(max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    converted = models.BooleanField(default=False)
    conversion_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['experiment_name', 'variant', 'converted'],
                         name='ab_exp_variant_idx'),
        ]


# ── Service functions ──────────────────────────────────────────────────────────


def track_event(event_type: str, request=None, user=None, **kwargs):
    """
    Track an analytics event. Call this from views/services.
    Saves directly for now; can be made async via Celery later.
    """
    try:
        event_type = EVENT_TYPE_ALIASES.get(event_type, event_type)
        properties = {
            **(kwargs.get('properties', {}) or {}),
            **(kwargs.get('metadata', {}) or {}),
        }
        event_data = {
            'event_type': event_type,
            'user': user or (request.user if request and request.user.is_authenticated else None),
            'properties': properties,
            'city': kwargs.get('city', ''),
            'property_id': kwargs.get('property_id') or properties.get('property_id'),
            'amount': kwargs.get('amount') or properties.get('amount'),
        }

        if request:
            event_data['ip_address'] = _get_client_ip(request)
            event_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
            event_data['referrer'] = request.META.get('HTTP_REFERER', '')[:200]
            event_data['session_id'] = _get_session_id(request)

        AnalyticsEvent.objects.create(**event_data)
    except Exception as e:
        logger.error('Failed to track analytics event %s: %s', event_type, e)


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_session_id(request):
    """Get or create a session ID from cookie or generate one."""
    session_id = request.COOKIES.get('zygo_sid', '')
    if not session_id:
        session_id = uuid.uuid4().hex[:16]
    return session_id


def compute_daily_metrics(date=None):
    """Compute and store daily aggregated metrics."""
    from django.db.models import Count, Sum, Avg
    if date is None:
        date = timezone.now().date() - timezone.timedelta(days=1)  # yesterday

    events_qs = AnalyticsEvent.objects.filter(created_at__date=date)

    metrics = {
        'total_searches': events_qs.filter(event_type=AnalyticsEvent.EVENT_SEARCH).count(),
        'total_property_views': events_qs.filter(event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW).count(),
        'total_booking_contexts': events_qs.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONTEXT).count(),
        'total_bookings_confirmed': events_qs.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED).count(),
        'total_bookings_cancelled': events_qs.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CANCELLED).count(),
        'total_revenue': events_qs.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'total_payments_failed': events_qs.filter(event_type=AnalyticsEvent.EVENT_PAYMENT_FAIL).count(),
        'unique_users': events_qs.exclude(user=None).values('user').distinct().count(),
    }

    # Conversion rate: confirmed / contexts
    if metrics['total_booking_contexts'] > 0:
        metrics['conversion_rate'] = Decimal(
            metrics['total_bookings_confirmed'] / metrics['total_booking_contexts'] * 100
        ).quantize(Decimal('0.01'))

    if metrics['total_bookings_confirmed'] > 0:
        metrics['avg_booking_value'] = (
            metrics['total_revenue'] / metrics['total_bookings_confirmed']
        ).quantize(Decimal('0.01'))

    DailyMetrics.objects.update_or_create(date=date, defaults=metrics)
    logger.info('Daily metrics computed for %s: %s', date, metrics)
    return metrics


# ── Funnel Analytics ──────────────────────────────────────────────────────────


def get_funnel_metrics(start_date, end_date):
    """
    Compute booking funnel conversion rates for a date range.
    Returns dict with stage counts and conversion rates.
    """
    events = AnalyticsEvent.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    funnel = {
        'searches': events.filter(event_type=AnalyticsEvent.EVENT_SEARCH).count(),
        'property_views': events.filter(event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW).count(),
        'room_selects': events.filter(event_type=AnalyticsEvent.EVENT_ROOM_SELECT).count(),
        'booking_contexts': events.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONTEXT).count(),
        'payments_initiated': events.filter(event_type=AnalyticsEvent.EVENT_PAYMENT_INIT).count(),
        'payments_success': events.filter(event_type=AnalyticsEvent.EVENT_PAYMENT_SUCCESS).count(),
        'bookings_confirmed': events.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED).count(),
    }

    # Compute conversion rates between stages
    rates = {}
    stages = list(funnel.keys())
    for i in range(1, len(stages)):
        prev = funnel[stages[i - 1]]
        curr = funnel[stages[i]]
        key = f'{stages[i - 1]}_to_{stages[i]}'
        rates[key] = round((curr / prev * 100), 1) if prev > 0 else 0

    # Overall conversion: searches → confirmed
    if funnel['searches'] > 0:
        rates['overall'] = round(
            funnel['bookings_confirmed'] / funnel['searches'] * 100, 2,
        )
    else:
        rates['overall'] = 0

    return {'funnel': funnel, 'conversion_rates': rates}


def get_property_analytics(property_id, days=30):
    """
    Get analytics summary for a specific property.
    Used by property owners in their dashboard.
    """
    cutoff = timezone.now() - timezone.timedelta(days=days)

    events = AnalyticsEvent.objects.filter(
        property_id=property_id,
        created_at__gte=cutoff,
    )

    from django.db.models import Count, Avg, Sum

    return {
        'views': events.filter(event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW).count(),
        'room_selects': events.filter(event_type=AnalyticsEvent.EVENT_ROOM_SELECT).count(),
        'bookings': events.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED).count(),
        'revenue': float(
            events.filter(
                event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
            ).aggregate(total=Sum('amount'))['total'] or 0,
        ),
        'unique_visitors': events.filter(
            event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
        ).values('session_id').distinct().count(),
        'conversion_rate': round(
            events.filter(event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED).count() /
            max(events.filter(event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW).count(), 1) * 100,
            1,
        ),
        'period_days': days,
    }


def compute_hotel_performance(date=None):
    """
    Compute per-hotel daily performance metrics.
    Designed to run as a nightly Celery beat task.
    """
    from django.db.models import Count, Sum, Avg as DbAvg

    if date is None:
        date = timezone.now().date() - timezone.timedelta(days=1)

    events = AnalyticsEvent.objects.filter(created_at__date=date)

    # Group events by property_id
    property_ids = (
        events.exclude(property_id=None)
        .values_list('property_id', flat=True)
        .distinct()
    )

    for pid in property_ids:
        prop_events = events.filter(property_id=pid)
        impressions = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_SEARCH,
        ).count()
        views = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
        ).count()
        clicks = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_ROOM_SELECT,
        ).count()
        bookings = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
        ).count()
        cancellations = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CANCELLED,
        ).count()
        revenue = prop_events.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        s2v = round(views / max(impressions, 1) * 100, 2) if impressions else 0
        v2b = round(bookings / max(views, 1) * 100, 2) if views else 0

        HotelPerformanceMetrics.objects.update_or_create(
            property_id=pid,
            date=date,
            defaults={
                'impressions': impressions,
                'views': views,
                'clicks_to_book': clicks,
                'bookings': bookings,
                'cancellations': cancellations,
                'revenue': revenue,
                'search_to_view_rate': Decimal(str(s2v)),
                'view_to_book_rate': Decimal(str(v2b)),
            },
        )

    logger.info('Hotel performance computed for %s: %d properties', date, len(property_ids))


def track_event_async(event_type: str, request=None, user=None, **kwargs):
    """Async version of track_event — dispatches via Celery."""
    from apps.core.analytics_tasks import track_event_task
    event_type = EVENT_TYPE_ALIASES.get(event_type, event_type)
    req_data = {}
    if request:
        req_data = {
            'ip_address': _get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'referrer': request.META.get('HTTP_REFERER', '')[:200],
            'session_id': _get_session_id(request),
        }
    track_event_task.delay(
        event_type=event_type,
        user_id=user.id if user else (
            request.user.id if request and request.user.is_authenticated else None
        ),
        req_data=req_data,
        **kwargs,
    )
