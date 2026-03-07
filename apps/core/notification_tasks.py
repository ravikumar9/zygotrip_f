"""
Notification Celery Tasks — Async multi-channel notification delivery.

Tasks are called via .delay() from the notification dispatcher.
Each task handles: in-app record creation, email sending, and SMS delivery.
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger('zygotrip.notifications')


def _create_in_app(user, category, title, message, data=None):
    """Create an in-app notification record."""
    Notification = apps.get_model('core', 'Notification')
    return Notification.objects.create(
        user=user,
        category=category,
        title=title,
        message=message,
        data=data,
    )


def _send_email(to_email, subject, text_body, html_body=None):
    """Send an email, logging failures."""
    try:
        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_body,
            fail_silently=False,
        )
        logger.info('Email sent to %s: %s', to_email, subject)
        return True
    except Exception as e:
        logger.error('Email failed to %s: %s', to_email, e)
        return False


def _send_sms(phone, message):
    """Send SMS via configured backend."""
    if not phone:
        return False
    try:
        from apps.accounts.sms_service import get_sms_backend
        backend = get_sms_backend()
        return backend.send(phone, message)
    except Exception as e:
        logger.error('SMS failed to %s: %s', phone, e)
        return False


@shared_task(bind=True, max_retries=3)
def send_booking_confirmation_notification(self, booking_id):
    """
    Multi-channel booking confirmation:
      1. In-app notification for guest
      2. Email to guest
      3. SMS to guest phone
      4. In-app notification for property owner
    """
    try:
        Booking = apps.get_model('booking', 'Booking')
        booking = Booking.objects.select_related('user', 'property', 'property__owner').get(id=booking_id)

        property_name = booking.property.name if booking.property else 'N/A'
        booking_ref = booking.public_booking_id or str(booking.uuid)

        # 1. In-app for guest
        _create_in_app(
            user=booking.user,
            category='booking',
            title='Booking Confirmed! 🎉',
            message=f'Your booking at {property_name} ({booking_ref}) has been confirmed.',
            data={
                'booking_uuid': str(booking.uuid),
                'property_name': property_name,
                'action': 'view_booking',
            },
        )

        # 2. Email to guest
        email_body = (
            f"Dear {booking.user.full_name},\n\n"
            f"Your booking has been confirmed!\n\n"
            f"Booking ID: {booking_ref}\n"
            f"Property: {property_name}\n"
            f"Check-in: {booking.check_in}\n"
            f"Check-out: {booking.check_out}\n"
            f"Total: ₹{booking.total_amount}\n\n"
            f"You can view your booking details in your ZygoTrip dashboard.\n\n"
            f"Have a great stay!\n"
            f"— Team ZygoTrip"
        )
        _send_email(
            booking.user.email,
            f'Booking Confirmed — {booking_ref} at {property_name}',
            email_body,
        )

        # 3. SMS to guest
        sms_msg = (
            f'ZygoTrip: Booking {booking_ref} at {property_name} is confirmed! '
            f'Check-in: {booking.check_in}. Total: Rs{booking.total_amount}.'
        )
        _send_sms(booking.user.phone, sms_msg)

        # 4. Notify property owner
        if booking.property and hasattr(booking.property, 'owner') and booking.property.owner:
            _create_in_app(
                user=booking.property.owner,
                category='booking',
                title='New Booking Received 📋',
                message=f'Guest {booking.user.full_name} booked {property_name} ({booking.check_in} → {booking.check_out}). Amount: ₹{booking.total_amount}.',
                data={
                    'booking_uuid': str(booking.uuid),
                    'action': 'owner_view_booking',
                },
            )

        logger.info('Booking confirmation notifications sent for %s', booking_ref)
        return {'status': 'sent', 'booking_id': booking_id}

    except Exception as exc:
        logger.error('Failed to send booking notifications for %s: %s', booking_id, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_payment_notification(self, booking_id, transaction_id, amount_str):
    """Payment receipt notification — email + in-app."""
    try:
        Booking = apps.get_model('booking', 'Booking')
        booking = Booking.objects.select_related('user', 'property').get(id=booking_id)
        amount = Decimal(amount_str)
        booking_ref = booking.public_booking_id or str(booking.uuid)
        property_name = booking.property.name if booking.property else 'N/A'

        _create_in_app(
            user=booking.user,
            category='payment',
            title='Payment Received ✅',
            message=f'₹{amount} payment for {property_name} ({booking_ref}) was successful. Transaction: {transaction_id}.',
            data={
                'booking_uuid': str(booking.uuid),
                'transaction_id': transaction_id,
                'action': 'view_booking',
            },
        )

        email_body = (
            f"Dear {booking.user.full_name},\n\n"
            f"We've received your payment of ₹{amount}.\n\n"
            f"Transaction ID: {transaction_id}\n"
            f"Booking: {booking_ref}\n"
            f"Property: {property_name}\n\n"
            f"Thank you for choosing ZygoTrip!\n"
            f"— Team ZygoTrip"
        )
        _send_email(
            booking.user.email,
            f'Payment Received — ₹{amount} for {booking_ref}',
            email_body,
        )

        logger.info('Payment notification sent for booking %s, txn %s', booking_ref, transaction_id)
        return {'status': 'sent', 'booking_id': booking_id}

    except Exception as exc:
        logger.error('Payment notification failed for %s: %s', booking_id, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_cancellation_notification(self, booking_id, refund_amount_str):
    """Cancellation notification — email + SMS + in-app."""
    try:
        Booking = apps.get_model('booking', 'Booking')
        booking = Booking.objects.select_related('user', 'property').get(id=booking_id)
        refund = Decimal(refund_amount_str)
        booking_ref = booking.public_booking_id or str(booking.uuid)
        property_name = booking.property.name if booking.property else 'N/A'

        refund_msg = f' Refund of ₹{refund} will be processed within 5-7 business days.' if refund > 0 else ''

        _create_in_app(
            user=booking.user,
            category='cancellation',
            title='Booking Cancelled',
            message=f'Your booking at {property_name} ({booking_ref}) has been cancelled.{refund_msg}',
            data={
                'booking_uuid': str(booking.uuid),
                'refund_amount': str(refund),
                'action': 'view_booking',
            },
        )

        email_body = (
            f"Dear {booking.user.full_name},\n\n"
            f"Your booking has been cancelled.\n\n"
            f"Booking: {booking_ref}\n"
            f"Property: {property_name}\n"
            f"{f'Refund: ₹{refund} (5-7 business days)' if refund > 0 else 'No refund applicable per cancellation policy.'}\n\n"
            f"If you need assistance, contact our support team.\n\n"
            f"— Team ZygoTrip"
        )
        _send_email(
            booking.user.email,
            f'Booking Cancelled — {booking_ref}',
            email_body,
        )

        sms_msg = f'ZygoTrip: Booking {booking_ref} cancelled.{" Refund Rs" + str(refund) + " in 5-7 days." if refund > 0 else ""}'
        _send_sms(booking.user.phone, sms_msg)

        logger.info('Cancellation notifications sent for %s', booking_ref)
        return {'status': 'sent', 'booking_id': booking_id}

    except Exception as exc:
        logger.error('Cancellation notification failed for %s: %s', booking_id, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_owner_payout_notification(self, owner_id, amount_str, booking_count):
    """Owner payout notification — email + in-app."""
    try:
        User = apps.get_model('accounts', 'User')
        owner = User.objects.get(id=owner_id)
        amount = Decimal(amount_str)

        _create_in_app(
            user=owner,
            category='payout',
            title='Payout Processed 💰',
            message=f'₹{amount} has been transferred to your bank for {booking_count} booking(s).',
            data={'action': 'owner_dashboard'},
        )

        email_body = (
            f"Dear {owner.full_name},\n\n"
            f"A payout of ₹{amount} has been initiated for {booking_count} booking(s).\n"
            f"It will reflect in your bank account within 2-3 business days.\n\n"
            f"— Team ZygoTrip"
        )
        _send_email(
            owner.email,
            f'Payout Processed — ₹{amount}',
            email_body,
        )

        logger.info('Payout notification sent to owner %s: ₹%s', owner.email, amount)
        return {'status': 'sent', 'owner_id': owner_id}

    except Exception as exc:
        logger.error('Payout notification failed for %s: %s', owner_id, exc)
        raise self.retry(exc=exc, countdown=60)
