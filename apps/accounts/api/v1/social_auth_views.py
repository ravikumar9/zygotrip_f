"""Social authentication endpoints for Google and Apple sign-in."""
import logging
from typing import Optional

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
User = get_user_model()


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def _ensure_wallet(user):
    """Create wallet for new user if it doesn't exist."""
    try:
        from apps.wallet.models import Wallet
        Wallet.objects.get_or_create(user=user)
    except Exception as exc:
        logger.warning('ensure_wallet failed user=%s err=%s', user.id, exc)


def _full_name_from_email(email: str) -> str:
    return (email.split('@')[0] or 'Traveler').replace('.', ' ').title()


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get('id_token') or '').strip()
        if not token:
            return Response({'error': 'id_token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token as google_id_token

            id_info = google_id_token.verify_oauth2_token(
                token,
                Request(),
                getattr(settings, 'GOOGLE_CLIENT_ID', ''),
            )
        except Exception as exc:
            logger.exception('Google token verification failed: %s', exc)
            return Response({'error': 'Invalid Google id_token'}, status=status.HTTP_401_UNAUTHORIZED)

        email = (id_info.get('email') or '').strip().lower()
        name = (id_info.get('name') or '').strip()
        google_sub = (id_info.get('sub') or '').strip()
        if not email:
            return Response({'error': 'Email missing from token'}, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': name or _full_name_from_email(email),
                    'role': 'traveler',
                    'google_id': google_sub or None,
                },
            )
            updates = []
            if google_sub and user.google_id != google_sub:
                user.google_id = google_sub
                updates.append('google_id')
            if name and user.full_name != name:
                user.full_name = name
                updates.append('full_name')
            if created:
                user.set_unusable_password()
                _ensure_wallet(user)
            if updates or created:
                user.save()

        tokens = _issue_tokens(user)
        return Response(
            {
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'is_new_user': created,
            },
            status=status.HTTP_200_OK,
        )


def _resolve_apple_public_key(identity_token: str):
    import jwt
    from jwt.algorithms import RSAAlgorithm

    header = jwt.get_unverified_header(identity_token)
    kid = header.get('kid')
    key_set = requests.get('https://appleid.apple.com/auth/keys', timeout=10).json()
    for key_data in key_set.get('keys', []):
        if key_data.get('kid') == kid:
            return RSAAlgorithm.from_jwk(key_data)
    return None


class AppleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identity_token = (request.data.get('identity_token') or '').strip()
        if not identity_token:
            return Response({'error': 'identity_token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            import jwt

            public_key = _resolve_apple_public_key(identity_token)
            if public_key is None:
                return Response({'error': 'Unable to resolve Apple public key'}, status=status.HTTP_401_UNAUTHORIZED)
            payload = jwt.decode(
                identity_token,
                public_key,
                algorithms=['RS256'],
                audience=getattr(settings, 'APPLE_BUNDLE_ID', ''),
                issuer='https://appleid.apple.com',
            )
        except Exception as exc:
            logger.exception('Apple token verification failed: %s', exc)
            return Response({'error': 'Invalid Apple identity_token'}, status=status.HTTP_401_UNAUTHORIZED)

        apple_sub = (payload.get('sub') or '').strip()
        email = (payload.get('email') or '').strip().lower()
        if not apple_sub and not email:
            return Response({'error': 'Identity payload missing sub/email'}, status=status.HTTP_400_BAD_REQUEST)

        if not email:
            email = f'{apple_sub}@privaterelay.appleid.com'

        with db_transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': _full_name_from_email(email),
                    'role': 'traveler',
                    'apple_sub': apple_sub or None,
                },
            )
            if apple_sub and user.apple_sub != apple_sub:
                user.apple_sub = apple_sub
                user.save(update_fields=['apple_sub'])
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
                _ensure_wallet(user)

        tokens = _issue_tokens(user)
        return Response(
            {
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'is_new_user': created,
            },
            status=status.HTTP_200_OK,
        )


def google_auth(request):
    return GoogleAuthView().post(request)


def apple_auth(request):
    return AppleAuthView().post(request)
