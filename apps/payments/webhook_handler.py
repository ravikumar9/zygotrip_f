"""
Idempotent Payment Webhook Handler.

Guarantees at-most-once processing of gateway webhook events.

Model:  PaymentWebhookEvent  — unique per (gateway, event_id)
Flow:   receive → HMAC verify → idempotency check → process → confirm booking

Supported gateways:
  - cashfree (X-Webhook-Signature header, SHA256 HMAC)
  - stripe    (Stripe-Signature header, standard Stripe webhook verification)
  - paytm_upi (X-Paytm-Checksum header, Paytm checksum verification)

Usage (in URL conf):
    path('webhooks/cashfree/',  cashfree_webhook,  name='webhook-cashfree'),
    path('webhooks/stripe/',    stripe_webhook,    name='webhook-stripe'),
    path('webhooks/paytm/',     paytm_upi_webhook, name='webhook-paytm'),
"""
import hashlib
import hmac
import json
import logging
import time
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.payments.webhook')


# ============================================================================
# PaymentWebhookEvent model
# ============================================================================

class PaymentWebhookEvent(TimeStampedModel):
    """
    Immutable record of each gateway webhook event.

    Unique constraint on (gateway, event_id) ensures idempotency:
    duplicate webhook deliveries are detected instantly and discarded
    without re-processing.
    """

    GATEWAY_CHOICES = [
        ('cashfree',  'Cashfree'),
        ('stripe',    'Stripe'),
        ('paytm_upi', 'Paytm UPI'),
        ('wallet',    'ZygoTrip Wallet'),
    ]

    STATUS_RECEIVED   = 'received'
    STATUS_PROCESSING = 'processing'
    STATUS_PROCESSED  = 'processed'
    STATUS_FAILED     = 'failed'
    STATUS_IGNORED    = 'ignored'

    STATUS_CHOICES = [
        (STATUS_RECEIVED,   'Received'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PROCESSED,  'Processed'),
        (STATUS_FAILED,     'Failed'),
        (STATUS_IGNORED,    'Ignored (duplicate/unsupported event)'),
    ]

    gateway  = models.CharField(max_length=20, choices=GATEWAY_CHOICES, db_index=True)
    # Gateway-assigned event ID (e.g. Cashfree orderId, Stripe event.id)
    event_id = models.CharField(max_length=255, db_index=True)

    event_type    = models.CharField(max_length=100, blank=True, db_index=True)
    raw_payload   = models.JSONField()
    signature     = models.CharField(max_length=512, blank=True)
    signature_ok  = models.BooleanField(default=False)

    status        = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED,
    )
    # Link to our transaction once resolved.
    # related_name uses 'gateway_webhook_events' to avoid clash with
    # checkout.PaymentWebhook which already owns 'webhook_events'.
    transaction   = models.ForeignKey(
        'payments.PaymentTransaction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gateway_webhook_events',
    )
    error_detail  = models.TextField(blank=True)
    processed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'payments'
        # Core idempotency constraint
        unique_together = [('gateway', 'event_id')]
        indexes = [
            models.Index(fields=['gateway', 'status'],   name='whe_gw_status_idx'),
            models.Index(fields=['event_type'],           name='whe_event_type_idx'),
            models.Index(fields=['created_at'],           name='whe_created_at_idx'),
        ]

    def __str__(self):
        return f"WebhookEvent({self.gateway}/{self.event_id} {self.status})"

    def mark_processed(self, txn=None):
        self.status       = self.STATUS_PROCESSED
        self.processed_at = timezone.now()
        if txn:
            self.transaction = txn
        self.save(update_fields=['status', 'processed_at', 'transaction', 'updated_at'])

    def mark_failed(self, error: str):
        self.status       = self.STATUS_FAILED
        self.error_detail = error[:2000]
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'error_detail', 'processed_at', 'updated_at'])

    def mark_ignored(self, reason: str = ''):
        self.status       = self.STATUS_IGNORED
        self.error_detail = reason[:500]
        self.save(update_fields=['status', 'error_detail', 'updated_at'])


# ============================================================================
# Signature verifiers
# ============================================================================

def _verify_cashfree(payload: bytes, signature: str) -> bool:
    """Cashfree: HMAC-SHA256 of raw body, base64-encoded."""
    secret = getattr(settings, 'CASHFREE_SECRET_KEY', '')
    if not secret:
        logger.warning('CASHFREE_SECRET_KEY not configured — skipping signature check')
        return True
    import base64
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    # Cashfree includes a timestamp prefix: "t={ts},v1={sig}"
    if ',' in signature:
        parts = dict(p.split('=', 1) for p in signature.split(',') if '=' in p)
        ts    = parts.get('t', '')
        sig   = parts.get('v1', '')
        # Replay protection — reject events > 5 minutes old
        try:
            if abs(int(ts) - int(time.time())) > 300:
                logger.warning('Cashfree webhook replay: timestamp=%s', ts)
                return False
        except ValueError:
            return False
        signed_payload = f"{ts}.{payload.decode(errors='replace')}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, sig)
    return hmac.compare_digest(expected, signature)


