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

    except CheckoutException as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ValueError as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        logger.exception("Checkout start failed: %s", exc)
        return Response(
            {'error': 'Failed to create checkout session'},
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
            # External gateway: return intent for client-side flow
            return Response({
                'status': 'pending',
                'payment_intent': PaymentIntentResponseSerializer(intent).data,
                'attempt': PaymentAttemptResponseSerializer(attempt).data,
                'gateway': gateway,
                'next_action': 'redirect_to_gateway',
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
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
