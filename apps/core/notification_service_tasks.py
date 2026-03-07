"""
Celery tasks for the Notification Service.

Handles async dispatch of all notification channels with retry logic.
"""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.notification_service')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    name='core.send_notification',
)
def send_notification_task(self, event_type, channel, user_id, context):
    """
    Async notification send for a single channel.

    Args:
        event_type: str event identifier
        channel: 'email' | 'sms' | 'push' | 'webhook' | 'inapp'
        user_id: user PK or None
        context: dict with template variables + recipient info
    """
    from django.contrib.auth import get_user_model
    from apps.core.notification_service import NotificationService, NotificationTemplate

    User = get_user_model()
    user = None
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('User %s not found for notification', user_id)
            return

    # Render template if available
    template = NotificationTemplate.objects.filter(
        event_type=event_type, channel=channel, is_enabled=True,
    ).first()

    if template:
        rendered = template.render(context)
        subject = rendered['subject']
        body = rendered['body']
    else:
        subject = context.get('subject', event_type.replace('_', ' ').title())
        body = context.get('body', context.get('message', ''))

    try:
        if channel == 'email':
            recipient = context.get('email') or (user.email if user else None)
            if recipient:
                NotificationService.send_email(recipient, subject, body, user, event_type)

        elif channel == 'sms':
            phone = context.get('phone') or (getattr(user, 'phone', None) if user else None)
            if phone:
                NotificationService.send_sms(phone, body, user, event_type)

        elif channel == 'push':
            if user:
                NotificationService.send_push(user, subject, body,
                                              data=context.get('data'), event_type=event_type)

        elif channel == 'webhook':
            payload = {
                'event': event_type,
                'data': context.get('data', context),
                'timestamp': context.get('timestamp'),
            }
            NotificationService.send_webhook(event_type, payload)

        elif channel == 'inapp':
            if user:
                NotificationService.send_inapp(user, event_type, subject, body,
                                               data=context.get('data'))

    except Exception as exc:
        logger.error('Notification task failed: %s channel=%s: %s', event_type, channel, exc)
        raise self.retry(exc=exc)


@shared_task(name='core.process_webhook_batch')
def process_webhook_batch(event_type, payload, owner_id=None):
    """Batch webhook dispatch for an event."""
    from django.contrib.auth import get_user_model
    from apps.core.notification_service import NotificationService

    User = get_user_model()
    owner = None
    if owner_id:
        try:
            owner = User.objects.get(pk=owner_id)
        except User.DoesNotExist:
            pass

    NotificationService.send_webhook(event_type, payload, owner=owner)


@shared_task(name='core.cleanup_old_deliveries')
def cleanup_old_deliveries(days=90):
    """Remove delivery records older than N days."""
    from django.utils import timezone
    from apps.core.notification_service import NotificationDelivery

    cutoff = timezone.now() - __import__('datetime').timedelta(days=days)
    deleted, _ = NotificationDelivery.objects.filter(created_at__lt=cutoff).delete()
    logger.info('Cleaned up %d old notification delivery records', deleted)


@shared_task(name='core.send_checkin_reminders')
def send_checkin_reminders():
    """Send check-in reminders for bookings arriving tomorrow."""
    from django.utils import timezone
    from apps.booking.models import Booking
    from apps.core.notification_service import NotificationService

    tomorrow = (timezone.now() + __import__('datetime').timedelta(days=1)).date()
    bookings = Booking.objects.filter(
        check_in=tomorrow,
        status='confirmed',
    ).select_related('user', 'property')

    for booking in bookings:
        NotificationService.notify(
            event_type='checkin_reminder',
            user=booking.user,
            context={
                'booking_id': str(booking.booking_id),
                'property_name': booking.property.name if booking.property else '',
                'check_in': str(booking.check_in),
                'email': booking.user.email if booking.user else '',
                'subject': 'Check-in Tomorrow',
                'body': f'Your check-in at {booking.property.name if booking.property else "your hotel"} '
                        f'is tomorrow ({booking.check_in}). Booking: {booking.booking_id}',
            },
            channels=['email', 'push', 'inapp'],
        )

    logger.info('Sent %d check-in reminders', bookings.count())
