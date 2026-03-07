"""
Payment REST API v1 — Production Payment Integration.

Endpoints:
  POST /api/v1/payment/initiate/              — Initiate payment for a booking
  GET  /api/v1/payment/status/<txn_id>/       — Check payment transaction status
  GET  /api/v1/payment/gateways/<booking_uuid>/  — Available gateways for booking
  POST /api/v1/payment/webhook/cashfree/      — Cashfree webhook (signature-verified)
  POST /api/v1/payment/webhook/stripe/        — Stripe webhook (signature-verified)
  POST /api/v1/payment/webhook/paytm/         — Paytm webhook (checksum-verified)
"""
import logging
import uuid
from decimal import Decimal

from django.db import transaction
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
from apps.core.throttles import PaymentRateThrottle, WebhookRateThrottle

logger = logging.getLogger('zygotrip.payments')


# ===========================================================================
# POST /api/v1/payment/initiate/
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentRateThrottle])
def initiate_payment(request):
    """
    Initiate a payment for a booking.

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

    # Fetch booking
    try:
        booking = Booking.objects.select_related('property').get(
            uuid=booking_uuid, user=request.user,
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
        existing_txn = PaymentTransaction.objects.filter(
            idempotency_key=idempotency_key,
        ).first()
        if existing_txn:
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

    with transaction.atomic():
        # Transition HOLD → PAYMENT_PENDING if not already
        if booking.status == Booking.STATUS_HOLD:
            BookingStateMachine.transition(
                booking, Booking.STATUS_PAYMENT_PENDING,
                note=f'Payment initiated via {gateway_name}',
            )

        # Create PaymentTransaction
        txn_id = f'{gateway_name[:3].upper()}-{uuid.uuid4().hex[:12].upper()}'
        txn = PaymentTransaction.objects.create(
            transaction_id=txn_id,
            idempotency_key=idempotency_key,
            gateway=gateway_name,
            user=request.user,
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
    result = gateway.initiate_payment(booking, amount, request.user, txn)

    if result.get('success'):
        # Wallet payments are instant — confirm booking immediately
        if result.get('instant'):
            with transaction.atomic():
                booking.refresh_from_db()
                if booking.status == Booking.STATUS_PAYMENT_PENDING:
                    # Create Payment record
                    Payment.objects.create(
                        booking=booking,
                        user=request.user,
                        amount=amount,
                        payment_method='wallet',
                        transaction_id=txn_id,
                        status='success',
                    )
                    BookingStateMachine.transition(
                        booking, Booking.STATUS_CONFIRMED,
                        note=f'Wallet payment confirmed: {txn_id}',
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
@permission_classes([IsAuthenticated])
def payment_status(request, transaction_id):
    """
    Check status of a payment transaction.
    Optionally verifies with gateway if status is pending.
    """
    try:
        txn = PaymentTransaction.objects.select_related('booking').get(
            transaction_id=transaction_id, user=request.user,
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
@permission_classes([IsAuthenticated])
def available_gateways(request, booking_uuid):
    """
    Return available payment gateways for a booking.
    Includes wallet balance if applicable.
    """
    try:
        booking = Booking.objects.get(uuid=booking_uuid, user=request.user)
    except Booking.DoesNotExist:
        return Response(
            {'success': False, 'error': {'code': 'not_found', 'message': 'Booking not found'}},
            status=status.HTTP_404_NOT_FOUND,
        )

    gateways = PaymentRouter.get_available_gateways(
        booking.total_amount, request.user,
    )

    return Response({
        'success': True,
        'data': {
            'booking_uuid': str(booking.uuid),
            'amount': str(booking.total_amount),
            'gateways': gateways,
        },
    })


# ===========================================================================
# Webhook Endpoints (csrf_exempt, AllowAny — signature-verified)
# ===========================================================================

def _confirm_payment_from_verification(txn, info=None):
    """Shared logic: mark txn success + confirm booking."""
    with transaction.atomic():
        txn.refresh_from_db()
        if txn.status == PaymentTransaction.STATUS_SUCCESS:
            return  # Already processed (idempotent)

        gateway_txn_id = ''
        if info and isinstance(info, dict):
            gateway_txn_id = info.get('data', {}).get('cf_order_id', '') or info.get('data', {}).get('id', '')

        txn.mark_success(gateway_txn_id=gateway_txn_id, gateway_response=info)

        if txn.booking:
            booking = Booking.objects.select_for_update().get(pk=txn.booking_id)
            if booking.status == Booking.STATUS_PAYMENT_PENDING:
                Payment.objects.create(
                    booking=booking,
                    user=txn.user,
                    amount=txn.amount,
                    payment_method=txn.gateway,
                    transaction_id=txn.transaction_id,
                    status='success',
                )
                BookingStateMachine.transition(
                    booking, Booking.STATUS_CONFIRMED,
                    note=f'Payment confirmed via {txn.gateway} webhook: {txn.transaction_id}',
                )
                logger.info(
                    'Booking %s confirmed via %s webhook',
                    booking.public_booking_id, txn.gateway,
                )


def _fail_payment_from_webhook(txn, reason=''):
    """Shared logic: mark txn failed + fail booking."""
    with transaction.atomic():
        txn.refresh_from_db()
        if txn.status in (PaymentTransaction.STATUS_FAILED, PaymentTransaction.STATUS_SUCCESS):
            return  # Already terminal

        txn.mark_failed(reason)

        if txn.booking:
            booking = Booking.objects.select_for_update().get(pk=txn.booking_id)
            if booking.status == Booking.STATUS_PAYMENT_PENDING:
                BookingStateMachine.transition(
                    booking, Booking.STATUS_FAILED,
                    note=f'Payment failed via {txn.gateway} webhook: {reason}',
                )
                # Release inventory
                try:
                    from apps.booking.hold_expiry_service import _release_hold_transaction
                    _release_hold_transaction(booking)
                except Exception as e:
                    logger.error('Failed to release inventory for booking %s: %s', booking.uuid, e)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_cashfree(request):
    """Cashfree webhook — signature-verified."""
    is_valid, payload = CashfreeGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning('Cashfree webhook: invalid signature')
        return Response({'error': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)

    order_data = payload.get('data', {}).get('order', {})
    payment_data = payload.get('data', {}).get('payment', {})
    order_id = order_data.get('order_id', '')
    order_status = order_data.get('order_status', '')

    if not order_id:
        return Response({'error': 'Missing order_id'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        txn = PaymentTransaction.objects.get(transaction_id=order_id)
    except PaymentTransaction.DoesNotExist:
        logger.error('Cashfree webhook: txn not found for order %s', order_id)
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)

    txn.record_webhook(payload)

    if order_status == 'PAID':
        _confirm_payment_from_verification(txn, {'data': payment_data})
    elif order_status in ('ACTIVE', 'PENDING'):
        pass  # Still processing
    else:
        _fail_payment_from_webhook(txn, reason=f'Cashfree status: {order_status}')

    return Response({'status': 'ok'})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_stripe(request):
    """Stripe webhook — signature-verified."""
    is_valid, event = StripeGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning('Stripe webhook: invalid signature')
        return Response({'error': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)

    event_type = event.get('type', '') if isinstance(event, dict) else getattr(event, 'type', '')

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
                    _confirm_payment_from_verification(txn, {'data': session})
            except PaymentTransaction.DoesNotExist:
                logger.error('Stripe webhook: txn not found for %s', txn_id)

    elif event_type == 'checkout.session.expired':
        session = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event['data']['object']
        txn_id = session.get('metadata', {}).get('transaction_id', '')
        if txn_id:
            try:
                txn = PaymentTransaction.objects.get(transaction_id=txn_id)
                txn.record_webhook(
                    event if isinstance(event, dict) else {'type': event_type},
                )
                _fail_payment_from_webhook(txn, reason='Stripe checkout session expired')
            except PaymentTransaction.DoesNotExist:
                pass

    return Response({'status': 'ok'})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookRateThrottle])
def webhook_paytm(request):
    """Paytm webhook — checksum-verified."""
    is_valid, payload = PaytmUPIGateway.verify_webhook_signature(request)
    if not is_valid:
        logger.warning('Paytm webhook: invalid checksum')
        return Response({'error': 'Invalid checksum'}, status=status.HTTP_403_FORBIDDEN)

    order_id = payload.get('ORDERID', '') or payload.get('orderId', '')
    result_status = payload.get('STATUS', '') or payload.get('resultInfo', {}).get('resultStatus', '')
    gateway_txn_id = payload.get('TXNID', '') or payload.get('txnId', '')

    if not order_id:
        return Response({'error': 'Missing order ID'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        txn = PaymentTransaction.objects.get(transaction_id=order_id)
    except PaymentTransaction.DoesNotExist:
        logger.error('Paytm webhook: txn not found for order %s', order_id)
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)

    txn.record_webhook(payload)

    if result_status == 'TXN_SUCCESS':
        _confirm_payment_from_verification(txn, {'data': {'id': gateway_txn_id}})
    elif result_status == 'TXN_FAILURE':
        _fail_payment_from_webhook(
            txn,
            reason=payload.get('RESPMSG', 'Paytm transaction failed'),
        )
    # PENDING — do nothing, wait for next callback

    return Response({'status': 'ok'})