def _verify_stripe(payload: bytes, signature: str) -> bool:
    """Stripe standard webhook signature verification."""
    secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    if not secret:
        logger.warning('STRIPE_WEBHOOK_SECRET not configured — skipping verification')
        return True
    try:
        import stripe
        stripe.WebhookSignature.verify_header(payload, signature, secret, tolerance=300)
        return True
    except Exception as exc:
        logger.warning('Stripe webhook signature invalid: %s', exc)
        return False


def _verify_paytm(payload: bytes, checksum: str) -> bool:
    """Paytm UPI checksum verification."""
    merchant_key = getattr(settings, 'PAYTM_MERCHANT_KEY', '')
    if not merchant_key:
        logger.warning('PAYTM_MERCHANT_KEY not configured — skipping checksum check')
        return True
    try:
        from paytmchecksum import PaytmChecksum
        body_str = payload.decode(errors='replace')
        params   = json.loads(body_str)
        return PaytmChecksum.verifySignature(params, merchant_key, checksum)
    except Exception as exc:
        logger.warning('Paytm checksum verification failed: %s', exc)
        return False


# ============================================================================
# Core idempotent processing logic
# ============================================================================

def _idempotent_process(
    gateway: str,
    event_id: str,
    event_type: str,
    payload: dict,
    signature: str,
    signature_ok: bool,
) -> tuple:
    """
    Create a PaymentWebhookEvent record and return (event, is_new).

    If a record with the same (gateway, event_id) already exists:
      - Returns (existing_record, False) — caller should return 200 immediately
    If new:
      - Creates record with status=processing
      - Returns (record, True) — caller should process
    """
    try:
        with transaction.atomic():
            event = PaymentWebhookEvent.objects.create(
                gateway      = gateway,
                event_id     = event_id,
                event_type   = event_type,
                raw_payload  = payload,
                signature    = signature[:512],
                signature_ok = signature_ok,
                status       = PaymentWebhookEvent.STATUS_PROCESSING,
            )
            try:
                from apps.core.metrics import record_webhook_event
                record_webhook_event(gateway, 'received')
            except Exception:
                pass
            return event, True
    except IntegrityError:
        # Duplicate delivery — retrieve existing record
        try:
            existing = PaymentWebhookEvent.objects.get(gateway=gateway, event_id=event_id)
            logger.info(
                'Duplicate webhook: gateway=%s event_id=%s status=%s',
                gateway, event_id, existing.status,
            )
            try:
                from apps.core.metrics import record_webhook_event
                record_webhook_event(gateway, 'duplicate')
            except Exception:
                pass
            return existing, False
        except PaymentWebhookEvent.DoesNotExist:
            # Extremely unlikely race — treat as new
            return None, True


def _handle_payment_success(payload: dict, gateway: str) -> 'PaymentTransaction | None':
    """
    Find the PaymentTransaction for a successful payment event and mark it success.

    Returns the updated PaymentTransaction or None.
    """
    from apps.payments.models import PaymentTransaction
    from apps.booking.services import transition_booking_status

    # Extract gateway-specific fields
    gateway_txn_id = ''
    booking_ref    = ''
    amount         = None

    if gateway == 'cashfree':
        data           = payload.get('data', payload)
        gateway_txn_id = str(data.get('cf_payment_id', data.get('orderId', '')))
        booking_ref    = str(data.get('order_id', data.get('orderId', '')))
        amount_raw     = data.get('order_amount', data.get('orderAmount'))
        amount         = Decimal(str(amount_raw)) if amount_raw else None

    elif gateway == 'stripe':
        obj            = payload.get('data', {}).get('object', {})
        gateway_txn_id = obj.get('id', '')
        booking_ref    = obj.get('metadata', {}).get('booking_reference', '')
        amount_raw     = obj.get('amount_received') or obj.get('amount', 0)
        amount         = Decimal(str(amount_raw)) / 100  # Stripe sends paise

    elif gateway == 'paytm_upi':
        body           = payload.get('body', payload)
        gateway_txn_id = body.get('txnId', '')
        booking_ref    = body.get('orderId', '')
        amount_raw     = body.get('txnAmount', {}).get('value') if isinstance(body.get('txnAmount'), dict) else body.get('txnAmount')
        amount         = Decimal(str(amount_raw)) if amount_raw else None

    if not booking_ref:
        logger.warning('Webhook: no booking_ref found in %s payload', gateway)
        return None

    try:
        txn = PaymentTransaction.objects.select_for_update().get(
            booking_reference=booking_ref,
            status__in=[
                PaymentTransaction.STATUS_INITIATED,
                PaymentTransaction.STATUS_PENDING,
            ],
        )
    except PaymentTransaction.DoesNotExist:
        logger.warning(
            'Webhook: no pending PaymentTransaction for booking_ref=%s gateway=%s',
            booking_ref, gateway,
        )
        return None
    except PaymentTransaction.MultipleObjectsReturned:
        txn = PaymentTransaction.objects.filter(
            booking_reference=booking_ref,
            status=PaymentTransaction.STATUS_PENDING,
        ).order_by('-created_at').first()

    with transaction.atomic():
        txn.mark_success(
            gateway_txn_id=gateway_txn_id,
            gateway_response=payload,
        )
        try:
            from apps.core.metrics import record_payment
            record_payment(gateway, 'success')
        except Exception:
            pass

        # Confirm the booking
        try:
            if txn.booking_id:
                transition_booking_status(
                    booking_id=txn.booking_id,
                    new_status='confirmed',
                    actor='webhook',
                    notes=f'{gateway} payment confirmed: {gateway_txn_id}',
                )
        except Exception as exc:
            logger.error(
                'Webhook: booking confirmation failed booking_ref=%s: %s',
                booking_ref, exc,
            )
            # Don't re-raise — payment is already marked success

    logger.info(
        'Webhook processed: gateway=%s booking_ref=%s txn=%s amount=%s',
        gateway, booking_ref, txn.transaction_id, amount,
    )
    return txn


