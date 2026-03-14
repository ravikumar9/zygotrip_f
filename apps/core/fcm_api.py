"""
FCM Device Token Registration API — System 8: Push Notifications.

Allows mobile clients to register/update their FCM device token so the server
can send push notifications for booking events.

Endpoints:
  POST /api/v1/devices/register/       — Register or update FCM token
  DELETE /api/v1/devices/unregister/   — Remove FCM token (logout)
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger('zygotrip.push.fcm')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device(request):
    """
    POST /api/v1/devices/register/
    Body: { fcm_token: string, platform: 'android'|'ios'|'web' }
    """
    fcm_token = request.data.get('fcm_token', '').strip()
    platform = request.data.get('platform', 'android')

    if not fcm_token:
        return Response({'error': 'fcm_token is required'}, status=400)

    if platform not in ('android', 'ios', 'web'):
        return Response({'error': 'platform must be android, ios, or web'}, status=400)

    try:
        from apps.core.device_fingerprint import DeviceFingerprint
        # Store FCM token in device fingerprint record for this user
        # Use update_or_create keyed on user + fcm_token to avoid duplicates
        obj, created = DeviceFingerprint.objects.update_or_create(
            user=request.user,
            fcm_token=fcm_token,
            defaults={
                'platform': platform,
                'is_mobile': platform in ('android', 'ios'),
            }
        )
        logger.info('FCM token %s for user %s (%s)', 'registered' if created else 'updated', request.user.id, platform)
        return Response({'status': 'registered', 'platform': platform})
    except Exception as exc:
        logger.error('register_device failed: %s', exc)
        return Response({'error': 'Failed to register device'}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unregister_device(request):
    """
    DELETE /api/v1/devices/unregister/
    Body: { fcm_token: string }
    """
    fcm_token = request.data.get('fcm_token', '').strip()
    if not fcm_token:
        return Response({'error': 'fcm_token is required'}, status=400)

    try:
        from apps.core.device_fingerprint import DeviceFingerprint
        deleted, _ = DeviceFingerprint.objects.filter(
            user=request.user,
            fcm_token=fcm_token,
        ).delete()
        return Response({'status': 'unregistered', 'removed': deleted})
    except Exception as exc:
        logger.error('unregister_device failed: %s', exc)
        return Response({'error': 'Failed to unregister device'}, status=500)
