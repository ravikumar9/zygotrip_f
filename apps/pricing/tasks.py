"""
Pricing Celery Tasks — Dynamic price recomputation.
"""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.pricing')


@shared_task(name='apps.pricing.tasks.recompute_dynamic_prices')
def recompute_dynamic_prices():
    """
    Recompute dynamic prices for all active properties.
    Runs every 6 hours via Celery beat.
    Applies seasonal/weekend/event/occupancy/competitor modifiers.
    """
    from apps.hotels.models import Property
    from apps.pricing.dynamic_engine import recompute_dynamic_prices_for_property

    properties = Property.objects.filter(
        status='approved', agreement_signed=True,
    ).only('id', 'name')

    total_updated = 0
    errors = 0

    for prop in properties:
        try:
            count = recompute_dynamic_prices_for_property(prop, days_ahead=30)
            total_updated += count
        except Exception as exc:
            errors += 1
            logger.error('Dynamic pricing failed for %s: %s', prop.name, exc)

    logger.info(
        'Dynamic pricing complete: %d rate updates across %d properties (%d errors)',
        total_updated, properties.count(), errors,
    )
    return {'updated': total_updated, 'properties': properties.count(), 'errors': errors}