def _handle_payment_failed(payload: dict, gateway: str):
    """Mark the PaymentTransaction as failed."""
    from apps.payments.models import PaymentTransaction

    booking_ref = ''
    reason      = 'Payment failed'

    if gateway == 'cashfree':
        data        = payload.get('data', payload)
        booking_ref = str(data.get('order_id', data.get('orderId', '')))
        reason      = data.get('payment_message', reason)
    elif gateway == 'stripe':
        obj         = payload.get('data', {}).get('object', {})
        booking_ref = obj.get('metadata', {}).get('booking_reference', '')
        reason      = obj.get('last_payment_error', {}).get('message', reason)
    elif gateway == 'paytm_upi':
        body        = payload.get('body', payload)
        booking_ref = body.get('orderId', '')
        reason      = body.get('resultInfo', {}).get('resultMsg', reason)

    if not booking_ref:
        return

    try:
        txn = PaymentTransaction.objects.filter(
            booking_reference=booking_ref,
            status__in=[
                PaymentTransaction.STATUS_INITIATED,
                PaymentTransaction.STATUS_PENDING,
            ],
        ).order_by('-created_at').first()
        if txn:
            txn.mark_failed(reason=reason, gateway_response=payload)
            try:
                from apps.core.metrics import record_payment
                record_payment(gateway, 'failed')
            except Exception:
                pass

            # Send payment failure notification to guest
            try:
                _send_payment_failure_notification(txn, reason)
            except Exception as notif_exc:
                logger.warning('Failed to queue payment failure notification: %s', notif_exc)

    except Exception as exc:
        logger.error('Webhook: failed to mark txn failed: %s', exc)


def _send_payment_failure_notification(txn, failure_reason: str = '') -> None:
    """
    Queue a payment failure email notification for the guest.
    Called from _handle_payment_failed after the transaction is marked failed.
    """
    try:
        from apps.payments.models import PaymentTransaction

        booking = txn.booking if txn.booking_id else None
        if not booking:
            return

        guest_email = booking.guest_email or (booking.user.email if booking.user else '')
        guest_name  = booking.guest_name or (booking.user.full_name if booking.user and booking.user else 'Guest')

        if not guest_email:
            return

        from apps.core.notification_tasks import send_payment_failure_notification
        send_payment_failure_notification.delay(
            session_id=str(booking.uuid),
            guest_email=guest_email,
            guest_name=guest_name,
            property_name=booking.property.name if booking.property_id else 'the selected property',
            check_in=str(booking.check_in) if booking.check_in else '',
            check_out=str(booking.check_out) if booking.check_out else '',
            amount=str(txn.amount),
            failure_reason=failure_reason[:200] if failure_reason else '',
        )
    except Exception as exc:
        logger.warning('_send_payment_failure_notification error: %s', exc)


# ============================================================================
# Celery task wrapper for async processing
# ============================================================================

