"""
Notification System — Multi-channel notifications (Email, SMS, In-App).

Supports:
  - Booking confirmation (email + SMS + in-app)
  - Payment receipt (email + in-app)
  - Cancellation confirmation (email + SMS + in-app)
  - OTP delivery (SMS — handled separately in sms_service.py)
  - Owner payout notifications (email + in-app)

All notifications are dispatched asynchronously via Celery.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.notifications')


class Notification(TimeStampedModel):
    """
    In-app notification record.
    Frontend polls /api/v1/notifications/ for unread notifications.
    """
    CATEGORY_BOOKING = 'booking'
    CATEGORY_PAYMENT = 'payment'
    CATEGORY_CANCELLATION = 'cancellation'
    CATEGORY_PAYOUT = 'payout'
    CATEGORY_PROMO = 'promo'
    CATEGORY_SYSTEM = 'system'

    CATEGORY_CHOICES = [
        (CATEGORY_BOOKING, 'Booking'),
        (CATEGORY_PAYMENT, 'Payment'),
        (CATEGORY_CANCELLATION, 'Cancellation'),
        (CATEGORY_PAYOUT, 'Payout'),
        (CATEGORY_PROMO, 'Promo'),
        (CATEGORY_SYSTEM, 'System'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(blank=True, null=True, help_text='Structured payload for frontend routing')
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at'], name='notif_user_unread_idx'),
        ]

    def __str__(self):
        return f"[{self.category}] {self.title} → {self.user.email}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])


# ===========================================================================
# Notification Dispatcher (delegates to Celery tasks)
# ===========================================================================

def notify_booking_confirmed(booking):
    """
    Trigger booking confirmation notifications:
      - Email to guest
      - SMS to guest phone
      - In-app notification
      - Email to property owner
    """
    from apps.core.notification_tasks import (
        send_booking_confirmation_notification,
    )
    send_booking_confirmation_notification.delay(booking.id)


def notify_payment_received(booking, transaction_id, amount):
    """Trigger payment receipt notification."""
    from apps.core.notification_tasks import send_payment_notification
    send_payment_notification.delay(booking.id, transaction_id, str(amount))


def notify_booking_cancelled(booking, refund_amount=None):
    """Trigger cancellation notification."""
    from apps.core.notification_tasks import send_cancellation_notification
    send_cancellation_notification.delay(
        booking.id, str(refund_amount or Decimal('0')),
    )


def notify_owner_payout(owner, amount, booking_count):
    """Trigger owner payout notification."""
    from apps.core.notification_tasks import send_owner_payout_notification
    send_owner_payout_notification.delay(owner.id, str(amount), booking_count)
