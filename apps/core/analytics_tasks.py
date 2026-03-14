"""
Analytics Celery Tasks — async event tracking and daily aggregation.
"""
import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger('zygotrip.analytics')


@shared_task(name='core.track_event', acks_late=True)
def track_event_task(event_type, user_id=None, req_data=None, **kwargs):
    """Async analytics event creation."""
    from django.contrib.auth import get_user_model
    from apps.core.analytics import AnalyticsEvent, EVENT_TYPE_ALIASES

    User = get_user_model()
    user = None
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    req_data = req_data or {}
    try:
        properties = {
            **(kwargs.get('properties', {}) or {}),
            **(kwargs.get('metadata', {}) or {}),
        }
        event = AnalyticsEvent.objects.create(
            event_type=EVENT_TYPE_ALIASES.get(event_type, event_type),
            user=user,
            ip_address=req_data.get('ip_address'),
            user_agent=req_data.get('user_agent', ''),
            referrer=req_data.get('referrer', ''),
            session_id=req_data.get('session_id', ''),
            properties=properties,
            city=kwargs.get('city', ''),
            property_id=kwargs.get('property_id') or properties.get('property_id'),
            amount=kwargs.get('amount') or properties.get('amount'),
        )
        export_analytics_events_to_warehouse.delay(last_event_id=max(event.id - 1, 0), batch_size=250)
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


@shared_task(name='core.export_analytics_events_to_warehouse')
def export_analytics_events_to_warehouse(last_event_id=None, batch_size=500):
    """Publish analytics events as an ordered downstream export stream."""
    return _export_analytics_events_to_warehouse_impl(
        last_event_id=last_event_id,
        batch_size=batch_size,
    )


def _export_analytics_events_to_warehouse_impl(last_event_id=None, batch_size=500):
    """Implementation for warehouse export that can be exercised without Celery."""
    from apps.core.analytics import AnalyticsEvent
    from apps.core.event_bus import DomainEvent, event_bus

    checkpoint_key = 'analytics:warehouse_export:last_id'
    start_id = last_event_id if last_event_id is not None else (cache.get(checkpoint_key, 0) or 0)
    events = AnalyticsEvent.objects.filter(id__gt=start_id).order_by('id')[:batch_size]

    exported = 0
    max_id = start_id
    for event in events:
        payload = {
            'event_id': str(event.event_id),
            'event_type': event.event_type,
            'created_at': event.created_at.isoformat(),
            'session_id': event.session_id,
            'user_id': event.user_id,
            'property_id': event.property_id,
            'city': event.city,
            'amount': str(event.amount) if event.amount is not None else None,
            'properties': event.properties,
            'ip_address': str(event.ip_address) if event.ip_address else None,
            'user_agent': event.user_agent,
            'referrer': event.referrer,
        }
        event_bus.publish(DomainEvent(
            event_type='analytics.warehouse_exported',
            payload=payload,
            user_id=event.user_id,
            source='core.analytics_tasks',
        ))
        logger.info('warehouse_event %s', payload)
        exported += 1
        max_id = event.id

    if exported:
        cache.set(checkpoint_key, max_id, timeout=None)

    return {'exported': exported, 'last_id': max_id}
