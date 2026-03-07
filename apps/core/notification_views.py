"""
Notification REST API views.

Endpoints (mounted at /api/v1/notifications/):
  GET    /                         — List notifications (paginated, filterable)
  POST   /mark-read/               — Mark one or all notifications as read
  GET    /unread-count/            — Get unread notification count
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils import timezone

from apps.core.notifications import Notification

logger = logging.getLogger('zygotrip.notifications')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """
    GET /api/v1/notifications/

    Query params:
      ?unread=true     — Only unread
      ?category=booking — Filter by category
      ?page=1&page_size=20
    """
    qs = Notification.objects.filter(user=request.user)

    if request.query_params.get('unread') == 'true':
        qs = qs.filter(is_read=False)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    page_size = min(int(request.query_params.get('page_size', 20)), 100)
    page = max(int(request.query_params.get('page', 1)), 1)
    offset = (page - 1) * page_size

    total = qs.count()
    notifications = qs[offset:offset + page_size]

    data = [
        {
            'id': n.id,
            'category': n.category,
            'title': n.title,
            'message': n.message,
            'data': n.data,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        }
        for n in notifications
    ]

    return Response({
        'success': True,
        'data': {
            'results': data,
            'total': total,
            'page': page,
            'page_size': page_size,
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """
    POST /api/v1/notifications/mark-read/

    Body:
      { "notification_id": 123 }    — Mark single notification
      { "all": true }               — Mark all as read
    """
    notification_id = request.data.get('notification_id')
    mark_all = request.data.get('all', False)

    if mark_all:
        updated = Notification.objects.filter(
            user=request.user, is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response({
            'success': True,
            'data': {'marked_count': updated},
        })

    if notification_id:
        try:
            notification = Notification.objects.get(
                id=notification_id, user=request.user,
            )
            notification.mark_read()
            return Response({
                'success': True,
                'data': {'marked_count': 1},
            })
        except Notification.DoesNotExist:
            return Response(
                {'success': False, 'error': {'code': 'not_found', 'message': 'Notification not found'}},
                status=status.HTTP_404_NOT_FOUND,
            )

    return Response(
        {'success': False, 'error': {'code': 'validation_error', 'message': 'Provide notification_id or all=true'}},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """GET /api/v1/notifications/unread-count/"""
    count = Notification.objects.filter(
        user=request.user, is_read=False,
    ).count()
    return Response({
        'success': True,
        'data': {'unread_count': count},
    })
