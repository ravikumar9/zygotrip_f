"""
OTP Authentication API views.

Endpoints:
  POST /api/v1/auth/otp/send/      — Send OTP to phone number
  POST /api/v1/auth/otp/verify/    — Verify OTP and login/register
"""
import logging
import re

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.otp_models import OTP
from apps.accounts.sms_service import send_otp
from apps.core.throttles import OTPRateThrottle

logger = logging.getLogger('zygotrip.api.auth')

PHONE_RE = re.compile(r'^\+?\d{10,15}$')


def _sanitize_phone(phone: str) -> str:
    """Normalize phone: strip spaces, ensure +91 prefix for Indian numbers."""
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('0'):
        phone = '+91' + phone[1:]
    elif not phone.startswith('+'):
        phone = '+91' + phone
    return phone


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPRateThrottle])
def otp_send(request):
    """
    POST /api/v1/auth/otp/send/

    Body: { phone: "+919876543210", purpose?: "login" | "verify" }
    Returns: { success: true, data: { message, expires_in_seconds } }
    """
    raw_phone = request.data.get('phone', '')
    purpose = request.data.get('purpose', 'login')

    if purpose not in ('login', 'verify'):
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Invalid purpose'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _sanitize_phone(raw_phone)

    if not PHONE_RE.match(phone):
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Invalid phone number format'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        otp = OTP.generate(phone=phone, purpose=purpose)
    except ValueError as e:
        return Response(
            {'success': False, 'error': {'code': 'rate_limited', 'message': str(e)}},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Send OTP via SMS
    sent = send_otp(phone, otp.code)
    if not sent:
        logger.error('Failed to send OTP to %s', phone)
        return Response(
            {'success': False, 'error': {'code': 'sms_failed', 'message': 'Failed to send OTP. Please try again.'}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    logger.info('OTP sent to %s (purpose=%s)', phone, purpose)

    return Response({
        'success': True,
        'data': {
            'message': 'OTP sent successfully',
            'expires_in_seconds': 300,
            'phone': phone,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPRateThrottle])
def otp_verify(request):
    """
    POST /api/v1/auth/otp/verify/

    Body: { phone: "+919876543210", code: "123456", full_name?: "..." }

    Behaviour:
      - If user with this phone exists → login (return JWT tokens)
      - If no user exists → create account with phone as primary identifier,
        optional full_name, then return JWT tokens
    """
    raw_phone = request.data.get('phone', '')
    code = request.data.get('code', '')
    full_name = request.data.get('full_name', '')

    phone = _sanitize_phone(raw_phone)

    if not PHONE_RE.match(phone):
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'Invalid phone number'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not code or len(code) != 6:
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': 'OTP must be 6 digits'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify OTP
    is_valid = OTP.verify(phone=phone, code=code, purpose='login')
    if not is_valid:
        return Response(
            {'success': False, 'error': {'code': 'invalid_otp', 'message': 'Invalid or expired OTP'}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Find or create user
    user = User.objects.filter(phone=phone).first()
    is_new_user = False

    if not user:
        # Auto-register: create user with phone
        is_new_user = True
        email = f'{phone.replace("+", "")}@phone.zygotrip.local'  # placeholder email
        user = User.objects.create_user(
            email=email,
            password=None,  # No password for OTP users
            full_name=full_name or f'User {phone[-4:]}',
            phone=phone,
            role='traveler',
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        logger.info('New OTP user created: %s (phone=%s)', user.email, phone)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    tokens = {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

    from apps.accounts.api.v1.serializers import UserSerializer

    logger.info('OTP login: %s (phone=%s, new=%s)', user.email, phone, is_new_user)

    return Response({
        'success': True,
        'data': {
            'user': UserSerializer(user).data,
            'tokens': tokens,
            'is_new_user': is_new_user,
        },
    }, status=status.HTTP_200_OK if not is_new_user else status.HTTP_201_CREATED)
