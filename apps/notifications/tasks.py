"""Celery tasks for scheduled push notifications."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_checkin_reminders():
    from apps.booking.models import Booking
    from apps.notifications.fcm_service import FCMService

    tomorrow = timezone.localdate() + timedelta(days=1)
    bookings = Booking.objects.filter(
        check_in=tomorrow,
        status=Booking.STATUS_CONFIRMED,
    ).select_related('user', 'property')

    service = FCMService()
    sent_count = 0
    for booking in bookings:
        if not booking.user_id:
            continue
        try:
            service.check_in_reminder(booking)
            sent_count += 1
        except Exception as exc:
            logger.exception('Failed check-in reminder for booking=%s: %s', booking.id, exc)
    return {'date': str(tomorrow), 'sent': sent_count}


@shared_task
def send_check_in_reminders():
    return send_checkin_reminders()


@shared_task
def send_checkout_reminders():
    """Daily 8am: send checkout reminder to guests checking out today."""
    from apps.booking.models import Booking
    from apps.notifications.templates import checkout_reminder

    today = timezone.now().date()
    bookings = Booking.objects.filter(
        check_out=today,
        status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_CHECKED_IN],
        user__isnull=False,
    ).select_related('user', 'property')

    sent = 0
    for booking in bookings:
        try:
            checkout_reminder(booking)
            sent += 1
        except Exception as exc:
            logger.warning('checkout_reminder failed booking=%s err=%s', booking.uuid, exc)

    logger.info('checkout_reminders sent: %d for today=%s', sent, today)
    return {'sent': sent}


@shared_task
def watch_price_drops():
    """
    Price watcher: compares current price vs 7-day average.
    Fires price_drop_alert if today's price is >10% below average.
    """
    from apps.hotels.models import Property
    from apps.pricing.pricing_service import calculate_from_amounts
    from apps.notifications.templates import price_drop_alert
    from apps.rooms.models import RoomInventory
    import datetime

    today = timezone.now().date()
    fired = 0

    for prop in Property.objects.filter(is_active=True)[:200]:
        try:
            inv = RoomInventory.objects.filter(
                room_type__property=prop,
                date=today,
                available_rooms__gt=0,
            ).first()
            if not inv:
                continue

            current_price = float(inv.price_override or inv.room_type.base_price)

            # Calculate 7-day average
            week_prices = list(RoomInventory.objects.filter(
                room_type__property=prop,
                date__gte=today - datetime.timedelta(days=7),
                date__lt=today,
            ).values_list('price_override', flat=True))

            if not week_prices:
                continue

            avg_price = sum(float(p or 0) for p in week_prices) / len(week_prices)
            if avg_price > 0 and current_price < avg_price * 0.90:
                price_drop_alert(prop, avg_price, current_price)
                fired += 1
        except Exception as exc:
            logger.debug('price_watcher: prop=%s err=%s', prop.id, exc)

    logger.info('price_drop_alerts fired: %d', fired)
    return {'alerts_fired': fired}
