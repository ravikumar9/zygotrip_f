import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.fcm_service import FCMService
from apps.core.whatsapp_notifications import whatsapp_client

from .models import SupportTicket, SupportTicketMessage
from .permissions import IsTicketOwnerOrStaff
from .serializers import (
    SupportTicketCreateSerializer,
    SupportTicketMessageSerializer,
    SupportTicketSerializer,
    SupportTicketUpdateSerializer,
)

logger = logging.getLogger('zygotrip.support')


def _notify_ticket_created(ticket: SupportTicket):
    user = ticket.user
    ticket_ref = f'SUP-{ticket.id:06d}'

    if user.email:
        send_mail(
            subject=f'Support ticket received: {ticket_ref}',
            message=(
                f'Hi {user.full_name},\n\n'
                f'We received your support request.\n'
                f'Reference: {ticket_ref}\n'
                f'Subject: {ticket.subject}\n\n'
                f'Our team will respond soon.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@zygotrip.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )

    if user.phone:
        whatsapp_client.send_template(
            user.phone,
            'support_ticket_created',
            components=[{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': user.full_name or 'Traveler'},
                    {'type': 'text', 'text': ticket_ref},
                    {'type': 'text', 'text': ticket.subject[:40]},
                ],
            }],
        )

    FCMService().send_to_user(
        user=user,
        title='Support ticket created',
        body=f'Your ticket {ticket_ref} is now open.',
        data={'type': 'support_ticket_created', 'ticket_id': str(ticket.id)},
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def support_ticket_list_create(request):
    if request.method == 'GET':
        qs = SupportTicket.objects.select_related('user', 'assigned_to').prefetch_related('messages', 'messages__author')
        if not request.user.is_staff:
            qs = qs.filter(user=request.user)

        status_filter = (request.GET.get('status') or '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = SupportTicketSerializer(qs[:100], many=True).data
        return Response({'results': data})

    serializer = SupportTicketCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ticket = serializer.save(user=request.user, status=SupportTicket.STATUS_OPEN)

    initial_message = (request.data.get('message') or '').strip()
    if initial_message:
        SupportTicketMessage.objects.create(
            ticket=ticket,
            author=request.user,
            message=initial_message,
            is_staff_reply=False,
        )

    _notify_ticket_created(ticket)
    return Response({'success': True, 'data': SupportTicketSerializer(ticket).data}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def support_ticket_detail(request, ticket_id):
    try:
        ticket = SupportTicket.objects.select_related('user', 'assigned_to').prefetch_related('messages', 'messages__author').get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return Response({'success': False, 'error': {'code': 'not_found', 'message': 'Ticket not found'}}, status=status.HTTP_404_NOT_FOUND)

    permission = IsTicketOwnerOrStaff()
    if not permission.has_object_permission(request, None, ticket):
        return Response({'success': False, 'error': {'code': 'forbidden', 'message': 'Not allowed'}}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response({'success': True, 'data': SupportTicketSerializer(ticket).data})

    if not request.user.is_staff:
        return Response({'success': False, 'error': {'code': 'forbidden', 'message': 'Only staff can update ticket state'}}, status=status.HTTP_403_FORBIDDEN)

    serializer = SupportTicketUpdateSerializer(ticket, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'success': True, 'data': SupportTicketSerializer(ticket).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def support_ticket_add_message(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return Response({'success': False, 'error': {'code': 'not_found', 'message': 'Ticket not found'}}, status=status.HTTP_404_NOT_FOUND)

    permission = IsTicketOwnerOrStaff()
    if not permission.has_object_permission(request, None, ticket):
        return Response({'success': False, 'error': {'code': 'forbidden', 'message': 'Not allowed'}}, status=status.HTTP_403_FORBIDDEN)

    message = (request.data.get('message') or '').strip()
    if not message:
        return Response({'success': False, 'error': {'code': 'invalid', 'message': 'message is required'}}, status=status.HTTP_400_BAD_REQUEST)

    row = SupportTicketMessage.objects.create(
        ticket=ticket,
        author=request.user,
        message=message,
        is_staff_reply=bool(request.user.is_staff),
    )

    serializer = SupportTicketMessageSerializer(row)
    return Response({'success': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)
