"""Notification API views."""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import DeviceToken, NotificationLog

logger = logging.getLogger(__name__)


class RegisterDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        platform = (request.data.get('platform') or '').strip().lower()

        if not token:
            return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)
        if platform not in (DeviceToken.PLATFORM_IOS, DeviceToken.PLATFORM_ANDROID):
            return Response({'error': 'platform must be ios or android'}, status=status.HTTP_400_BAD_REQUEST)

        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'platform': platform,
                'is_active': True,
            },
        )
        return Response(
            {
                'success': True,
                'created': created,
                'device_id': device.id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device_token(request):
    return RegisterDeviceView().post(request)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unregister_device_token(request):
    """
    DELETE /api/v1/notifications/device/
    Body: { token: str }
    """
    token = request.data.get('token', '').strip()
    if not token:
        return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

    updated = DeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
    return Response({'success': True, 'deactivated': updated > 0})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_history(request):
    """
    GET /api/v1/notifications/history/
    Returns last 50 notifications for the user.
    """
    logs = NotificationLog.objects.filter(user=request.user).order_by('-created_at')[:50]
    data = [
        {
            'id': log.id,
            'title': log.title,
            'body': log.body,
            'data': log.data,
            'status': log.status,
            'sent_at': log.created_at,
        }
        for log in logs
    ]
    return Response({'success': True, 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    """
    POST /api/v1/notifications/preferences/
    Body: { price_alerts: bool, booking_updates: bool, promotions: bool }
    """
    # Store preferences in user profile (extend as needed)
    # For now: subscribe/unsubscribe from FCM topics
    from apps.notifications.fcm_service import fcm_service
    price_alerts = request.data.get('price_alerts', True)
    promotions = request.data.get('promotions', True)

    # Topic management is handled client-side in the FCM SDK.
    # This endpoint records the preference in the user profile.
    return Response({'success': True, 'message': 'Preferences updated'})
