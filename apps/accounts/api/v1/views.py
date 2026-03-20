"""
Auth REST API v1.

Endpoints:
  POST /api/v1/auth/register/        — Register + receive JWT tokens
  POST /api/v1/auth/login/           — Login + receive JWT tokens
  POST /api/v1/auth/token/refresh/   — Refresh access token
  POST /api/v1/auth/logout/          — Blacklist refresh token
  GET  /api/v1/users/me/             — Current user profile
  PUT  /api/v1/users/me/             — Update profile
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, UpdateProfileSerializer

logger = logging.getLogger('zygotrip.api.auth')


class AuthBurstThrottle(AnonRateThrottle):
    """Strict rate limit for auth endpoints: 5 requests/minute per IP."""
    rate = '5/min'


class RegisterThrottle(AnonRateThrottle):
    """Registration: 3 per minute, 10 per hour per IP."""
    rate = '3/min'


def _token_response(user):
    """Generate JWT access + refresh token pair for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def register_view(request):
    """
    POST /api/v1/auth/register/

    Body: { email, password, full_name, phone?, role? }
    Returns: { success, data: { user, tokens: { access, refresh } } }
    """
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()
    referral_code = getattr(user, '_raw_referral_code', '')
    if referral_code:
        try:
            from apps.referrals.services import process_signup_referral
            process_signup_referral(new_user=user, referral_code=referral_code)
        except Exception:
            logger.exception('Referral processing failed for user=%s', user.id)

    try:
        from apps.core.email_service import send_welcome_email
        send_welcome_email(user.email, getattr(user, 'full_name', '') or 'Traveler')
    except Exception:
        pass

    tokens = _token_response(user)
    logger.info('New user registered: %s (role=%s)', user.email, user.role)

    return Response(
        {
            'success': True,
            'data': {
                'user': UserSerializer(user).data,
                'tokens': tokens,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def login_view(request):
    """
    POST /api/v1/auth/login/

    Body: { email, password }
    Returns: { success, data: { user, tokens: { access, refresh } } }
    """
    # Fraud detection — check login velocity
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    try:
        from apps.core.fraud_detection import assess_login_risk, record_login_failure, FraudFlag
        risk = assess_login_risk(client_ip, request.data.get('email', ''))
        if risk['action'] == FraudFlag.ACTION_BLOCK:
            logger.warning('Login blocked by fraud detection: ip=%s', client_ip)
            return Response(
                {'success': False, 'error': {'code': 'rate_limited', 'message': 'Too many failed attempts. Try again later.'}},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
    except Exception:
        pass  # Don't block login if fraud service fails

    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        # Record failed login for fraud scoring
        try:
            from apps.core.fraud_detection import record_login_failure
            record_login_failure(client_ip)
        except Exception:
            pass
        return Response(
            {'success': False, 'error': {'code': 'auth_error', 'message': serializer.errors}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user = serializer.validated_data['user']
    tokens = _token_response(user)
    logger.info('User logged in: %s', user.email)

    # Collect device fingerprint on successful login
    try:
        from apps.core.device_fingerprint import FingerprintService
        FingerprintService.collect_from_request(request)
    except Exception:
        pass  # Non-blocking

    return Response(
        {
            'success': True,
            'data': {
                'user': UserSerializer(user).data,
                'tokens': tokens,
            },
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/v1/auth/logout/

    Body: { refresh }
    Blacklists the refresh token, invalidating the session.
    """
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response(
            {'success': False, 'error': {'code': 'missing_token', 'message': 'Refresh token required.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except TokenError:
        # Already invalid — treat as success (idempotent logout)
        pass

    return Response({'success': True, 'data': {'message': 'Logged out successfully.'}})


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    GET  /api/v1/users/me/  — Return current user profile
    PUT  /api/v1/users/me/  — Update full_name, phone
    PATCH /api/v1/users/me/ — Partial update
    """
    user = request.user

    if request.method == 'GET':
        return Response({'success': True, 'data': UserSerializer(user).data})

    partial = request.method == 'PATCH'
    serializer = UpdateProfileSerializer(user, data=request.data, partial=partial)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save()
    return Response({'success': True, 'data': UserSerializer(user).data})
