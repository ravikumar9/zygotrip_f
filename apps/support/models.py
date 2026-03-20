from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class SupportTicket(TimeStampedModel):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    CHANNEL_APP = 'app'
    CHANNEL_EMAIL = 'email'
    CHANNEL_WHATSAPP = 'whatsapp'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]
    CHANNEL_CHOICES = [
        (CHANNEL_APP, 'In App'),
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    booking = models.ForeignKey(
        'booking.Booking',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='support_tickets',
    )
    subject = models.CharField(max_length=160)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_APP)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_support_tickets',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='support_ticket_user_idx'),
            models.Index(fields=['status', 'priority'], name='support_ticket_status_idx'),
        ]

    def __str__(self):
        return f'Ticket#{self.id} {self.subject}'


class SupportTicketMessage(TimeStampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_messages')
    message = models.TextField()
    is_staff_reply = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message#{self.id} ticket={self.ticket_id}'
