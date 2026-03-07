from django.contrib import admin
from .models import Payment


# PHASE 9: Register Payment model for transaction tracking
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'booking', 'amount', 'status', 'payment_method', 'created_at')
	list_filter = ('status', 'payment_method', 'created_at')
	search_fields = ('user__email', 'booking__id', 'transaction_id')
	readonly_fields = ('transaction_id', 'created_at', 'updated_at')
	
	fieldsets = (
		('Booking & User', {
			'fields': ('booking', 'user')
		}),
		('Payment Details', {
			'fields': ('amount', 'payment_method', 'transaction_id', 'status')
		}),
		('Timestamps', {
			'fields': ('created_at', 'updated_at'),
			'classes': ('collapse',)
		}),
	)
