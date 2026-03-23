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


def _send_sms(phone, message, template_id=None, variables=None):
    """Send SMS via MSG91 with template support."""
    if not phone:
        return False
    try:
        from django.conf import settings as _s
        import requests as _req
        auth_key = getattr(_s, 'MSG91_AUTH_KEY', '')
        sender = getattr(_s, 'MSG91_SENDER_ID', 'ZYGOIN')

        if not auth_key:
            # Fallback to console
            from apps.accounts.sms_service import get_sms_backend
            return get_sms_backend().send(phone, message)

        mobile = str(phone).replace('+', '').replace(' ', '').replace('-', '')
        if not mobile.startswith('91') and len(mobile) == 10:
            mobile = '91' + mobile

        if template_id:
            url = 'https://control.msg91.com/api/v5/flow/'
            headers = {'authkey': auth_key, 'Content-Type': 'application/json'}
            recipient = {'mobiles': mobile}
            if variables:
                recipient.update(variables)
            payload = {'template_id': template_id, 'sender': sender, 'recipients': [recipient]}
            resp = _req.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            logger.info('MSG91 SMS to %s template=%s: %s', phone, template_id, data)
            return data.get('type') == 'success'
        else:
            from apps.accounts.sms_service import get_sms_backend
            return get_sms_backend().send(phone, message)
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

        # 2. Email to guest (HTML template + PDF invoice attachment)
        try:
            from apps.core.email_service import send_booking_confirmation as _html_conf
            from django.core.mail import EmailMultiAlternatives
            from django.template.loader import render_to_string
            from django.conf import settings as _cfg
            import mimetypes

            # Generate PDF invoice attachment
            pdf_bytes = None
            try:
                from apps.booking.invoice_pdf import get_invoice_pdf_bytes
                pdf_bytes = get_invoice_pdf_bytes(booking)
            except Exception as _pdf_err:
                logger.warning('PDF generation skipped for %s: %s', booking_ref, _pdf_err)

            if pdf_bytes:
                # Send with PDF attachment using EmailMultiAlternatives
                to_email = (
                    getattr(booking, 'guest_email', None)
                    or (booking.user.email if booking.user else '')
                )
                guest_nm = (
                    getattr(booking, 'guest_name', None)
                    or (booking.user.full_name if booking.user else 'Guest')
                )
                subject = f'Booking Confirmed - {booking_ref} | ZygoTrip'
                text_body = (
                    f"Hi {guest_nm},\n\n"
                    f"Your booking at {property_name} is confirmed!\n\n"
                    f"Booking ID: {booking_ref}\n"
                    f"Check-in: {booking.check_in}\n"
                    f"Check-out: {booking.check_out}\n"
                    f"Total: Rs{booking.total_amount}\n\n"
                    f"Your invoice PDF is attached to this email.\n\n"
                    f"Thank you for choosing ZygoTrip!"
                )
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=_cfg.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                )
                # Attach PDF
                filename = f'ZygoTrip_Invoice_{booking_ref}.pdf'
                msg.attach(filename, pdf_bytes, 'application/pdf')
                msg.send(fail_silently=False)
                logger.info('Confirmation email with PDF sent to %s for booking %s', to_email, booking_ref)
            else:
                # Fallback: send without PDF
                _html_conf(
                    to_email=booking.user.email,
                    booking_ref=str(booking_ref),
                    guest_name=booking.user.full_name or 'Guest',
                    hotel_name=property_name,
                    check_in=str(booking.check_in),
                    check_out=str(booking.check_out),
                    total_amount=str(booking.total_amount),
                    room_type=getattr(booking, 'room_type_name', '') or '',
                    guests=getattr(booking, 'adults', 1) or 1,
                )
        except Exception as _email_err:
            logger.error('HTML confirmation email failed for %s: %s', booking_ref, _email_err)

        # 3. SMS to guest
        sms_msg = f'ZygoTrip: Booking {booking_ref} at {property_name} is confirmed! Check-in: {booking.check_in}. Total: Rs{booking.total_amount}.'
        _send_sms(
            booking.user.phone, sms_msg,
            template_id=getattr(__import__('django.conf', fromlist=['settings']).settings, 'MSG91_BOOKING_TEMPLATE_ID', ''),
            variables={'booking_id': booking_ref, 'name': booking.user.full_name or 'Guest'},
        )

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
