"""
Email Service — transactional emails for booking lifecycle.

Sends emails for:
  - Booking confirmation
  - Booking cancellation
  - Payment receipt
  - OTP verification (optional)
  - Password reset
  - Welcome email

Uses Django's email framework. Backend is configured via EMAIL_BACKEND in settings.
Production: SMTP (Gmail, SES, SendGrid) or SendGrid API.
Development: Console backend (prints to stdout).
"""
import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger("zygotrip")


def _from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@zygotrip.com")


def send_booking_confirmation(
    to_email: str,
    booking_ref: str,
    guest_name: str,
    hotel_name: str,
    check_in: str,
    check_out: str,
    total_amount: str,
    room_type: str = "",
    guests: int = 1,
) -> bool:
    """Send booking confirmation email."""
    subject = f"Booking Confirmed — {booking_ref} | ZygoTrip"
    context = {
        "booking_ref": booking_ref,
        "guest_name": guest_name,
        "hotel_name": hotel_name,
        "check_in": check_in,
        "check_out": check_out,
        "total_amount": total_amount,
        "room_type": room_type,
        "guests": guests,
    }
    return _send_template_email(
        to_email=to_email,
        subject=subject,
        template="emails/booking_confirmation.html",
        context=context,
        fallback_text=(
            f"Hi {guest_name},\n\n"
            f"Your booking {booking_ref} at {hotel_name} is confirmed!\n\n"
            f"Check-in: {check_in}\n"
            f"Check-out: {check_out}\n"
            f"Room: {room_type}\n"
            f"Guests: {guests}\n"
            f"Total: {total_amount}\n\n"
            f"Thank you for choosing ZygoTrip!"
        ),
    )


def send_booking_cancellation(
    to_email: str,
    booking_ref: str,
    guest_name: str,
    hotel_name: str,
    refund_amount: str = "",
) -> bool:
    """Send booking cancellation email."""
    subject = f"Booking Cancelled — {booking_ref} | ZygoTrip"
    refund_text = f"\nRefund of {refund_amount} will be processed within 5-7 business days." if refund_amount else ""
    return _send_template_email(
        to_email=to_email,
        subject=subject,
        template="emails/booking_cancellation.html",
        context={
            "booking_ref": booking_ref,
            "guest_name": guest_name,
            "hotel_name": hotel_name,
            "refund_amount": refund_amount,
        },
        fallback_text=(
            f"Hi {guest_name},\n\n"
            f"Your booking {booking_ref} at {hotel_name} has been cancelled."
            f"{refund_text}\n\n"
            f"— ZygoTrip Team"
        ),
    )


def send_payment_receipt(
    to_email: str,
    booking_ref: str,
    guest_name: str,
    amount: str,
    payment_method: str = "",
    transaction_id: str = "",
) -> bool:
    """Send payment receipt email."""
    subject = f"Payment Receipt — {booking_ref} | ZygoTrip"
    return _send_template_email(
        to_email=to_email,
        subject=subject,
        template="emails/payment_receipt.html",
        context={
            "booking_ref": booking_ref,
            "guest_name": guest_name,
            "amount": amount,
            "payment_method": payment_method,
            "transaction_id": transaction_id,
        },
        fallback_text=(
            f"Hi {guest_name},\n\n"
            f"Payment of {amount} received for booking {booking_ref}.\n"
            f"Transaction ID: {transaction_id}\n\n"
            f"— ZygoTrip"
        ),
    )


def send_otp_email(to_email: str, otp_code: str, purpose: str = "login") -> bool:
    """Send OTP verification email."""
    subject = f"Your ZygoTrip Verification Code: {otp_code}"
    return _send_template_email(
        to_email=to_email,
        subject=subject,
        template="emails/otp_verification.html",
        context={"otp_code": otp_code, "purpose": purpose},
        fallback_text=(
            f"Your ZygoTrip verification code is: {otp_code}\n\n"
            f"This code expires in 5 minutes. Do not share it with anyone.\n\n"
            f"— ZygoTrip"
        ),
    )


