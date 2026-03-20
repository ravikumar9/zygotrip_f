"""Demand-based dynamic pricing service."""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.pricing.models import DynamicPriceCache

logger = logging.getLogger(__name__)

HOLIDAY_LIST = {
    '2026-01-01',
    '2026-01-14',
    '2026-01-26',
    '2026-03-25',
    '2026-08-15',
    '2026-10-20',
    '2026-11-12',
}


class DemandPricingService:
    def get_occupancy_rate(self, property_id, target_date):
        from apps.booking.models import Booking
        from apps.rooms.models import RoomType

        total_rooms = RoomType.objects.filter(property_id=property_id).count()
        if total_rooms <= 0:
            return Decimal('0.00')

        confirmed = Booking.objects.filter(
            property_id=property_id,
            status=Booking.STATUS_CONFIRMED,
            check_in__lte=target_date,
            check_out__gt=target_date,
        ).count()
        return Decimal(str(confirmed / total_rooms))

    def calculate_multiplier(self, property_id, target_date):
        if isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)

        multiplier = Decimal('1.00')
        occupancy = self.get_occupancy_rate(property_id, target_date)

        if occupancy > Decimal('0.85'):
            multiplier *= Decimal('1.25')
        elif occupancy > Decimal('0.70'):
            multiplier *= Decimal('1.15')

        if occupancy < Decimal('0.15'):
            multiplier *= Decimal('0.75')
        elif occupancy < Decimal('0.30'):
            multiplier *= Decimal('0.85')

        if target_date.weekday() in (4, 5):
            multiplier *= Decimal('1.08')

        if target_date.isoformat() in HOLIDAY_LIST:
            multiplier *= Decimal('1.20')

        days_until_checkin = (target_date - timezone.localdate()).days
        if days_until_checkin < 2:
            multiplier *= Decimal('1.15')
        if days_until_checkin > 60:
            multiplier *= Decimal('0.90')

        if multiplier < Decimal('0.70'):
            multiplier = Decimal('0.70')
        if multiplier > Decimal('1.50'):
            multiplier = Decimal('1.50')
        return multiplier.quantize(Decimal('0.001'))

    def get_dynamic_price(self, property_id, room_type_id, target_date):
        from apps.rooms.models import RoomInventory, RoomType

        if isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)

        cache_cutoff = timezone.now() - timedelta(hours=4)
        cache = DynamicPriceCache.objects.filter(
            property_id=property_id,
            room_type_id=room_type_id,
            date=target_date,
            calculated_at__gte=cache_cutoff,
        ).first()
        if cache:
            return cache.dynamic_price

        room_type = RoomType.objects.get(id=room_type_id, property_id=property_id)
        inventory = RoomInventory.objects.filter(room_type_id=room_type_id, date=target_date).first()
        base_price = Decimal(str((inventory.price if inventory and inventory.price else room_type.base_price) or 0))
        multiplier = self.calculate_multiplier(property_id, target_date)
        dynamic_price = (base_price * multiplier)
        dynamic_price = (dynamic_price / Decimal('50')).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * Decimal('50')

        DynamicPriceCache.objects.update_or_create(
            property_id=property_id,
            room_type_id=room_type_id,
            date=target_date,
            defaults={
                'multiplier': multiplier,
                'base_price': base_price,
                'dynamic_price': dynamic_price,
                'calculated_at': timezone.now(),
            },
        )
        return dynamic_price
