"""
Payment REST API v1 — Production Payment Integration.

Endpoints:
  POST /api/v1/payment/initiate/                    — Initiate payment for a booking
  POST /api/v1/payment/create-order/                — Cashfree-specific create order
  GET  /api/v1/payment/status/<txn_id>/             — Check payment transaction status
  GET  /api/v1/payment/gateways/<booking_uuid>/     — Available gateways for booking
  POST /api/v1/payment/wallet/topup/                — Initiate wallet top-up via gateway
  GET  /api/v1/payment/wallet/topup/status/<id>/    — Wallet top-up status
  POST /api/v1/payment/webhook/cashfree/            — Cashfree webhook (signature-verified)
  POST /api/v1/payment/webhook/stripe/              — Stripe webhook (signature-verified)
  POST /api/v1/payment/webhook/paytm/               — Paytm webhook (checksum-verified)

Security:
  - All webhooks enforce HMAC signature + timestamp replay protection
  - Webhook idempotency via PaymentWebhookEvent model (DB-level unique constraint)
  - Booking confirmation ONLY via verified webhook — return URL never confirms
  - Wallet credit ONLY after verified webhook success
  - All payment state transitions enforced via PaymentStateMachine
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.booking.models import Booking
from apps.booking.state_machine import BookingStateMachine
from apps.payments.models import Payment, PaymentTransaction
from apps.payments.gateways import (
    PaymentRouter,
    CashfreeGateway,
    StripeGateway,
    PaytmUPIGateway,
    WalletGateway,
)
from apps.payments.state_machine import PaymentStateMachine
from apps.core.throttles import PaymentRateThrottle, WebhookRateThrottle

logger = logging.getLogger('zygotrip.payments')

WALLET_TOPUP_REF_PREFIX = 'wallet_topup:'


def _wallet_topup_reference(user_id):
    return f'{WALLET_TOPUP_REF_PREFIX}{user_id}'


def _is_wallet_topup_txn(txn):
    ref = txn.booking_reference or ''
    return txn.booking_id is None and ref.startswith(WALLET_TOPUP_REF_PREFIX)


# ===========================================================================
# POST /api/v1/payment/initiate/
# ===========================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PaymentRateThrottle])
def initiate_payment(request):
    """
    Initiate a payment for a booking.

    Supports both authenticated users and guest bookings.
    Guest bookings are identified by UUID alone (the UUID is the secret).

    Body:
      {
        "booking_uuid": "...",
        "gateway": "wallet" | "cashfree" | "stripe" | "paytm_upi",
        "idempotency_key": "optional-client-key"
      }

    Returns gateway-specific data needed to complete payment on frontend.
    """
    booking_uuid = request.data.get('booking_uuid')
    gateway_name = request.data.get('gateway')
    idempotency_key = request.data.get('idempotency_key')

    if not booking_uuid or not gateway_name:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'booking_uuid and gateway are required'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if gateway_name not in PaymentRouter.GATEWAY_MAP:
        return Response(
            {'success': False, 'error': {'code': 'invalid_gateway', 'message': f'Unknown gateway: {gateway_name}'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fetch booking — authenticated users must own it; guest bookings accessed by UUID
    try:
        if request.user and request.user.is_authenticated:
            booking = Booking.objects.select_related('property').get(
                uuid=booking_uuid, user=request.user,
            )
        else:
            booking = Booking.objects.select_related('property').get(
                uuid=booking_uuid, is_guest_booking=True,
            )
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Only HOLD or PAYMENT_PENDING bookings can be paid
    if booking.status not in (Booking.STATUS_HOLD, Booking.STATUS_PAYMENT_PENDING):
        return Response(
            {'success': False, 'error': {
                'code': 'invalid_status',
                'message': f'Booking is in "{booking.status}" status and cannot be paid',
            }},
            status=status.HTTP_409_CONFLICT,
        )

    # Check hold expiry
    if booking.is_hold_expired():
        return Response(
            {'success': False, 'error': {'code': 'hold_expired', 'message': 'Booking hold has expired'}},
            status=status.HTTP_410_GONE,
        )

    amount = booking.total_amount

    # Idempotency check: if same key exists and succeeded, return existing result
    if idempotency_key:
        existing_qs = PaymentTransaction.objects.filter(
            idempotency_key=idempotency_key,
        )
        if request.user and request.user.is_authenticated:
            existing_qs = existing_qs.filter(user=request.user)
        else:
            existing_qs = existing_qs.filter(user__isnull=True)

        existing_txn = existing_qs.first()
        if existing_txn:
            if existing_txn.booking_id and existing_txn.booking_id != booking.id:
                return Response(
                    {
                        'success': False,
                        'error': {
                            'code': 'idempotency_conflict',
                            'message': 'This idempotency_key is already used for a different booking.',
                        },
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if existing_txn.status == PaymentTransaction.STATUS_SUCCESS:
                return Response({
                    'success': True,
                    'data': {
                        'transaction_id': existing_txn.transaction_id,
                        'gateway': existing_txn.gateway,
                        'status': existing_txn.status,
                        'idempotent': True,
                    },
                })
            elif existing_txn.status == PaymentTransaction.STATUS_PENDING:
                # Return the pending transaction data
                gateway_resp = existing_txn.gateway_response or {}
                return Response({
                    'success': True,
                    'data': {
                        'transaction_id': existing_txn.transaction_id,
                        'gateway': existing_txn.gateway,
                        'status': 'pending',
                        'idempotent': True,
                        **gateway_resp,
                    },
                })
            elif existing_txn.status in (
                PaymentTransaction.STATUS_FAILED,
                PaymentTransaction.STATUS_CANCELLED,
            ):
                return Response(
                    {
                        'success': False,
                        'error': {
                            'code': 'idempotency_reused_after_failure',
                            'message': 'This idempotency_key belongs to a failed payment attempt. Use a new idempotency_key to retry.',
                        },
                    },
                    status=status.HTTP_409_CONFLICT,
                )

    with transaction.atomic():
        # Transition HOLD → PAYMENT_PENDING if not already
        if booking.status == Booking.STATUS_HOLD:
            BookingStateMachine.transition(
                booking, Booking.STATUS_PAYMENT_PENDING,
                note=f'Payment initiated via {gateway_name}',
            )

        # Create PaymentTransaction
        txn_id = f'{gateway_name[:3].upper()}-{uuid.uuid4().hex[:12].upper()}'
        txn_user = request.user if request.user and request.user.is_authenticated else None
        txn = PaymentTransaction.objects.create(
            transaction_id=txn_id,
            idempotency_key=idempotency_key,
            gateway=gateway_name,
            user=txn_user,
            booking=booking,
            booking_reference=str(booking.uuid),
            amount=amount,
            status=PaymentTransaction.STATUS_INITIATED,
        )

        # Store payment reference on booking
        booking.payment_reference_id = txn_id
        booking.save(update_fields=['payment_reference_id', 'updated_at'])

    # Initiate with gateway (outside atomic to allow external API calls)
    gateway = PaymentRouter.get_gateway(gateway_name)
    result = gateway.initiate_payment(booking, amount, txn_user, txn)

    if result.get('success'):
        # Wallet and dev-simulate payments are instant — confirm booking immediately
        if result.get('instant'):
            with transaction.atomic():
                booking.refresh_from_db()
                if booking.status == Booking.STATUS_PAYMENT_PENDING:
                    # Create Payment record
                    Payment.objects.create(
                        booking=booking,
                        user=txn_user,
                        amount=amount,
                        payment_method=gateway_name,  # wallet, dev_simulate, etc.
                        transaction_id=txn_id,
                        status='success',
                    )
                    BookingStateMachine.transition(
                        booking, Booking.STATUS_CONFIRMED,
                        note=f'{gateway_name} payment confirmed: {txn_id}',
                    )

        response_data = {
            'transaction_id': txn.transaction_id,
            'gateway': gateway_name,
            'amount': str(amount),
            'booking_uuid': str(booking.uuid),
            'status': txn.status,
        }
        # Include gateway-specific fields
        for key in ('payment_session_id', 'cf_order_id', 'order_id',
                     'environment', 'payment_url', 'session_id',
                     'txn_token', 'mid', 'callback_url', 'instant'):
            if key in result:
                response_data[key] = result[key]

        return Response({'success': True, 'data': response_data}, status=status.HTTP_201_CREATED)
    else:
        return Response(
            {'success': False, 'error': {'code': 'payment_failed', 'message': result.get('error', 'Payment initiation failed')}},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ===========================================================================
# GET /api/v1/payment/status/<txn_id>/
# ===========================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def payment_status(request, transaction_id):
    """
    Check status of a payment transaction.
    Supports authenticated users (matched by user) and guest bookings (matched by txn ID alone).
    Optionally verifies with gateway if status is pending.
    """
    try:
        if request.user and request.user.is_authenticated:
            txn = PaymentTransaction.objects.select_related('booking').get(
                transaction_id=transaction_id, user=request.user,
            )
        else:
            txn = PaymentTransaction.objects.select_related('booking').get(
                transaction_id=transaction_id, user__isnull=True,
            )
    except PaymentTransaction.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Transaction not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # If pending, optionally verify with gateway
    if txn.status == PaymentTransaction.STATUS_PENDING and request.query_params.get('verify') == 'true':
        try:
            gateway = PaymentRouter.get_gateway(txn.gateway)
            is_paid, info = gateway.verify_payment(txn)
            if is_paid and txn.status != PaymentTransaction.STATUS_SUCCESS:
                _confirm_payment_from_verification(txn, info)
        except Exception as e:
            logger.warning('Gateway verification failed for %s: %s', transaction_id, e)

    booking_status = None
    if txn.booking:
        txn.booking.refresh_from_db()
        booking_status = txn.booking.status

    return Response({
        'success': True,
        'data': {
            'transaction_id': txn.transaction_id,
            'gateway': txn.gateway,
            'amount': str(txn.amount),
            'status': txn.status,
            'booking_uuid': txn.booking_reference,
            'booking_status': booking_status,
            'created_at': txn.created_at.isoformat(),
            'updated_at': txn.updated_at.isoformat(),
        },
    })


# ===========================================================================
# GET /api/v1/payment/gateways/<booking_uuid>/
# ===========================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def available_gateways(request, booking_uuid):
    """
    Return available payment gateways for a booking.
    Supports authenticated users and guest bookings.
    Includes wallet balance if applicable (only for authenticated users).
    """
    try:
        if request.user and request.user.is_authenticated:
            booking = Booking.objects.get(uuid=booking_uuid, user=request.user)
        else:
            booking = Booking.objects.get(uuid=booking_uuid, is_guest_booking=True)
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    gw_user = request.user if request.user and request.user.is_authenticated else None
    gateways = PaymentRouter.get_available_gateways(
        booking.total_amount, gw_user,
    )

    # Transform to match frontend PaymentGateway interface:
    #   { name: gateway_key, display_name: human_label, available: bool, ... }
    frontend_gateways = []
    for gw in gateways:
        fg = {
            'name': gw['gateway'],           # gateway key: wallet, cashfree, dev_simulate, etc.
            'display_name': gw['name'],       # human-readable label
            'description': gw.get('description', ''),
            'available': True,                # already filtered by get_available_gateways
        }
        if gw['gateway'] == 'wallet':
            fg['wallet_balance'] = gw.get('balance', '0')
            fg['sufficient_balance'] = True   # only included when balance is sufficient
        frontend_gateways.append(fg)

    return Response({
        'success': True,
        'data': {
            'booking_uuid': str(booking.uuid),
            'amount': str(booking.total_amount),
            'gateways': frontend_gateways,
        },
    })


# ===========================================================================
# Cashfree-specific Create Order endpoint (Phase 7)
# ===========================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PaymentRateThrottle])
def cashfree_create_order(request):
    """
    POST /api/v1/payment/create-order/

    Cashfree-specific create-order endpoint.  Returns payment_session_id
    for use with the Cashfree JS checkout SDK.

    Body: { "booking_uuid": "...", "idempotency_key": "..." }
    Response: { payment_session_id, order_id, environment, amount, currency }
    """
    return initiate_payment(request)


# ===========================================================================
# Wallet Top-up (Phase 6)
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentRateThrottle])
def wallet_topup_initiate(request):
    """
    POST /api/v1/payment/wallet/topup/

    Initiate a wallet top-up via Cashfree (or any configured gateway).
    Wallet is only credited AFTER verified webhook success.

    Body:
      {
        "amount": 500.00,
        "gateway": "cashfree",
        "idempotency_key": "optional-key"
      }

    Security:
      - Authenticated users only
      - Wallet credit only occurs in cashfree webhook handler after signature
        verification — never on return URL
      - Duplicate webhooks silently ignored via PaymentWebhookEvent idempotency
    """
    amount_raw = request.data.get('amount')
    gateway_name = request.data.get('gateway', 'cashfree')
    idempotency_key = request.data.get('idempotency_key')

    if not amount_raw:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'amount is required'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = Decimal(str(amount_raw))
        if amount <= 0:
            raise ValueError('Must be positive')
        if amount > Decimal('100000'):
            raise ValueError('Max top-up is ₹1,00,000')
    except (ValueError, TypeError) as e:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': f'Invalid amount: {e}'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if gateway_name not in PaymentRouter.GATEWAY_MAP:
        return Response(
            {'success': False, 'error': {'code': 'invalid_gateway', 'message': f'Unknown gateway: {gateway_name}'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Idempotency: if same key was used and succeeded, return cached result
    if idempotency_key:
        existing = PaymentTransaction.objects.filter(
            idempotency_key=idempotency_key,
            user=request.user,
            booking__isnull=True,
            booking_reference=_wallet_topup_reference(request.user.id),
        ).first()
        if existing and existing.status == PaymentTransaction.STATUS_SUCCESS:
            return Response({
                'success': True,
                'data': {
                    'transaction_id': existing.transaction_id,
                    'amount': str(existing.amount),
                    'status': existing.status,
                    'idempotent': True,
                },
            })
        if existing and existing.status == PaymentTransaction.STATUS_PENDING:
            return Response({
                'success': True,
                'data': {
                    'transaction_id': existing.transaction_id,
                    'amount': str(existing.amount),
                    'status': existing.status,
                    'idempotent': True,
                },
            })
        if existing and existing.status in (
            PaymentTransaction.STATUS_FAILED,
            PaymentTransaction.STATUS_CANCELLED,
        ):
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 'idempotency_reused_after_failure',
                        'message': 'This idempotency_key belongs to a failed top-up attempt. Use a new idempotency_key to retry.',
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

    # Create a wallet-topup PaymentTransaction (no booking linked)
    txn_id = f'WTP-{uuid.uuid4().hex[:12].upper()}'

    with transaction.atomic():
        txn = PaymentTransaction.objects.create(
            transaction_id=txn_id,
            idempotency_key=idempotency_key,
            gateway=gateway_name,
            user=request.user,
            booking=None,
            booking_reference=_wallet_topup_reference(request.user.id),
            amount=amount,
            status=PaymentTransaction.STATUS_INITIATED,
        )

    # Build a lightweight mock booking-like object for gateway.initiate_payment()
    class _WalletTopupContext:
        """Minimal booking-like namespace for the gateway API call."""
        uuid = uuid.uuid4()
        public_booking_id = txn_id

    context = _WalletTopupContext()
    gateway = PaymentRouter.get_gateway(gateway_name)
    result = gateway.initiate_payment(context, amount, request.user, txn)

    if result.get('success'):
        response_data = {
            'transaction_id': txn.transaction_id,
            'gateway': gateway_name,
            'amount': str(amount),
            'currency': getattr(settings, 'DEFAULT_CURRENCY', 'INR'),
            'txn_type': 'wallet_topup',
            'status': txn.status,
        }
        for key in ('payment_session_id', 'cf_order_id', 'order_id', 'environment',
                    'payment_url', 'session_id', 'txn_token', 'mid'):
            if key in result:
                response_data[key] = result[key]

        logger.info(
            'wallet_topup_initiate: txn=%s user=%s amount=₹%s gateway=%s',
            txn_id, request.user.id, amount, gateway_name,
        )
        return Response({'success': True, 'data': response_data}, status=status.HTTP_201_CREATED)
    else:
        return Response(
            {'success': False, 'error': {'code': 'payment_failed', 'message': result.get('error', 'Top-up initiation failed')}},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_topup_status(request, transaction_id):
    """
    GET /api/v1/payment/wallet/topup/status/<transaction_id>/

    Check status of a wallet top-up transaction.
    If status is pending and ?verify=true, polls the gateway.
    """
    try:
        txn = PaymentTransaction.objects.get(
            transaction_id=transaction_id,
            user=request.user,
            booking__isnull=True,
            booking_reference=_wallet_topup_reference(request.user.id),
        )
    except PaymentTransaction.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Top-up transaction not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify with gateway if requested
    if txn.status == PaymentTransaction.STATUS_PENDING and request.query_params.get('verify') == 'true':
        try:
            gateway = PaymentRouter.get_gateway(txn.gateway)
            is_paid, info = gateway.verify_payment(txn)
            if is_paid and txn.status != PaymentTransaction.STATUS_SUCCESS:
                _credit_wallet_from_topup(txn, info)
        except Exception as e:
            logger.warning('Wallet topup verify failed for %s: %s', transaction_id, e)

    txn.refresh_from_db()
    return Response({
        'success': True,
        'data': {
            'transaction_id': txn.transaction_id,
            'amount': str(txn.amount),
            'status': txn.status,
            'txn_type': 'wallet_topup',
            'gateway': txn.gateway,
            'created_at': txn.created_at.isoformat(),
        },
    })


# ===========================================================================
# Webhook Endpoints (csrf_exempt, AllowAny — signature-verified)
# ===========================================================================

def _get_or_record_webhook_event(gateway, event_id, event_type, payload, signature=''):
    """
    Create a PaymentWebhookEvent record for idempotent webhook processing.

    Returns:
        (event, is_new)
        event:  PaymentWebhookEvent instance
        is_new: True if this is the first time we see this event_id
    """
    from apps.payments.webhook_handler import PaymentWebhookEvent

    try:
        event = PaymentWebhookEvent.objects.create(
            gateway=gateway,
            event_id=event_id,
            event_type=event_type,
            raw_payload=payload,
            signature=signature[:512],
            signature_ok=True,
            status=PaymentWebhookEvent.STATUS_PROCESSING,
        )
        return event, True
    except IntegrityError:
        # Duplicate — already processed or being processed
        event = PaymentWebhookEvent.objects.get(gateway=gateway, event_id=event_id)
        logger.info(
            '_get_or_record_webhook_event: duplicate %s/%s status=%s',
            gateway, event_id, event.status,
        )
        return event, False


def _confirm_payment_from_verification(txn, info=None, webhook_event=None):
    """
    Mark transaction success + confirm booking atomically.

    Only triggers if booking is still in PAYMENT_PENDING state.
    For wallet top-ups: credits the wallet instead of confirming a booking.
    """
    with transaction.atomic():
        txn.refresh_from_db()
        if txn.status == PaymentTransaction.STATUS_SUCCESS:
            # Already processed — idempotent return
            if webhook_event:
                webhook_event.__class__.objects.filter(pk=webhook_event.pk).update(
                    status=webhook_event.__class__.STATUS_IGNORED,
                    processed_at=timezone.now(),
                )
            return

        gateway_txn_id = ''
        if info and isinstance(info, dict):
            gateway_txn_id = (
                info.get('data', {}).get('cf_order_id', '')
                or info.get('data', {}).get('id', '')
                or info.get('data', {}).get('payment_id', '')
            )

        txn.mark_success(gateway_txn_id=gateway_txn_id, gateway_response=info)

        # ── Wallet top-up path ────────────────────────────────────────────
        if _is_wallet_topup_txn(txn):
            _credit_wallet_from_topup(txn, info, inside_atomic=True)
            if webhook_event:
                webhook_event.__class__.objects.filter(pk=webhook_event.pk).update(
                    status=webhook_event.__class__.STATUS_PROCESSED,
                    processed_at=timezone.now(),
                    transaction=txn,
                )
            logger.info(
                'wallet_topup confirmed: txn=%s user=%s amount=₹%s gateway=%s',
                txn.transaction_id, txn.user_id, txn.amount, txn.gateway,
            )
            return

        # ── Booking payment path ──────────────────────────────────────────
        if txn.booking_id:
            booking = Booking.objects.select_for_update().get(pk=txn.booking_id)
            if booking.status == Booking.STATUS_PAYMENT_PENDING:
                Payment.objects.get_or_create(
                    transaction_id=txn.transaction_id,
                    defaults={
                        'booking': booking,
                        'user': txn.user,
                        'amount': txn.amount,
                        'payment_method': txn.gateway,
                        'status': 'success',
                    },
                )
                BookingStateMachine.transition(
                    booking, Booking.STATUS_CONFIRMED,
                    note=f'Payment confirmed via {txn.gateway} webhook: {txn.transaction_id}',
                )
                logger.info(
                    'booking_confirmed: booking=%s txn=%s gateway=%s amount=₹%s',
                    booking.public_booking_id, txn.transaction_id, txn.gateway, txn.amount,
                )

        if webhook_event:
            webhook_event.__class__.objects.filter(pk=webhook_event.pk).update(
                status=webhook_event.__class__.STATUS_PROCESSED,
                processed_at=timezone.now(),
                transaction=txn,
            )


def _credit_wallet_from_topup(txn, info=None, inside_atomic=False):
    """
    Credit wallet balance after a verified top-up payment.
    Must be called inside a transaction if inside_atomic=True.
    """
    from apps.wallet.models import Wallet

    credit_amount = txn.amount

    def _do_credit():
        try:
            wallet = Wallet.objects.select_for_update().get(user=txn.user)
        except Wallet.DoesNotExist:
            logger.error(
                '_credit_wallet_from_topup: no wallet for user=%s txn=%s',
                txn.user_id, txn.transaction_id,
            )
            return

        wallet.credit(
            credit_amount,
            txn_type='topup',
            reference=txn.transaction_id,
            note=f'Wallet top-up via {txn.gateway}: {txn.transaction_id}',
        )
        logger.info(
            'wallet_credited: user=%s amount=₹%s txn=%s',
            txn.user_id, credit_amount, txn.transaction_id,
        )

    if inside_atomic:
        _do_credit()
    else:
        with transaction.atomic():
            _do_credit()


def _fail_payment_from_webhook(txn, reason='', webhook_event=None):
    """Mark txn failed + fail booking + release inventory."""
    with transaction.atomic():
        txn.refresh_from_db()
        if txn.status in (PaymentTransaction.STATUS_FAILED, PaymentTransaction.STATUS_SUCCESS):
            if webhook_event:
                webhook_event.__class__.objects.filter(pk=webhook_event.pk).update(
                    status=webhook_event.__class__.STATUS_IGNORED,
                    processed_at=timezone.now(),
                )
            return

        txn.mark_failed(reason)

        if webhook_event:
            webhook_event.__class__.objects.filter(pk=webhook_event.pk).update(
                status=webhook_event.__class__.STATUS_PROCESSED,
                processed_at=timezone.now(),
                transaction=txn,
                error_detail=reason[:500],
            )

        if txn.booking_id:
            booking = Booking.objects.select_for_update().get(pk=txn.booking_id)
            if booking.status == Booking.STATUS_PAYMENT_PENDING:
                BookingStateMachine.transition(
                    booking, Booking.STATUS_FAILED,
                    note=f'Payment failed via {txn.gateway} webhook: {reason}',
                )
                try:
                    from apps.booking.hold_expiry_service import _release_hold_transaction
                    _release_hold_transaction(booking)
                except Exception as e:
                    logger.error(
                        'failed_to_release_inventory: booking=%s error=%s',
                        booking.uuid, e,
                    )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_cashfree(request):
    """
    POST /api/v1/payment/webhook/cashfree/

    Cashfree webhook handler with full OTA-grade security:
      1. HMAC-SHA256 signature verification
      2. Timestamp replay protection (±5 minutes)
      3. DB-level idempotency via PaymentWebhookEvent UNIQUE(gateway, event_id)
      4. Atomic booking confirmation / wallet credit
      5. Return URL NEVER confirms booking — only this webhook does

    IMPORTANT: Gateway must be configured to POST to this endpoint.
    """
    is_valid, payload = CashfreeGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning(
            'cashfree_webhook: invalid_signature ip=%s',
            request.META.get('REMOTE_ADDR', ''),
        )
        return Response(
            {'success': False, 'error': {'code': 'invalid_signature', 'message': 'Invalid signature'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Extract order / event identifiers
    order_data   = payload.get('data', {}).get('order', {})
    payment_data = payload.get('data', {}).get('payment', {})
    order_id     = order_data.get('order_id', '')
    order_status = order_data.get('order_status', '')
    # Cashfree event_id: use cf_payment_id if available, else order_id
    event_id     = (
        payment_data.get('cf_payment_id', '')
        or order_data.get('cf_order_id', '')
        or order_id
    )
    event_type   = payload.get('type', 'PAYMENT_SUCCESS_WEBHOOK')

    if not order_id:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Missing order_id'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Idempotency gate ─────────────────────────────────────────────────────
    sig_header = request.headers.get('x-webhook-signature', '')
    wh_event, is_new = _get_or_record_webhook_event(
        gateway='cashfree',
        event_id=str(event_id),
        event_type=event_type,
        payload=payload,
        signature=sig_header,
    )
    if not is_new:
        logger.info('cashfree_webhook: duplicate event_id=%s — ignored', event_id)
        return Response({'success': True, 'data': {'status': 'ok', 'idempotent': True}})

    # ── Look up transaction ──────────────────────────────────────────────────
    try:
        txn = PaymentTransaction.objects.get(transaction_id=order_id)
    except PaymentTransaction.DoesNotExist:
        logger.error('cashfree_webhook: txn_not_found order_id=%s', order_id)
        from apps.payments.webhook_handler import PaymentWebhookEvent
        PaymentWebhookEvent.objects.filter(pk=wh_event.pk).update(
            status=PaymentWebhookEvent.STATUS_FAILED,
            error_detail='Transaction not found',
            processed_at=timezone.now(),
        )
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Transaction not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    txn.record_webhook(payload)

    logger.info(
        'cashfree_webhook: order_id=%s status=%s txn=%s amount=₹%s',
        order_id, order_status, txn.transaction_id, txn.amount,
    )

    if order_status == 'PAID':
        _confirm_payment_from_verification(txn, {'data': payment_data}, webhook_event=wh_event)
    elif order_status in ('ACTIVE', 'PENDING'):
        from apps.payments.webhook_handler import PaymentWebhookEvent
        PaymentWebhookEvent.objects.filter(pk=wh_event.pk).update(
            status=PaymentWebhookEvent.STATUS_IGNORED,
            processed_at=timezone.now(),
        )
    else:
        _fail_payment_from_webhook(
            txn,
            reason=f'Cashfree status: {order_status}',
            webhook_event=wh_event,
        )

    return Response({'success': True, 'data': {'status': 'ok'}})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_stripe(request):
    """Stripe webhook — signature-verified, idempotent via PaymentWebhookEvent."""
    is_valid, event = StripeGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning(
            'stripe_webhook: invalid_signature ip=%s',
            request.META.get('REMOTE_ADDR', ''),
        )
        return Response(
            {'success': False, 'error': {'code': 'invalid_signature', 'message': 'Invalid signature'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    event_type  = event.get('type', '') if isinstance(event, dict) else getattr(event, 'type', '')
    stripe_event_id = event.get('id', '') if isinstance(event, dict) else getattr(event, 'id', '')

    # Idempotency gate
    wh_event, is_new = _get_or_record_webhook_event(
        gateway='stripe',
        event_id=stripe_event_id or f'stripe-{event_type}',
        event_type=event_type,
        payload=event if isinstance(event, dict) else {'type': event_type},
    )
    if not is_new:
        return Response({'success': True, 'data': {'status': 'ok', 'idempotent': True}})

    if event_type == 'checkout.session.completed':
        session = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event['data']['object']
        txn_id = session.get('metadata', {}).get('transaction_id', '')
        if txn_id:
            try:
                txn = PaymentTransaction.objects.get(transaction_id=txn_id)
                txn.record_webhook(
                    event if isinstance(event, dict) else {'type': event_type, 'session_id': session.get('id')},
                )
                if session.get('payment_status') == 'paid':
                    _confirm_payment_from_verification(txn, {'data': session}, webhook_event=wh_event)
            except PaymentTransaction.DoesNotExist:
                logger.error('stripe_webhook: txn_not_found txn_id=%s', txn_id)

    elif event_type == 'checkout.session.expired':
        session = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event['data']['object']
        txn_id = session.get('metadata', {}).get('transaction_id', '')
        if txn_id:
            try:
                txn = PaymentTransaction.objects.get(transaction_id=txn_id)
                txn.record_webhook(event if isinstance(event, dict) else {'type': event_type})
                _fail_payment_from_webhook(txn, reason='Stripe checkout session expired', webhook_event=wh_event)
            except PaymentTransaction.DoesNotExist:
                pass

    logger.info('stripe_webhook: type=%s event_id=%s', event_type, stripe_event_id)
    return Response({'success': True, 'data': {'status': 'ok'}})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_paytm(request):
    """Paytm webhook — checksum-verified, idempotent via PaymentWebhookEvent."""
    is_valid, payload = PaytmUPIGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning(
            'paytm_webhook: invalid_checksum ip=%s',
            request.META.get('REMOTE_ADDR', ''),
        )
        return Response(
            {'success': False, 'error': {'code': 'invalid_signature', 'message': 'Invalid checksum'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    order_id       = payload.get('ORDERID', '') or payload.get('orderId', '')
    result_status  = payload.get('STATUS', '') or payload.get('resultInfo', {}).get('resultStatus', '')
    gateway_txn_id = payload.get('TXNID', '') or payload.get('txnId', '')

    if not order_id:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Missing order ID'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Idempotency gate — use TXNID if present, else ORDERID
    event_id = gateway_txn_id or order_id
    wh_event, is_new = _get_or_record_webhook_event(
        gateway='paytm_upi',
        event_id=event_id,
        event_type=result_status,
        payload=payload,
    )
    if not is_new:
        return Response({'success': True, 'data': {'status': 'ok', 'idempotent': True}})

    try:
        txn = PaymentTransaction.objects.get(transaction_id=order_id)
    except PaymentTransaction.DoesNotExist:
        logger.error('paytm_webhook: txn_not_found order_id=%s', order_id)
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Transaction not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    txn.record_webhook(payload)

    logger.info(
        'paytm_webhook: order_id=%s status=%s txn=%s',
        order_id, result_status, txn.transaction_id,
    )

    if result_status == 'TXN_SUCCESS':
        _confirm_payment_from_verification(
            txn, {'data': {'id': gateway_txn_id}}, webhook_event=wh_event,
        )
    elif result_status == 'TXN_FAILURE':
        _fail_payment_from_webhook(
            txn,
            reason=payload.get('RESPMSG', 'Paytm transaction failed'),
            webhook_event=wh_event,
        )
    # PENDING — wait for next callback

    return Response({'success': True, 'data': {'status': 'ok'}})
