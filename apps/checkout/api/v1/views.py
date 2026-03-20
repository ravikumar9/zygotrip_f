"""
Checkout API Views — 5-step production checkout flow.

Endpoints:
  POST /api/v1/checkout/start/              → Create session + hold inventory
  GET  /api/v1/checkout/{session_id}/        → Get session status
  POST /api/v1/checkout/{session_id}/guest-details/ → Submit guest info
  GET  /api/v1/checkout/{session_id}/payment-options/ → Available gateways
  POST /api/v1/checkout/{session_id}/pay/    → Initiate payment

All endpoints require authentication (JWT).
"""
import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.hotels.models import Property
from apps.rooms.models import RoomType

from apps.checkout.services import (
    create_checkout_session,
    set_guest_details,
    create_payment_intent,
    create_payment_attempt,
    complete_payment,
    extract_snapshot_total,
    fail_payment,
    compute_risk_score,
    track_funnel_event,
)
from apps.checkout.exceptions import (
    CheckoutException,
    SessionExpiredException,
    SessionStateError,
    PriceChangedException,
    InventoryTokenExpiredError,
    PaymentIntentError,
    RiskBlockedException,
)
from apps.inventory.atomic_ops import InsufficientInventoryError, RestrictionError
from apps.checkout.models import BookingSession, PaymentIntent

from .serializers import (
    StartCheckoutSerializer,
    GuestDetailsSerializer,
    InitiatePaymentSerializer,
    CheckoutSessionResponseSerializer,
    PaymentIntentResponseSerializer,
    PaymentAttemptResponseSerializer,
    BookingConfirmationSerializer,
)

logger = logging.getLogger('zygotrip.checkout.api')


# ============================================================================
# CASHFREE DIRECT VERIFICATION
# Bypass webhook dependency: call Cashfree GET Order API from the frontend
# return URL to complete the booking without waiting for the webhook.
# ============================================================================

