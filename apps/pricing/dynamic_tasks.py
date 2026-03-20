"""Celery tasks for dynamic pricing recalculation."""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.pricing.dynamic.tasks')


@shared_task
def recalculate_dynamic_prices():
    """
    Every 6 hours: recalculate demand multipliers for all active properties
    for the next 30 days.
    """
    from apps.hotels.models import Property
    from apps.pricing.dynamic_pricing import demand_pricing_service
    from django.utils import timezone
    import datetime

    today = timezone.now().date()
    properties = Property.objects.filter(is_active=True).values_list('id', flat=True)
    updated = 0

    for prop_id in properties:
        for delta in range(30):
            date = today + datetime.timedelta(days=delta)
            try:
                multiplier = demand_pricing_service._compute_multiplier(prop_id, date)
                demand_pricing_service._cache_multiplier(prop_id, date, multiplier)
                updated += 1
            except Exception as exc:
                logger.debug('recalculate_dynamic_prices: prop=%s date=%s err=%s', prop_id, date, exc)

    logger.info('recalculate_dynamic_prices: updated %d price caches', updated)
    return {'updated': updated}
