"""
Checkout Celery Tasks — Background jobs for session expiry, analytics, risk.

Tasks:
  1. expire_checkout_sessions — Run every 2 min, expire stale sessions
  2. aggregate_funnel_analytics — Run hourly, compute daily conversion rates
  3. batch_risk_scoring — Run every 5 min, score sessions missing risk scores
  4. cleanup_old_sessions — Run daily, purge sessions older than 30 days
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger('zygotrip.checkout.tasks')


@shared_task(name='checkout.expire_sessions')
def expire_checkout_sessions():
    """Expire stale checkout sessions and release their inventory holds."""
    from .services import expire_stale_sessions
    count = expire_stale_sessions()
    return f"Expired {count} sessions"


@shared_task(name='checkout.aggregate_funnel')
def aggregate_funnel_analytics(date_str=None):
    """
    Pre-aggregate funnel conversion metrics for a given date.
    Default: yesterday.
    """
    from .analytics_models import BookingAnalytics, FunnelConversionDaily

    if date_str:
        from datetime import date as date_type
        target_date = date_type.fromisoformat(date_str)
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()

    # Get all events for the date
    events = BookingAnalytics.objects.filter(
        event_timestamp__date=target_date,
    )

    if not events.exists():
        return f"No events for {target_date}"

    # Get cities in events
    cities = list(
        events.values_list('search_city', flat=True)
        .distinct()
    )
    cities.append('')  # Also compute aggregate for "ALL" cities

    count = 0
    for city in cities:
        qs = events.filter(search_city=city) if city else events

        counts = {}
        for event_type in [
            'search_view', 'hotel_click', 'room_select',
            'checkout_start', 'payment_start', 'payment_success',
            'booking_success', 'booking_cancel',
        ]:
            counts[event_type] = qs.filter(event_type=event_type).count()

        # Revenue
        revenue = qs.filter(
            event_type='booking_success',
            revenue_amount__isnull=False,
        ).aggregate(
            total=Sum('revenue_amount'),
            count=Count('id'),
        )

        total_revenue = revenue['total'] or Decimal('0')
        booking_count = revenue['count'] or 0
        avg_value = total_revenue / booking_count if booking_count > 0 else Decimal('0')

        # Conversion rates
        def rate(num_key, denom_key):
            n = counts.get(num_key, 0)
            d = counts.get(denom_key, 0)
            return Decimal(str(round(n / d * 100, 2))) if d > 0 else Decimal('0')

        funnel, _ = FunnelConversionDaily.objects.update_or_create(
            date=target_date,
            city=city,
            defaults={
                'search_views': counts.get('search_view', 0),
                'hotel_clicks': counts.get('hotel_click', 0),
                'room_selects': counts.get('room_select', 0),
                'checkout_starts': counts.get('checkout_start', 0),
                'payment_starts': counts.get('payment_start', 0),
                'payment_successes': counts.get('payment_success', 0),
                'booking_successes': counts.get('booking_success', 0),
                'booking_cancels': counts.get('booking_cancel', 0),
                'search_to_click_rate': rate('hotel_click', 'search_view'),
                'click_to_checkout_rate': rate('checkout_start', 'hotel_click'),
                'checkout_to_payment_rate': rate('payment_start', 'checkout_start'),
                'payment_to_booking_rate': rate('booking_success', 'payment_start'),
                'overall_conversion_rate': rate('booking_success', 'search_view'),
                'total_revenue': total_revenue,
                'avg_booking_value': avg_value,
            },
        )
        count += 1

    return f"Aggregated funnel for {target_date} across {count} city segments"


@shared_task(name='checkout.batch_risk_scoring')
def batch_risk_scoring():
    """Score checkout sessions that don't have risk scores yet."""
    from .models import BookingSession
    from .analytics_models import BookingRiskScore
    from .services import compute_risk_score

    sessions = BookingSession.objects.filter(
        session_status__in=[
            BookingSession.STATUS_ROOM_SELECTED,
            BookingSession.STATUS_GUEST_DETAILS,
            BookingSession.STATUS_PAYMENT_INITIATED,
        ],
    ).exclude(
        risk_score__isnull=False,  # Already scored
    ).select_related('user')[:50]  # Batch of 50

    count = 0
    for session in sessions:
        try:
            compute_risk_score(session)
            count += 1
        except Exception as exc:
            logger.error("Risk scoring failed for %s: %s", session.session_id, exc)

    return f"Scored {count} sessions"


@shared_task(name='checkout.cleanup_old_sessions')
def cleanup_old_sessions(days=30):
    """Purge completed/expired/abandoned sessions older than N days."""
    from .models import BookingSession

    cutoff = timezone.now() - timedelta(days=days)
    terminal_statuses = [
        BookingSession.STATUS_COMPLETED,
        BookingSession.STATUS_EXPIRED,
        BookingSession.STATUS_ABANDONED,
    ]

    deleted, _ = BookingSession.objects.filter(
        session_status__in=terminal_statuses,
        created_at__lt=cutoff,
    ).delete()

    logger.info("Cleaned up %d old checkout sessions", deleted)
    return f"Deleted {deleted} old sessions"
