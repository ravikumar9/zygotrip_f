"""
Analytics Celery Tasks — async event tracking and daily aggregation.
"""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.analytics')


@shared_task(name='core.track_event', acks_late=True)
def track_event_task(event_type, user_id=None, req_data=None, **kwargs):
    """Async analytics event creation."""
    from django.contrib.auth import get_user_model
    from apps.core.analytics import AnalyticsEvent

    User = get_user_model()
    user = None
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    req_data = req_data or {}
    try:
        AnalyticsEvent.objects.create(
            event_type=event_type,
            user=user,
            ip_address=req_data.get('ip_address'),
            user_agent=req_data.get('user_agent', ''),
            referrer=req_data.get('referrer', ''),
            session_id=req_data.get('session_id', ''),
            properties=kwargs.get('properties', {}),
            city=kwargs.get('city', ''),
            property_id=kwargs.get('property_id'),
            amount=kwargs.get('amount'),
        )
    except Exception as exc:
        logger.error('Async track_event failed: %s', exc)


@shared_task(name='core.compute_daily_metrics')
def compute_daily_metrics_task(date_str=None):
    """Nightly Celery beat task — compute yesterday's daily metrics."""
    from apps.core.analytics import compute_daily_metrics
    import datetime
    date = (
        datetime.date.fromisoformat(date_str)
        if date_str
        else None
    )
    compute_daily_metrics(date)


@shared_task(name='core.compute_hotel_performance')
def compute_hotel_performance_task(date_str=None):
    """Nightly Celery beat task — compute per-hotel performance."""
    from apps.core.analytics import compute_hotel_performance
    import datetime
    date = (
        datetime.date.fromisoformat(date_str)
        if date_str
        else None
    )
    compute_hotel_performance(date)
