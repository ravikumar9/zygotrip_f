from django.contrib import admin
from .models import Booking, BookingGuest, BookingPriceBreakdown, BookingStatusHistory, BookingContext
from .settlement_models import Settlement, SettlementLineItem
from .cancellation_models import CancellationPolicy, RatePlanPolicy


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['public_booking_id', 'user', 'property', 'check_in', 'check_out', 'status', 'total_amount']
    list_filter = ['status', 'settlement_status']
    search_fields = ['public_booking_id', 'user__email', 'property__name']
    readonly_fields = ['uuid', 'public_booking_id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(BookingContext)
class BookingContextAdmin(admin.ModelAdmin):
    list_display = ['property', 'checkin', 'checkout', 'adults', 'rooms', 'final_price', 'context_status', 'user']
    list_filter = ['context_status']
    search_fields = ['property__name', 'user__email', 'session_key']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CancellationPolicy)
class CancellationPolicyAdmin(admin.ModelAdmin):
    list_display = ['property', 'policy_type', 'free_cancel_hours', 'partial_refund_percent']
    list_filter = ['policy_type']


admin.site.register(BookingGuest)
admin.site.register(BookingPriceBreakdown)
admin.site.register(BookingStatusHistory)
admin.site.register(Settlement)
admin.site.register(SettlementLineItem)


@admin.register(RatePlanPolicy)
class RatePlanPolicyAdmin(admin.ModelAdmin):
    list_display = ['room_type', 'plan_name', 'plan_type', 'price_modifier_percent', 'free_cancel_hours', 'is_active']
    list_filter = ['plan_type', 'is_active']
    search_fields = ['plan_name', 'room_type__name']

# BookingInvoice admin (System 14)
try:
    from apps.booking.models import BookingInvoice

    @admin.register(BookingInvoice)
    class BookingInvoiceAdmin(admin.ModelAdmin):
        list_display = ['invoice_number', 'booking', 'customer_name', 'final_customer_price', 'owner_payout_amount', 'status', 'issued_at']
        list_filter = ['status', 'issued_at']
        search_fields = ['invoice_number', 'customer_name', 'booking__public_booking_id']
        readonly_fields = ['invoice_number', 'issued_at', 'created_at', 'updated_at']
        ordering = ['-created_at']
except Exception:
    pass
