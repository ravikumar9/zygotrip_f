"""
System 2 Enhancement — Price Lock TTL Enforcement.

Celery tasks to:
  1. Expire stale price locks on BookingContext
  2. Detect price changes between lock time and conversion time
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('zygotrip.price_lock')


@shared_task(name='booking.expire_stale_price_locks')
def expire_stale_price_locks():
    """
    Expire BookingContexts whose price_expires_at has passed.
    Sets price_locked=False, context_status='expired'.
    Runs every 2 minutes via Celery Beat.
    """
    from apps.booking.models import BookingContext

    now = timezone.now()
    stale = BookingContext.objects.filter(
        price_locked=True,
        context_status=BookingContext.STATUS_ACTIVE,
        price_expires_at__lt=now,
    )

    count = stale.update(
        price_locked=False,
        context_status=BookingContext.STATUS_EXPIRED,
    )

    if count:
        logger.info('Expired %d stale price locks', count)
    return {'expired': count}


@shared_task(name='booking.expire_abandoned_contexts')
def expire_abandoned_contexts():
    """
    Expire BookingContexts that have been active for over 30 minutes
    without being converted, even if price_expires_at is not set.
    Runs every 5 minutes.
    """
    from apps.booking.models import BookingContext

    cutoff = timezone.now() - timedelta(minutes=30)
    stale = BookingContext.objects.filter(
        context_status=BookingContext.STATUS_ACTIVE,
        booking__isnull=True,
        created_at__lt=cutoff,
    )

    count = stale.update(context_status=BookingContext.STATUS_ABANDONED)
    if count:
        logger.info('Abandoned %d stale booking contexts', count)
    return {'abandoned': count}


def verify_price_at_conversion(booking_context):
    """
    Called during hold→booking conversion to detect price drift.
    Compares locked price against current live price.

    Returns:
        dict with:
          - price_valid: bool
          - locked_price: Decimal
          - current_price: Decimal or None
          - drift_pct: float (absolute percentage difference)
    """
    from apps.pricing.pricing_service import PricingService

    locked = booking_context.locked_price
    if not locked or not booking_context.price_locked:
        return {'price_valid': True, 'locked_price': locked, 'current_price': None, 'drift_pct': 0}

    # Check TTL
    if booking_context.price_expires_at and booking_context.price_expires_at < timezone.now():
        logger.warning(
            'Price lock expired: context=%s expired_at=%s',
            booking_context.uuid, booking_context.price_expires_at,
        )
        return {
            'price_valid': False,
            'locked_price': locked,
            'current_price': None,
            'drift_pct': 0,
            'reason': 'price_lock_expired',
        }

    # Recalculate current price
    try:
        current = PricingService.calculate(
            property_id=booking_context.property_id,
            room_type_id=booking_context.room_type_id,
            checkin=booking_context.checkin,
            checkout=booking_context.checkout,
            adults=booking_context.adults,
            children=booking_context.children,
            rooms=booking_context.rooms,
            meal_plan=booking_context.meal_plan or '',
            promo_code=booking_context.promo_code or '',
        )
        current_price = current.get('final_price') or current.get('total')
    except Exception as exc:
        logger.warning('Price recalculation failed: %s', exc)
        # If we can't recalculate, honor the locked price (benefit of doubt)
        return {'price_valid': True, 'locked_price': locked, 'current_price': None, 'drift_pct': 0}

    if current_price is None:
        return {'price_valid': True, 'locked_price': locked, 'current_price': None, 'drift_pct': 0}

    from decimal import Decimal
    current_price = Decimal(str(current_price))
    drift = abs(current_price - locked) / max(locked, Decimal('1'))
    drift_pct = float(drift * 100)

    # Allow up to 5% drift (covers minor tax rounding etc.)
    MAX_DRIFT_PCT = 5.0
    price_valid = drift_pct <= MAX_DRIFT_PCT

    if not price_valid:
        logger.warning(
            'Price drift detected: context=%s locked=%s current=%s drift=%.1f%%',
            booking_context.uuid, locked, current_price, drift_pct,
        )

    return {
        'price_valid': price_valid,
        'locked_price': locked,
        'current_price': current_price,
        'drift_pct': round(drift_pct, 2),
    }
