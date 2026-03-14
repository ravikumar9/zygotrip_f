"""
Security Hardening Utilities — Webhook verification, audit logging, input sanitization.

Extends the existing security stack with:
  - Payment webhook signature verification (Cashfree, Stripe, Razorpay)
  - Security event audit logging
  - Request sanitization helpers
"""
import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from functools import wraps

logger = logging.getLogger('zygotrip.security')


# ── Webhook Signature Verification ──

class WebhookVerifier:
    """
    Verifies webhook signatures from payment gateways.
    Prevents replay attacks and tampering.
    """

    @staticmethod
    def verify_cashfree(payload_bytes: bytes, signature: str) -> bool:
        """Verify Cashfree webhook signature (HMAC-SHA256)."""
        secret = getattr(settings, 'CASHFREE_WEBHOOK_SECRET', '')
        if not secret:
            logger.error('CASHFREE_WEBHOOK_SECRET not configured')
            return False

        expected = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_stripe(payload_bytes: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature (v1 scheme)."""
        secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if not secret:
            logger.error('STRIPE_WEBHOOK_SECRET not configured')
            return False

        # Stripe signature format: t=timestamp,v1=signature
        parts = {}
        for item in signature.split(','):
            key, _, val = item.partition('=')
            parts[key.strip()] = val.strip()

        timestamp = parts.get('t', '')
        sig = parts.get('v1', '')

        if not timestamp or not sig:
            return False

        # Reject if older than 5 minutes (replay protection)
        try:
            if abs(time.time() - int(timestamp)) > 300:
                logger.warning('Stripe webhook timestamp too old')
                return False
        except ValueError:
            return False

        signed_payload = f'{timestamp}.'.encode() + payload_bytes
        expected = hmac.new(
            secret.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

    @staticmethod
    def verify_razorpay(payload_bytes: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature (HMAC-SHA256)."""
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        if not secret:
            logger.error('RAZORPAY_WEBHOOK_SECRET not configured')
            return False

        expected = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def require_webhook_signature(gateway: str):
    """
    Decorator for webhook views that verifies the request signature.
    Usage: @require_webhook_signature('cashfree')
    """
    verifiers = {
        'cashfree': ('X-Cashfree-Signature', WebhookVerifier.verify_cashfree),
        'stripe': ('Stripe-Signature', WebhookVerifier.verify_stripe),
        'razorpay': ('X-Razorpay-Signature', WebhookVerifier.verify_razorpay),
    }

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            header_name, verify_fn = verifiers.get(gateway, (None, None))
            if not verify_fn:
                logger.error('Unknown webhook gateway: %s', gateway)
                return HttpResponseForbidden('Invalid gateway')

            signature = request.META.get(
                f'HTTP_{header_name.upper().replace("-", "_")}', ''
            )
            if not signature:
                log_security_event('webhook_missing_signature', request, {
                    'gateway': gateway,
                })
                return HttpResponseForbidden('Missing signature')

            if not verify_fn(request.body, signature):
                log_security_event('webhook_invalid_signature', request, {
                    'gateway': gateway,
                })
                return HttpResponseForbidden('Invalid signature')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ── Security Event Audit Logging ──

def log_security_event(event_type: str, request=None, details=None):
    """
    Log security-relevant events for audit trail and alerting.
    Sends to both structured log and database.
    """
    details = details or {}

    event = {
        'event_type': event_type,
        'timestamp': timezone.now().isoformat(),
        'ip': _get_client_ip(request) if request else None,
        'user_id': getattr(request, 'user', None) and request.user.pk if request else None,
        'path': request.path if request else None,
        'method': request.method if request else None,
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200] if request else None,
        **details,
    }

    # Structured log (picked up by ELK/CloudWatch)
    logger.warning('SECURITY_EVENT: %s %s', event_type, event)

    # Persist critical events to DB
    critical_events = {
        'login_failed', 'brute_force_detected', 'webhook_invalid_signature',
        'rate_limit_exceeded', 'blocked_ip_attempt', 'suspicious_booking',
        'admin_action', 'permission_denied',
    }

    if event_type in critical_events:
        try:
            from apps.dashboard_admin.models import AuditLog
            AuditLog.objects.create(
                actor_id=event.get('user_id'),
                action=event_type,
                object_type='security_event',
                object_id=str(details.get('object_id', '')),
                metadata=event,
            )
        except Exception:
            pass  # Don't break the request for audit log failures


def _get_client_ip(request):
    """Extract real client IP, respecting X-Forwarded-For behind proxy."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ── Payment Amount Verification ──

def verify_payment_amount(booking, payment_amount, tolerance_pct=1.0):
    """
    Verify that the payment amount matches the booking amount.
    Allows a small tolerance for rounding differences.
    Returns (is_valid, message).
    """
    expected = float(booking.gross_amount or 0)
    actual = float(payment_amount)

    if expected == 0:
        return False, 'Booking amount is zero'

    diff_pct = abs(actual - expected) / expected * 100

    if diff_pct > tolerance_pct:
        log_security_event('payment_amount_mismatch', details={
            'booking_id': booking.id,
            'expected': expected,
            'actual': actual,
            'diff_pct': round(diff_pct, 2),
        })
        return False, f'Amount mismatch: expected {expected}, got {actual}'

    return True, 'OK'
