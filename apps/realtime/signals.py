"""Realtime signals for booking status updates."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.booking.models import Booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def booking_status_update(sender, instance, created, **kwargs):
    if created:
        return

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    group_name = f"booking_{instance.public_booking_id}"
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'booking.update',
                'status': instance.status,
                'updated_at': instance.updated_at.isoformat(),
                'message': f'Booking status updated to {instance.status}',
            },
        )
    except Exception as exc:
        # Realtime notifications are best-effort; never break booking writes.
        logger.warning('booking_status_update skipped: %s', exc)