try:
    from celery import shared_task

    @shared_task(
        name='apps.payments.webhook_handler.process_webhook_event',
        bind=True,
        max_retries=3,
        default_retry_delay=30,
        acks_late=True,
    )
    def process_webhook_event_task(self, event_pk: int):
        """
        Process a PaymentWebhookEvent asynchronously.

        Retries up to 3 times with 30s delay on failure.
        """
        try:
            event = PaymentWebhookEvent.objects.get(pk=event_pk)
        except PaymentWebhookEvent.DoesNotExist:
            logger.error('WebhookEvent pk=%d not found', event_pk)
            return

        if event.status == PaymentWebhookEvent.STATUS_PROCESSED:
            logger.info('WebhookEvent pk=%d already processed — skipping', event_pk)
            return

        try:
            _dispatch_event(event)
        except Exception as exc:
            logger.error('WebhookEvent pk=%d processing error: %s', event_pk, exc)
            try:
                try:
                    from apps.core.metrics import record_payment_retry
                    record_payment_retry(event.gateway)
                except Exception:
                    pass
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                event.mark_failed(str(exc))

except ImportError:
    # Celery not installed — sync-only mode
    process_webhook_event_task = None


def _dispatch_event(event: PaymentWebhookEvent):
    """Route webhook event to the correct handler by type."""
    etype   = event.event_type.lower()
    payload = event.raw_payload
    gateway = event.gateway

    if any(kw in etype for kw in ('payment.success', 'order.paid', 'payment_success', 'txn_success')):
        txn = _handle_payment_success(payload, gateway)
        event.mark_processed(txn=txn)

    elif any(kw in etype for kw in ('payment.failed', 'payment_failed', 'txn_failed')):
        _handle_payment_failed(payload, gateway)
        event.mark_processed()

    elif any(kw in etype for kw in ('refund.processed', 'refund.success')):
        # TODO: wire refund reconciliation
        event.mark_ignored('Refund event — manual reconciliation')

    else:
        event.mark_ignored(f'Unhandled event type: {event.event_type}')


# ============================================================================
# Django view handlers
# ============================================================================

@csrf_exempt
@require_POST
def cashfree_webhook(request):
    """POST /webhooks/cashfree/"""
    payload_bytes = request.body
    signature     = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
    sig_ok        = _verify_cashfree(payload_bytes, signature)

    if not sig_ok:
        logger.warning('Cashfree webhook signature mismatch')
        return HttpResponse(status=400)

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_id   = str(payload.get('data', {}).get('cf_payment_id')
                     or payload.get('data', {}).get('orderId', uuid.uuid4().hex))
    event_type = payload.get('type', 'payment.success')

    event, is_new = _idempotent_process(
        gateway='cashfree', event_id=event_id, event_type=event_type,
        payload=payload, signature=signature, signature_ok=sig_ok,
    )

    if event is None or not is_new:
        return HttpResponse(status=200)  # Acknowledge duplicate

    # Dispatch (sync or async)
    if process_webhook_event_task:
        process_webhook_event_task.delay(event.pk)
    else:
        try:
            _dispatch_event(event)
        except Exception as exc:
            event.mark_failed(str(exc))

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """POST /webhooks/stripe/"""
    payload_bytes = request.body
    signature     = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    sig_ok        = _verify_stripe(payload_bytes, signature)

    if not sig_ok:
        return HttpResponse(status=400)

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_id   = payload.get('id', uuid.uuid4().hex)
    event_type = payload.get('type', '')

    event, is_new = _idempotent_process(
        gateway='stripe', event_id=event_id, event_type=event_type,
        payload=payload, signature=signature, signature_ok=sig_ok,
    )

    if event is None or not is_new:
        return HttpResponse(status=200)

    if process_webhook_event_task:
        process_webhook_event_task.delay(event.pk)
    else:
        try:
            _dispatch_event(event)
        except Exception as exc:
            event.mark_failed(str(exc))

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def paytm_upi_webhook(request):
    """POST /webhooks/paytm/"""
    payload_bytes = request.body
    checksum      = request.META.get('HTTP_X_PAYTM_CHECKSUM', '')
    sig_ok        = _verify_paytm(payload_bytes, checksum)

    if not sig_ok:
        return HttpResponse(status=400)

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    body       = payload.get('body', payload)
    event_id   = body.get('txnId', uuid.uuid4().hex)
    event_type = 'payment_success' if body.get('resultInfo', {}).get('resultStatus') == 'TXN_SUCCESS' else 'payment_failed'

    event, is_new = _idempotent_process(
        gateway='paytm_upi', event_id=event_id, event_type=event_type,
        payload=payload, signature=checksum, signature_ok=sig_ok,
    )

    if event is None or not is_new:
        return HttpResponse(status=200)

    if process_webhook_event_task:
        process_webhook_event_task.delay(event.pk)
    else:
        try:
            _dispatch_event(event)
        except Exception as exc:
            event.mark_failed(str(exc))

    return HttpResponse(status=200)
