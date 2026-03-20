"""Hook loyalty points earning into booking confirmation."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('zygotrip.loyalty.signals')


def _register_booking_confirmed_signal():
    try:
        from apps.booking.models import Booking

        @receiver(post_save, sender=Booking)
        def award_points_on_confirmation(sender, instance, created, **kwargs):
            if instance.status == Booking.STATUS_CONFIRMED:
                # Only award once — check if already awarded
                try:
                    from apps.loyalty.models import PointsTransaction
                    already_awarded = PointsTransaction.objects.filter(
                        booking=instance,
                        transaction_type=PointsTransaction.TYPE_EARNED,
                    ).exists()
                    if not already_awarded:
                        from apps.loyalty.services import earn_points_for_booking
                        earn_points_for_booking(instance)
                except Exception as exc:
                    logger.warning('award_points signal failed: booking=%s err=%s', instance.uuid, exc)

    except Exception as exc:
        logger.warning('loyalty signal registration failed: %s', exc)


_register_booking_confirmed_signal()