def send_welcome_email(to_email: str, user_name: str) -> bool:
    """Send welcome email after registration."""
    subject = "Welcome to ZygoTrip!"
    return _send_template_email(
        to_email=to_email,
        subject=subject,
        template="emails/welcome.html",
        context={"user_name": user_name},
        fallback_text=(
            f"Hi {user_name},\n\n"
            f"Welcome to ZygoTrip! Start exploring hotels, buses, cabs, "
            f"and travel packages at the best prices.\n\n"
            f"— ZygoTrip Team"
        ),
    )


def _send_template_email(
    to_email: str,
    subject: str,
    template: str,
    context: dict,
    fallback_text: str,
) -> bool:
    """
    Send an email using a Django template with plain-text fallback.

    If the template doesn't exist, sends plain-text only.
    """
    try:
        try:
            html_content = render_to_string(template, context)
            text_content = strip_tags(html_content)
        except Exception:
            # Template doesn't exist — use fallback
            html_content = None
            text_content = fallback_text

        if html_content:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=_from_email(),
                to=[to_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
        else:
            send_mail(
                subject=subject,
                message=text_content,
                from_email=_from_email(),
                recipient_list=[to_email],
                fail_silently=False,
            )

        logger.info("Email sent: subject=%s to=%s", subject, to_email)
        return True

    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_refund_initiated(
    to_email: str,
    booking_ref: str,
    guest_name: str,
    refund_amount: str,
    days: int = 5,
) -> bool:
    """Send refund initiated notification."""
    subject = f'Refund of {refund_amount} Initiated — ZygoTrip'
    body = (
        f'Hi {guest_name},\n\n'
        f'Your refund of {refund_amount} for booking {booking_ref} has been initiated.\n'
        f'Expected processing time: {days} business days.\n\n'
        f'The amount will be credited to your original payment method.\n\n'
        f'Questions? Reply to this email or visit zygotrip.com/support\n\n'
        f'Team ZygoTrip'
    )
    try:
        send_mail(subject, body, _from_email(), [to_email], fail_silently=True)
        return True
    except Exception as exc:
        logger.exception('send_refund_initiated failed: %s', exc)
        return False


def send_booking_cancellation(
    to_email: str,
    booking_ref: str,
    guest_name: str,
    hotel_name: str,
    refund_amount: str = '',
    cancellation_reason: str = '',
) -> bool:
    """Send booking cancellation confirmation."""
    subject = f'Booking Cancelled — {booking_ref} | ZygoTrip'
    body = (
        f'Hi {guest_name},\n\n'
        f'Your booking {booking_ref} at {hotel_name} has been cancelled.\n'
    )
    if refund_amount:
        body += f'Refund amount: {refund_amount} (processed in 3-5 business days)\n'
    if cancellation_reason:
        body += f'Reason: {cancellation_reason}\n'
    body += '\nTeam ZygoTrip'
    try:
        send_mail(subject, body, _from_email(), [to_email], fail_silently=True)
        return True
    except Exception as exc:
        logger.exception('send_booking_cancellation failed: %s', exc)
        return False


def send_welcome_email(to_email: str, full_name: str) -> bool:
    """Send welcome email to new user."""
    subject = 'Welcome to ZygoTrip! 🎉'
    body = (
        f'Hi {full_name},\n\n'
        f'Welcome to ZygoTrip! Discover amazing hotels, flights and buses across India.\n\n'
        f'Start exploring: https://zygotrip.com\n\n'
        f'Happy travels!\nTeam ZygoTrip'
    )
    try:
        send_mail(subject, body, _from_email(), [to_email], fail_silently=True)
        return True
    except Exception as exc:
        logger.exception('send_welcome_email failed: %s', exc)
        return False
