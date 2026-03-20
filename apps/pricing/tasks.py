import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='apps.pricing.tasks.recalculate_all_dynamic_prices')
def recalculate_all_dynamic_prices():
    from apps.hotels.models import Property
    from apps.pricing.dynamic_pricing import DemandPricingService
    from apps.pricing.models import DynamicPriceCache

    service = DemandPricingService()
    now = timezone.now()
    DynamicPriceCache.objects.filter(calculated_at__lt=now - timedelta(hours=4)).delete()

    total = 0
    for prop in Property.objects.filter(is_active=True).prefetch_related('room_types'):
        for room_type in prop.room_types.all():
            for day in range(0, 30):
                target_date = timezone.localdate() + timedelta(days=day)
                try:
                    service.get_dynamic_price(prop.id, room_type.id, target_date)
                    total += 1
                except Exception as exc:
                    logger.exception(
                        'Dynamic pricing recompute failed property=%s room=%s date=%s err=%s',
                        prop.id,
                        room_type.id,
                        target_date,
                        exc,
                    )

    return {'recalculated': total}
