"""
Auth REST API v1.
Endpoints:
  POST /api/v1/auth/register/           — Register (sends OTP, user inactive)
  POST /api/v1/auth/verify-otp/         — Verify OTP → activate + return tokens
  POST /api/v1/auth/resend-otp/         — Resend OTP
  POST /api/v1/auth/login/              — Login with email+password
  POST /api/v1/auth/token/refresh/      — Refresh access token
  POST /api/v1/auth/logout/             — Blacklist refresh token
  POST /api/v1/auth/forgot-password/    — Send OTP for password reset
  POST /api/v1/auth/reset-password/     — Reset password with OTP
  GET  /api/v1/users/me/                — Current user profile
  PUT  /api/v1/users/me/                — Update profile
"""
import logging
import random
import string
from django.core.cache import cache
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
    rate = '20/min'

class RegisterThrottle(AnonRateThrottle):
    rate = '10/min'

def _token_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def _send_otp_to_user(user, otp):
    """Send OTP via MSG91 to phone and email."""
    sent = False
    # Send SMS OTP
    if user.phone:
        try:
            from apps.accounts.sms_service import send_otp
            sent = send_otp(user.phone, otp)
            logger.info('OTP SMS sent to user=%s phone=%s', user.id, user.phone)
        except Exception as e:
            logger.error('OTP SMS failed for user %s: %s', user.id, e)
    # Send email OTP
    try:
        from apps.core.email_service import send_otp_email
        send_otp_email(user.email, otp, purpose='registration')
        sent = True
        logger.info('OTP email sent to user=%s email=%s', user.id, user.email)
    except Exception as e:
        logger.error('OTP email failed for user %s: %s', user.id, e)
    return sent

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def register_view(request):
    """
    POST /api/v1/auth/register/
    Creates user with is_active=False, sends OTP.
    Returns: { success, message, user_id }
    """
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Check if user exists but unverified - resend OTP instead
    from apps.accounts.models import User as _User
    existing_email = request.data.get('email', '').lower()
    unverified = _User.objects.filter(email=existing_email, is_active=False).first()
    if unverified:
        otp = _generate_otp()
        cache.set(f'reg_otp_{unverified.id}', otp, timeout=600)
        _send_otp_to_user(unverified, otp)
        return Response({
            'success': True,
            'message': 'Account already registered but not verified. OTP resent.',
            'user_id': unverified.id,
            'email': unverified.email,
            'phone': unverified.phone,
            'resent': True,
        }, status=status.HTTP_201_CREATED)

    try:
        user = serializer.save()
        # Set user inactive until OTP verified
        user.is_active = False
        user.save(update_fields=['is_active'])
    except Exception as e:
        err_str = str(e).lower()
        if 'unique' in err_str or 'duplicate' in err_str or 'already exists' in err_str:
            if 'phone' in err_str:
                msg = 'An account with this phone number already exists.'
                field = 'phone'
            elif 'email' in err_str:
                msg = 'An account with this email already exists.'
                field = 'email'
            else:
                msg = 'An account with these details already exists.'
                field = 'non_field_errors'
            return Response(
                {'success': False, 'error': {'code': 'validation_error', 'message': {field: [msg]}}},
                status=400,
            )
        logger.exception('Unexpected error during user registration')
        return Response(
            {'success': False, 'error': {'code': 'internal_error', 'message': 'Registration failed. Please try again.'}},
            status=500,
        )

    # Generate and cache OTP (10 min expiry)
    otp = _generate_otp()
    cache_key = f'reg_otp_{user.id}'
    cache.set(cache_key, otp, timeout=600)
    logger.info('Registration OTP generated for user=%s', user.id)

    # Send OTP
    _send_otp_to_user(user, otp)

    # Process referral code
    referral_code = getattr(user, '_raw_referral_code', '')
    if referral_code:
        try:
            from apps.referrals.services import process_signup_referral
            process_signup_referral(new_user=user, referral_code=referral_code)
        except Exception:
            logger.exception('Referral processing failed for user=%s', user.id)

    return Response({
        'success': True,
        'message': 'OTP sent to your phone and email. Please verify to complete registration.',
        'user_id': user.id,
        'email': user.email,
        'phone': user.phone,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def verify_otp_view(request):
    """
    POST /api/v1/auth/verify-otp/
    Body: { user_id, otp }
    Activates user and returns JWT tokens.
    """
    user_id = request.data.get('user_id')
    otp = request.data.get('otp', '').strip()

    if not user_id or not otp:
        return Response(
            {'success': False, 'error': 'user_id and otp are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.accounts.models import User
    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        return Response(
            {'success': False, 'error': 'Invalid user or already verified'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cache_key = f'reg_otp_{user_id}'
    stored_otp = cache.get(cache_key)

    if not stored_otp:
        return Response(
            {'success': False, 'error': 'OTP expired. Please request a new one.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if stored_otp != otp:
        return Response(
            {'success': False, 'error': 'Invalid OTP. Please try again.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Activate user
    user.is_active = True
    user.save(update_fields=['is_active'])
    cache.delete(cache_key)

    # Send welcome email
    try:
        from apps.core.email_service import send_welcome_email
        send_welcome_email(user.email, user.full_name or 'Traveler')
    except Exception:
        pass

    logger.info('User %s verified and activated', user.id)

    return Response({
        'success': True,
        'message': 'Account verified successfully!',
        'data': {
            'user': UserSerializer(user).data,
            'tokens': _token_response(user),
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def resend_otp_view(request):
    """
    POST /api/v1/auth/resend-otp/
    Body: { user_id }
    """
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'success': False, 'error': 'user_id required'}, status=400)

    from apps.accounts.models import User
    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        return Response({'success': False, 'error': 'Invalid user or already verified'}, status=400)

    # Rate limit: max 3 resends per 10 min
    resend_key = f'reg_otp_resend_{user_id}'
    resend_count = cache.get(resend_key, 0)
    if resend_count >= 3:
        return Response({'success': False, 'error': 'Too many OTP requests. Please wait 10 minutes.'}, status=429)

    otp = _generate_otp()
    cache.set(f'reg_otp_{user_id}', otp, timeout=600)
    cache.set(resend_key, resend_count + 1, timeout=600)

    _send_otp_to_user(user, otp)
    logger.info('OTP resent for user=%s', user_id)

    return Response({'success': True, 'message': 'OTP resent successfully.'})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def login_view(request):
    """
    POST /api/v1/auth/login/
    Body: { email, password }
    Returns JWT tokens.
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = serializer.validated_data['user']

    # Check if user is verified
    if not user.is_active:
        # Resend OTP for unverified users
        otp = _generate_otp()
        cache.set(f'reg_otp_{user.id}', otp, timeout=600)
        _send_otp_to_user(user, otp)
        return Response({
            'success': False,
            'error': 'Account not verified. A new OTP has been sent.',
            'code': 'unverified',
            'user_id': user.id,
        }, status=status.HTTP_403_FORBIDDEN)

    logger.info('User %s logged in', user.id)
    return Response({
        'success': True,
        'data': {
            'user': UserSerializer(user).data,
            'tokens': _token_response(user),
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def forgot_password_view(request):
    """
    POST /api/v1/auth/forgot-password/
    Body: { email }
    Sends OTP for password reset.
    """
    email = request.data.get('email', '').lower().strip()
    if not email:
        return Response({'success': False, 'error': 'Email required'}, status=400)

    from apps.accounts.models import User
    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        # Don't reveal if email exists
        return Response({'success': True, 'message': 'If this email exists, an OTP has been sent.'})

    otp = _generate_otp()
    cache.set(f'reset_otp_{user.id}', otp, timeout=600)

    try:
        from apps.core.email_service import send_transactional_email
        send_transactional_email(
            to_email=user.email,
            subject='ZygoTrip Password Reset OTP',
            body=f'Your password reset OTP is: {otp}\n\nValid for 10 minutes. Do not share.\n\n— Team ZygoTrip',
        )
    except Exception as e:
        logger.error('Reset OTP email failed: %s', e)

    if user.phone:
        try:
            from apps.accounts.sms_service import send_otp
            send_otp(user.phone, otp)
        except Exception:
            pass

    return Response({
        'success': True,
        'message': 'OTP sent to your registered email and phone.',
        'user_id': user.id,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthBurstThrottle])
def reset_password_view(request):
    """
    POST /api/v1/auth/reset-password/
    Body: { user_id, otp, new_password }
    """
    user_id = request.data.get('user_id')
    otp = request.data.get('otp', '').strip()
    new_password = request.data.get('new_password', '')

    if not all([user_id, otp, new_password]):
        return Response({'success': False, 'error': 'user_id, otp and new_password required'}, status=400)

    if len(new_password) < 8:
        return Response({'success': False, 'error': 'Password must be at least 8 characters'}, status=400)

    from apps.accounts.models import User
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'success': False, 'error': 'Invalid user'}, status=400)

    stored_otp = cache.get(f'reset_otp_{user_id}')
    if not stored_otp or stored_otp != otp:
        return Response({'success': False, 'error': 'Invalid or expired OTP'}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])
    cache.delete(f'reset_otp_{user_id}')

    logger.info('Password reset for user=%s', user_id)
    return Response({'success': True, 'message': 'Password reset successfully. Please login.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'success': False, 'error': 'Refresh token required'}, status=400)
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except TokenError:
        pass
    return Response({'success': True, 'message': 'Logged out successfully.'})


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def me_view(request):
    if request.method == 'GET':
        return Response({'success': True, 'data': {'user': UserSerializer(request.user).data}})
    serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({'success': False, 'error': serializer.errors}, status=400)
    serializer.save()
    return Response({'success': True, 'data': {'user': UserSerializer(request.user).data}})