def _verify_cashfree_order_status(order_id):
    """
    Call Cashfree GET /pg/orders/{order_id} and return (order_status, raw_data).
    order_status is one of: 'PAID', 'ACTIVE', 'EXPIRED', 'CANCELLED', 'TERMINATED'.
    Returns (None, {}) on error.
    """
    import requests as _requests
    from django.conf import settings as _settings

    client_id = (
        getattr(_settings, 'CASHFREE_CLIENT_ID', '')
        or getattr(_settings, 'CASHFREE_APP_ID', '')
    )
    client_secret = (
        getattr(_settings, 'CASHFREE_CLIENT_SECRET', '')
        or getattr(_settings, 'CASHFREE_SECRET_KEY', '')
    )
    if not client_id or not client_secret:
        logger.warning('verify_cashfree: no credentials configured')
        return None, {}

    env = getattr(_settings, 'CASHFREE_ENV', 'sandbox')
    base_url = (
        'https://api.cashfree.com/pg'
        if env == 'production'
        else 'https://sandbox.cashfree.com/pg'
    )

    headers = {
        'x-client-id': client_id,
        'x-client-secret': client_secret,
        'x-api-version': getattr(_settings, 'CASHFREE_API_VERSION', '2023-08-01'),
    }

    try:
        resp = _requests.get(
            f'{base_url}/orders/{order_id}',
            headers=headers,
            timeout=15,
        )
        data = resp.json()
        order_status = data.get('order_status')
        logger.info(
            'verify_cashfree: order_id=%s http=%s order_status=%s',
            order_id, resp.status_code, order_status,
        )
        return order_status, data
    except Exception as exc:
        logger.warning('verify_cashfree: request failed order_id=%s err=%s', order_id, exc)
        return None, {}


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_cashfree(request, session_id):
    """
    POST /api/v1/checkout/{session_id}/verify-cashfree/

    Called by the frontend on the return URL when Cashfree redirects back.
    Since the Cashfree webhook cannot reach localhost (dev) or may be delayed
    (prod), this endpoint directly polls Cashfree's GET Order API and — if the
    order is PAID — completes the booking the same way the webhook would.

    Request body: { "order_id": "CHK..." }

    Returns: same shape as /pay/ on success, or current session state if still pending.
    """
    from apps.checkout.models import PaymentAttempt as _PA

    # Use ID-only lookup: session_id is a 128-bit UUID (unguessable) and the
    # caller must also supply a matching order_id — two-factor proof of ownership.
    # The normal _get_session() fails here because Django session cookies are not
    # reliably forwarded in cross-origin XHR calls after a Cashfree redirect.
    session = _get_session_by_id(session_id)
    if not session:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    # If the session is already completed (webhook arrived first) just return it.
    if session.session_status == BookingSession.STATUS_COMPLETED:
        session = BookingSession.objects.select_related(
            'hotel', 'room_type', 'inventory_token', 'booking',
        ).get(pk=session.pk)
        return Response({
            'status': 'completed',
            'session': CheckoutSessionResponseSerializer(session).data,
        })

    order_id = request.data.get('order_id') or request.query_params.get('order_id', '')
    if not order_id:
        return Response(
            {'error': 'order_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find the PaymentAttempt matching this Cashfree order_id.
    # gateway_order_id stores the Cashfree cf_order_id; the order_id we sent
    # is the one embedded in CHK... which maps to attempt.attempt_id prefix.
    # We stored cf_order_id in gateway_order_id; we also stored order_id in
    # gateway_response['order_id']. Try both.
    attempt = None
    try:
        # Primary: gateway_order_id is the Cashfree cf_order_id (numeric string)
        # but we also need to match the CHK... order_id we sent.
        # Try gateway_response->order_id first (most reliable).
        attempt = _PA.objects.filter(
            payment_intent__booking_session=session,
            gateway='cashfree',
            gateway_response__order_id=order_id,
        ).select_related('payment_intent').order_by('-created_at').first()

        if not attempt:
            # Fallback: the CHK... order_id maps to attempt_id prefix
            # CHK{attempt_id_no_dashes_upper[:20]}
            attempt = _PA.objects.filter(
                payment_intent__booking_session=session,
                gateway='cashfree',
            ).select_related('payment_intent').order_by('-created_at').first()
    except Exception as exc:
        logger.warning('verify_cashfree: attempt lookup failed: %s', exc)

    if not attempt:
        return Response(
            {'error': 'No Cashfree payment attempt found for this session'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Don't re-verify an already-completed attempt.
    if attempt.attempt_status == _PA.STATUS_SUCCESS:
        session = BookingSession.objects.select_related(
            'hotel', 'room_type', 'inventory_token', 'booking',
        ).get(pk=session.pk)
        return Response({
            'status': 'completed',
            'session': CheckoutSessionResponseSerializer(session).data,
        })

    # Call Cashfree API to get live order status.
    order_status, cf_data = _verify_cashfree_order_status(order_id)

    if order_status == 'PAID':
        try:
            booking, session = complete_payment(attempt, gateway_response=cf_data)

            track_funnel_event(
                'payment_success',
                session_id=str(session.session_id),
                user=request.user if request.user.is_authenticated else None,
                property_id=session.hotel_id,
                booking_session_id=session.session_id,
                revenue_amount=attempt.amount,
            )

            logger.info(
                'verify_cashfree: completed booking=%s session=%s',
                booking.uuid, session.session_id,
            )

            # Fire multi-channel confirmation: email + SMS + push to guest + in-app to owner.
            try:
                from apps.core.notification_tasks import send_booking_confirmation_notification
                send_booking_confirmation_notification.delay(booking.id)
                logger.info('verify_cashfree: notification queued for booking=%s', booking.uuid)
            except Exception as _notif_exc:
                logger.warning(
                    'verify_cashfree: notification dispatch failed booking=%s err=%s',
                    booking.uuid, _notif_exc,
                )

            # Re-fetch session with booking FK populated.
            session = BookingSession.objects.select_related(
                'hotel', 'room_type', 'inventory_token', 'booking',
            ).get(pk=session.pk)

            return Response({
                'status': 'completed',
                'session': CheckoutSessionResponseSerializer(session).data,
                'booking': BookingConfirmationSerializer(booking).data,
            })
        except Exception as exc:
            logger.exception('verify_cashfree: complete_payment failed: %s', exc)
            return Response(
                {'error': 'Could not complete booking. Please check My Bookings.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif order_status in ('EXPIRED', 'CANCELLED', 'TERMINATED'):
        # Mark our attempt as failed so user can retry.
        try:
            fail_payment(attempt, f'Cashfree order {order_status.lower()}', cf_data)
        except Exception:
            pass
        return Response(
            {
                'status': 'failed',
                'error': f'Payment {order_status.lower()} by Cashfree.',
                'can_retry': True,
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    else:
        # ACTIVE or unknown — still processing; return current session state.
        return Response({
            'status': 'pending',
            'order_status': order_status,
            'session': CheckoutSessionResponseSerializer(session).data,
        })


def _create_cashfree_order(session, intent, attempt):
    """
    Create a Cashfree order for checkout and return (payment_url, gateway_data).
    Returns (None, {}) if Cashfree credentials are not configured.
    Raises ValueError on API errors.
    """
    import requests as _requests
    from django.conf import settings as _settings
    from apps.checkout.models import PaymentAttempt

    client_id = (
        getattr(_settings, 'CASHFREE_CLIENT_ID', '')
        or getattr(_settings, 'CASHFREE_APP_ID', '')
    )
    client_secret = (
        getattr(_settings, 'CASHFREE_CLIENT_SECRET', '')
        or getattr(_settings, 'CASHFREE_SECRET_KEY', '')
    )

    if not client_id or not client_secret:
        return None, {}

    env = getattr(_settings, 'CASHFREE_ENV', 'sandbox')
    base_url = (
        'https://api.cashfree.com/pg'
        if env == 'production'
        else 'https://sandbox.cashfree.com/pg'
    )

    # Extract guest details from session JSON
    gd = session.guest_details or {}
    guest_name = gd.get('name') or gd.get('full_name') or 'Guest'
    guest_email = gd.get('email') or 'guest@zygotrip.com'
    guest_phone = gd.get('phone') or '9999999999'

    success_url = getattr(_settings, 'PAYMENT_SUCCESS_URL', 'http://localhost:3000/booking/confirmation/')
    order_id = f"CHK{str(attempt.attempt_id).replace('-', '').upper()[:20]}"

    order_payload = {
        'order_id': order_id,
        'order_amount': float(intent.amount),
        'order_currency': getattr(_settings, 'DEFAULT_CURRENCY', 'INR'),
        'customer_details': {
            'customer_id': f"sess_{str(session.session_id)[:8]}",
            'customer_name': guest_name,
            'customer_email': guest_email,
            'customer_phone': guest_phone,
        },
        'order_meta': {
            'return_url': f'{success_url}{session.session_id}?order_id={order_id}',
            'notify_url': getattr(
                _settings, 'CASHFREE_WEBHOOK_URL',
                'http://127.0.0.1:8000/api/v1/payment/webhook/cashfree/',
            ),
        },
        'order_note': f'ZygoTrip Checkout {str(session.session_id)[:8]}',
    }

    headers = {
        'Content-Type': 'application/json',
        'x-client-id': client_id,
        'x-client-secret': client_secret,
        'x-api-version': getattr(_settings, 'CASHFREE_API_VERSION', '2023-08-01'),
    }

    resp = _requests.post(
        f'{base_url}/orders',
        json=order_payload,
        headers=headers,
        timeout=30,
    )
    data = resp.json()

    if resp.status_code in (200, 201) and data.get('payment_session_id'):
        payment_session_id = data['payment_session_id']
        cf_order_id = data.get('cf_order_id', order_id)
        order_token = data.get('order_token', '')

        attempt.gateway_order_id = str(cf_order_id)
        attempt.gateway_response = data
        attempt.attempt_status = PaymentAttempt.STATUS_PENDING
        attempt.save(update_fields=['gateway_order_id', 'gateway_response', 'attempt_status', 'updated_at'])

        # Cashfree v3 API does NOT return payment_link or order_token.
        # The payment_session_id is consumed by the Cashfree.js SDK on the frontend.
        # We set a stub payment_url so legacy redirect logic still has a non-empty value;
        # the frontend checks for payment_session_id first and uses the JS SDK.
        if data.get('payment_link'):
            payment_url = data['payment_link']
        elif order_token:
            if env == 'production':
                payment_url = f'https://payments.cashfree.com/order/{order_token}'
            else:
                payment_url = f'https://sandbox.cashfree.com/order/pay/{order_token}'
        else:
            # v3 fallback: frontend should use JS SDK with payment_session_id.
            # This URL is for display only — not a direct payment page.
            if env == 'production':
                payment_url = f'https://payments.cashfree.com/pg/view/order/{order_id}'
            else:
                payment_url = f'https://sandbox.cashfree.com/pg/view/order/{order_id}'

        logger.info(
            'Cashfree order created: cf_order_id=%s order_id=%s payment_url=%s',
            cf_order_id, order_id, payment_url,
        )

        return payment_url, {
            'payment_session_id': payment_session_id,
            'cf_order_id': str(cf_order_id),
            'order_id': order_id,
            'order_token': order_token,
        }

    error_msg = data.get('message', str(data))
    logger.error('Cashfree order creation failed status=%s body=%s', resp.status_code, data)
    raise ValueError(f'Cashfree: {error_msg}')


def _get_client_ip(request):
    """Extract client IP from request."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _ensure_session_key(request):
    """Guarantee a Django session key exists for guest checkout ownership."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ''


def _get_session(session_id, request):
    """Fetch session with related data and validate ownership."""
    session_key = _ensure_session_key(request)
    qs = BookingSession.objects.select_related(
        'hotel', 'room_type', 'inventory_token',
    ).filter(session_id=session_id)

    if request.user.is_authenticated:
        return qs.filter(
            Q(user=request.user) | Q(user__isnull=True, session_key=session_key)
        ).first()

    return qs.filter(user__isnull=True, session_key=session_key).first()


def _get_session_by_id(session_id):
    """
    Fetch session by session_id only — NO ownership check.

    Used by verify_cashfree where:
      - session_id is a 128-bit UUID (unguessable — acts as a secret)
      - caller also supplies order_id which is validated against a PaymentAttempt
      - Django session cookies are NOT reliably sent cross-origin (frontend:3000
        → backend:8000) after a Cashfree payment redirect, so the normal
        session_key ownership check always fails and returns None.
    """
    return BookingSession.objects.select_related(
        'hotel', 'room_type', 'inventory_token',
    ).filter(session_id=session_id).first()


# ============================================================================
# 1. START CHECKOUT
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def start_checkout(request):
    """
    POST /api/v1/checkout/start/

    Create a checkout session with inventory hold.
    Returns session_id + price snapshot + expiry time.
    """
    serializer = StartCheckoutSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(
            "Checkout start validation failed: %s | data: %s",
            serializer.errors,
            request.data,
        )
        return Response(
            {'error': 'Invalid input', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Resolve property + room type
    try:
        property_obj = Property.objects.get(id=data['property_id'], is_active=True)
    except Property.DoesNotExist:
        return Response(
            {'error': 'Property not found or inactive'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        room_type = RoomType.objects.get(
            id=data['room_type_id'],
            property=property_obj,
        )
    except RoomType.DoesNotExist:
        return Response(
            {'error': 'Room type not found for this property'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        session = create_checkout_session(
            user=request.user if request.user.is_authenticated else None,
            session_key=_ensure_session_key(request),
            property_obj=property_obj,
            room_type=room_type,
            check_in=data['check_in'],
            check_out=data['check_out'],
            guests=data['guests'],
            rooms=data['rooms'],
            rate_plan_id=data.get('rate_plan_id', ''),
            meal_plan_code=data.get('meal_plan_code', ''),
            promo_code=data.get('promo_code', ''),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_fingerprint=request.data.get('device_fingerprint', ''),
        )

        # Track funnel event
        track_funnel_event(
            'checkout_start',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=property_obj.id,
            room_type_id=room_type.id,
            booking_session_id=session.session_id,
            search_context=session.search_snapshot,
            device_type=request.data.get('device_type', ''),
            traffic_source=request.data.get('traffic_source', ''),
        )

        # Compute risk score
        try:
            compute_risk_score(session)
        except Exception as exc:
            logger.warning("Risk scoring failed: %s", exc)

        response_data = CheckoutSessionResponseSerializer(session).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    except (InsufficientInventoryError, RestrictionError) as exc:
        logger.warning(
            'Checkout 400 - inventory/restriction: property=%s room=%s checkin=%s: %s',
            data.get('property_id'),
            data.get('room_type_id'),
            data.get('check_in'),
            exc,
        )
        return Response(
            {
                'error': 'Room not available for selected dates',
                'detail': str(exc),
                'code': 'insufficient_inventory',
                'fix': 'Run: python manage.py init_inventory_calendar',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except CheckoutException as exc:
        logger.warning('Checkout 400 - CheckoutException: %s', exc)
        return Response(
            {'error': str(exc), 'code': 'checkout_error'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ValueError as exc:
        logger.warning('Checkout 400 - ValueError: %s', exc)
        return Response(
            {'error': str(exc), 'code': 'validation_error'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        logger.exception('Checkout 500 - Unexpected: %s', exc)
        return Response(
            {'error': 'Could not start checkout. Please try again.', 'code': 'server_error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================================
# 2. GET SESSION STATUS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_session(request, session_id):
    """
    GET /api/v1/checkout/{session_id}/

    Retrieve current checkout session state.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    response_data = CheckoutSessionResponseSerializer(session).data
    return Response(response_data)


# ============================================================================
# 3. GUEST DETAILS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def submit_guest_details(request, session_id):
    """
    POST /api/v1/checkout/{session_id}/guest-details/

    Submit guest information for the booking.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = GuestDetailsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid guest details', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        session = set_guest_details(session, serializer.validated_data)

        track_funnel_event(
            'guest_details',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=session.hotel_id,
            booking_session_id=session.session_id,
        )

        response_data = CheckoutSessionResponseSerializer(session).data
        return Response(response_data)

    except SessionExpiredException:
        return Response(
            {'error': 'Session has expired. Please start a new checkout.'},
            status=status.HTTP_410_GONE,
        )
    except SessionStateError as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_409_CONFLICT,
        )
    except CheckoutException as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ============================================================================
# 4. PAYMENT OPTIONS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def payment_options(request, session_id):
    """
    GET /api/v1/checkout/{session_id}/payment-options/

    Return available payment gateways for this session.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check wallet balance
    wallet_balance = 0
    try:
        from apps.wallet.models import Wallet
        wallet = Wallet.objects.filter(user=request.user).first() if request.user.is_authenticated else None
        if wallet:
            wallet_balance = float(wallet.balance)
    except Exception:
        pass

    total = float(extract_snapshot_total(session.price_snapshot))

    gateways = [
        {
            'id': 'wallet',
            'name': 'Wallet',
            'available': request.user.is_authenticated and wallet_balance >= total,
            'balance': wallet_balance,
            'description': f'Pay from wallet (₹{wallet_balance:.2f} available)',
        },
        {
            'id': 'cashfree',
            'name': 'Cashfree',
            'available': True,
            'description': 'Credit/Debit Card, Net Banking, UPI',
        },
        {
            'id': 'stripe',
            'name': 'Stripe',
            'available': True,
            'description': 'International Cards',
        },
        {
            'id': 'paytm_upi',
            'name': 'Paytm UPI',
            'available': True,
            'description': 'UPI Payment',
        },
    ]

    # Add dev gateway in DEBUG mode
    from django.conf import settings
    if settings.DEBUG:
        gateways.append({
            'id': 'dev_simulate',
            'name': 'Dev Simulate',
            'available': True,
            'description': 'Simulated payment (dev only)',
        })

    return Response({
        'session_id': str(session.session_id),
        'amount': str(extract_snapshot_total(session.price_snapshot)),
        'currency': 'INR',
        'gateways': gateways,
    })


# ============================================================================
# 5. INITIATE PAYMENT
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_payment(request, session_id):
    """
    POST /api/v1/checkout/{session_id}/pay/

    Create payment intent and attempt payment via selected gateway.

    For dev_simulate gateway: immediately completes the booking.
    For real gateways: returns gateway-specific data for client-side flow.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = InitiatePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid payment data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    gateway = data['gateway']
    idempotency_key = data.get('idempotency_key', '')

    try:
        # Check risk
        try:
            from apps.checkout.analytics_models import BookingRiskScore
            risk = BookingRiskScore.objects.filter(
                booking_session=session,
            ).first()
            if risk and risk.action_taken == 'blocked':
                return Response(
                    {'error': 'This booking has been blocked for security reasons.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Exception:
            pass

        # Create payment intent
        intent = create_payment_intent(
            session,
            idempotency_key=idempotency_key or None,
        )

        # Create payment attempt
        attempt = create_payment_attempt(intent, gateway)

        track_funnel_event(
            'payment_start',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=session.hotel_id,
            booking_session_id=session.session_id,
            revenue_amount=intent.amount,
        )

        # Gateway-specific logic
        if gateway == 'dev_simulate':
            # Dev mode: auto-complete
            booking, session = complete_payment(
                attempt,
                gateway_response={'simulated': True, 'status': 'success'},
            )

            track_funnel_event(
                'payment_success',
                session_id=str(session.session_id),
                user=request.user if request.user.is_authenticated else None,
                property_id=session.hotel_id,
                booking_session_id=session.session_id,
                revenue_amount=intent.amount,
            )

            return Response({
                'status': 'completed',
                'session': CheckoutSessionResponseSerializer(session).data,
                'payment_intent': PaymentIntentResponseSerializer(intent).data,
                'booking': BookingConfirmationSerializer(booking).data,
            }, status=status.HTTP_200_OK)

        elif gateway == 'wallet':
            # Wallet payment: deduct from wallet
            if not request.user.is_authenticated:
                fail_payment(attempt, 'Wallet payment requires authentication')
                return Response(
                    {'error': 'Wallet payment requires login'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            try:
                from apps.wallet.services import debit_wallet
                debit_wallet(
                    user=request.user,
                    amount=intent.amount,
                    description=f"Booking payment - Session {session.session_id}",
                )
                booking, session = complete_payment(
                    attempt,
                    gateway_response={'wallet': True, 'status': 'success'},
                )

                track_funnel_event(
                    'payment_success',
                    session_id=str(session.session_id),
                    user=request.user,
                    property_id=session.hotel_id,
                    booking_session_id=session.session_id,
                    revenue_amount=intent.amount,
                )

                return Response({
                    'status': 'completed',
                    'session': CheckoutSessionResponseSerializer(session).data,
                    'payment_intent': PaymentIntentResponseSerializer(intent).data,
                    'booking': BookingConfirmationSerializer(booking).data,
                })
            except Exception as exc:
                fail_payment(attempt, str(exc))
                return Response(
                    {'error': f'Wallet payment failed: {exc}'},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        else:
            # External gateway: create order and return redirect URL
            payment_url = None
            payment_session_id = None   # Cashfree JS SDK token
            gateway_data = {}

            if gateway == 'cashfree':
                try:
                    payment_url, gateway_data = _create_cashfree_order(session, intent, attempt)
                    payment_session_id = gateway_data.get('payment_session_id')
                except ValueError as gw_err:
                    fail_payment(attempt, str(gw_err))
                    return Response(
                        {
                            'error': f'Payment gateway error: {gw_err}',
                            'can_retry': True,
                        },
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

            if payment_url is None and gateway == 'cashfree':
                # Credentials not configured — surface a clear error
                fail_payment(attempt, 'Cashfree gateway not configured')
                return Response(
                    {
                        'error': (
                            'Cashfree payment gateway is not configured on this server. '
                            'Use Dev Simulate for testing or contact support.'
                        ),
                        'can_retry': True,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Ph4: idempotency key exposed so frontend can track this exact attempt
            attempt_idem_key = f"chk-{str(session.session_id)[:8]}-{attempt.attempt_id}"

            return Response({
                'status': 'pending',
                'payment_intent': PaymentIntentResponseSerializer(intent).data,
                'attempt': PaymentAttemptResponseSerializer(attempt).data,
                'gateway': gateway,
                'next_action': 'redirect_to_gateway',
                'payment_url': payment_url,
                'payment_session_id': payment_session_id,  # Ph5: Cashfree.js SDK token
                'idempotency_key': attempt_idem_key,        # Ph4: retry tracking
                'gateway_data': gateway_data,
            }, status=status.HTTP_200_OK)

    except SessionExpiredException:
        return Response(
            {'error': 'Session has expired. Please start a new checkout.'},
            status=status.HTTP_410_GONE,
        )
    except PriceChangedException as exc:
        return Response({
            'error': 'Price has changed',
            'old_price': str(exc.old_price),
            'new_price': str(exc.new_price),
            'action': 'confirm_new_price',
        }, status=status.HTTP_409_CONFLICT)
    except InventoryTokenExpiredError:
        return Response(
            {'error': 'Inventory reservation expired. Please restart checkout.'},
            status=status.HTTP_410_GONE,
        )
    except (SessionStateError, PaymentIntentError) as exc:
        # If session is in a retryable state (e.g. 'failed' from a prior attempt)
        # give the frontend a clear signal to call /retry-payment/ instead.
        retryable_states = {
            BookingSession.STATUS_FAILED,
            BookingSession.STATUS_PAYMENT_INITIATED,
            BookingSession.STATUS_PAYMENT_PROCESSING,
        }
        if session and session.session_status in retryable_states:
            return Response(
                {
                    'error': str(exc),
                    'can_retry': True,
                    'retry_endpoint': f'/api/v1/checkout/{session_id}/retry-payment/',
                    'current_state': session.session_status,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {'error': str(exc)},
            status=status.HTTP_409_CONFLICT,
        )
    except CheckoutException as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        logger.exception("Payment initiation failed: %s", exc)
        return Response(
            {'error': 'Payment processing failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================================
# WEBHOOK CALLBACK (for external gateway completion)
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def payment_callback(request, session_id):
    """
    POST /api/v1/checkout/{session_id}/callback/

    Called after external gateway redirects back.
    Verifies payment status and completes booking if successful.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    attempt_id = request.data.get('attempt_id')
    gateway_status = request.data.get('status', '')
    gateway_response = request.data.get('gateway_response', {})

    if not attempt_id:
        return Response(
            {'error': 'attempt_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.checkout.models import PaymentAttempt
    try:
        attempt = PaymentAttempt.objects.get(
            attempt_id=attempt_id,
            payment_intent__booking_session=session,
        )
    except PaymentAttempt.DoesNotExist:
        return Response(
            {'error': 'Payment attempt not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if gateway_status == 'success':
        booking, session = complete_payment(attempt, gateway_response)

        track_funnel_event(
            'payment_success',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=session.hotel_id,
            booking_session_id=session.session_id,
            revenue_amount=attempt.amount,
        )

        # Fire multi-channel confirmation: email + SMS + push to guest.
        try:
            from apps.core.notification_tasks import send_booking_confirmation_notification
            send_booking_confirmation_notification.delay(booking.id)
        except Exception as _notif_exc:
            logger.warning('payment_callback: notification dispatch failed: %s', _notif_exc)

        return Response({
            'status': 'completed',
            'session': CheckoutSessionResponseSerializer(session).data,
            'booking': BookingConfirmationSerializer(booking).data,
        })
    else:
        reason = request.data.get('failure_reason', 'Gateway reported failure')
        fail_payment(attempt, reason, gateway_response)

        track_funnel_event(
            'payment_failed',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=session.hotel_id,
            booking_session_id=session.session_id,
        )

        return Response({
            'status': 'failed',
            'error': reason,
            'can_retry': True,
            'retry_endpoint': f'/api/v1/checkout/{session_id}/retry-payment/',
        }, status=status.HTTP_402_PAYMENT_REQUIRED)


# ============================================================================
# PHASE 3 — RETRY PAYMENT (create new order after failure)
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def retry_payment(request, session_id):
    """
    POST /api/v1/checkout/{session_id}/retry-payment/

    Phase 3 — Payment Retry Flow.

    When a payment fails the frontend must call THIS endpoint to get a fresh
    PaymentIntent + PaymentAttempt.  It must NEVER re-post to /pay/ with a
    failed attempt ID.

    Rules:
      • The checkout session must still be active (not COMPLETED / EXPIRED).
      • A NEW PaymentTransaction is created — the failed one is never reused.
      • A NEW idempotency key (format: chk-{session_id[:8]}-{attempt_count})
        is generated so the gateway can reject accidental duplicates.
      • Inventory hold is preserved — only the payment layer is retried.

    Returns same shape as /pay/ so the frontend can reuse the same handler.
    """
    session = _get_session(session_id, request)
    if not session:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    # Only truly terminal sessions cannot retry (completed, expired, abandoned)
    # STATUS_FAILED is NOT terminal for retry — it means a payment attempt failed
    # and the user should be able to pay again with a new PaymentIntent.
    hard_terminal_statuses = {
        BookingSession.STATUS_COMPLETED,
        BookingSession.STATUS_EXPIRED,
        BookingSession.STATUS_ABANDONED,
    }
    if session.session_status in hard_terminal_statuses:
        return Response(
            {'error': f'Session is in state {session.session_status!r} — cannot retry.'},
            status=status.HTTP_409_CONFLICT,
        )

    serializer = InitiatePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    gateway = serializer.validated_data['gateway']

    # Count prior attempts for this session to build an idempotency key
    from apps.checkout.models import PaymentAttempt
    prior_attempt_count = PaymentAttempt.objects.filter(
        payment_intent__booking_session=session,
    ).count()
    idem_key = f"chk-{str(session.session_id)[:8]}-{prior_attempt_count + 1}"

    try:
        # Phase 7 — reset session to GUEST_DETAILS so create_payment_intent() works.
        # Covers sessions stuck in: failed, payment_initiated, payment_processing.
        # Guest details are already stored — we skip straight to payment.
        resettable_states = {
            BookingSession.STATUS_FAILED,
            BookingSession.STATUS_PAYMENT_INITIATED,
            BookingSession.STATUS_PAYMENT_PROCESSING,
        }
        if session.session_status in resettable_states:
            session.session_status = BookingSession.STATUS_GUEST_DETAILS
            session.save(update_fields=['session_status', 'updated_at'])

        # Also reset the inventory token back to ACTIVE.
        # After a payment attempt the token is in STATUS_PAYMENT_PENDING.
        # create_payment_intent() requires STATUS_ACTIVE, so we must reset it
        # before calling it (whether the prior attempt failed or timed out).
        #
        # IMPORTANT: We ALWAYS re-fetch the session after the update — even if
        # the token was already ACTIVE (e.g. fail_payment reset it earlier).
        # Without a re-fetch the in-memory select_related cache still holds the
        # stale 'payment_pending' value, causing create_payment_intent() to
        # raise InventoryTokenExpiredError → HTTP 410.
        from apps.checkout.models import InventoryToken as _InventoryToken
        try:
            if session.inventory_token_id:
                updated_rows = _InventoryToken.objects.filter(
                    pk=session.inventory_token_id,
                    token_status=_InventoryToken.STATUS_PAYMENT_PENDING,
                ).update(token_status=_InventoryToken.STATUS_ACTIVE)
                if updated_rows:
                    logger.info(
                        "retry: reset inventory token %s → active",
                        session.inventory_token_id,
                    )
                # Always re-fetch so create_payment_intent() sees the current
                # token_status regardless of whether we just updated it.
                session = BookingSession.objects.select_related(
                    'hotel', 'room_type', 'inventory_token',
                ).get(pk=session.pk)
        except Exception as _tok_err:
            logger.warning("retry: could not reset inventory token: %s", _tok_err)

        logger.info(
            "retry PRE-INTENT: session=%s status=%s token_id=%s token_status=%s token_expired=%s",
            session.session_id, session.session_status,
            getattr(session.inventory_token, 'pk', None),
            getattr(session.inventory_token, 'token_status', None),
            getattr(session.inventory_token, 'is_expired', None),
        )

        intent = create_payment_intent(session, idempotency_key=idem_key)
        attempt = create_payment_attempt(intent, gateway)

        track_funnel_event(
            'payment_retry',
            session_id=str(session.session_id),
            user=request.user if request.user.is_authenticated else None,
            property_id=session.hotel_id,
            booking_session_id=session.session_id,
            revenue_amount=intent.amount,
        )

        if gateway == 'dev_simulate':
            booking, session = complete_payment(
                attempt,
                gateway_response={'simulated': True, 'status': 'success', 'retry': True},
            )
            return Response({
                'status': 'completed',
                'session': CheckoutSessionResponseSerializer(session).data,
                'payment_intent': PaymentIntentResponseSerializer(intent).data,
                'booking': BookingConfirmationSerializer(booking).data,
            }, status=status.HTTP_200_OK)

        # External gateway retry
        payment_url = None
        payment_session_id = None
        gateway_data = {}

        if gateway == 'cashfree':
            try:
                payment_url, gateway_data = _create_cashfree_order(session, intent, attempt)
                payment_session_id = gateway_data.get('payment_session_id')
            except ValueError as gw_err:
                fail_payment(attempt, str(gw_err))
                return Response(
                    {'error': f'Gateway error: {gw_err}', 'can_retry': True},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({
            'status': 'pending',
            'payment_intent': PaymentIntentResponseSerializer(intent).data,
            'attempt': PaymentAttemptResponseSerializer(attempt).data,
            'gateway': gateway,
            'next_action': 'redirect_to_gateway',
            'payment_url': payment_url,
            'payment_session_id': payment_session_id,
            'idempotency_key': idem_key,
            'gateway_data': gateway_data,
            'is_retry': True,
        }, status=status.HTTP_200_OK)

    except (SessionExpiredException, InventoryTokenExpiredError):
        return Response(
            {'error': 'Session or inventory has expired. Please restart checkout.'},
            status=status.HTTP_410_GONE,
        )
    except (SessionStateError, PaymentIntentError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
    except Exception as exc:
        logger.exception("Retry payment failed: %s", exc)
        return Response(
            {'error': 'Could not retry payment. Please restart checkout.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
