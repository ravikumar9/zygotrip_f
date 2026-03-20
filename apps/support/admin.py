from django.contrib import admin

from .models import SupportTicket, SupportTicketMessage


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'channel', 'created_at')
    search_fields = ('subject', 'description', 'user__email')


@admin.register(SupportTicketMessage)
class SupportTicketMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'author', 'is_staff_reply', 'created_at')
    list_filter = ('is_staff_reply', 'created_at')
    search_fields = ('ticket__subject', 'message', 'author__email')
