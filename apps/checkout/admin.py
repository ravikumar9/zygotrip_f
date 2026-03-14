"""Checkout admin registration."""
from django.contrib import admin

from .models import BookingSession, InventoryToken, PaymentIntent, PaymentAttempt, PaymentWebhook
from .analytics_models import BookingAnalytics, FunnelConversionDaily, BookingRiskScore


@admin.register(BookingSession)
class BookingSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'user', 'hotel', 'room_type',
        'session_status', 'expires_at', 'created_at',
    ]
    list_filter = ['session_status', 'created_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'search_snapshot', 'price_snapshot', 'guest_details']
    raw_id_fields = ['user', 'hotel', 'room_type', 'inventory_token', 'booking_context', 'booking']


@admin.register(InventoryToken)
class InventoryTokenAdmin(admin.ModelAdmin):
    list_display = [
        'token_id', 'hotel', 'room_type', 'date_start', 'date_end',
        'reserved_rooms', 'token_status', 'expires_at',
    ]
    list_filter = ['token_status']
    readonly_fields = ['token_id', 'hold_ids']


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = [
        'intent_id', 'booking_session', 'amount', 'currency',
        'payment_status', 'price_revalidated', 'created_at',
    ]
    list_filter = ['payment_status', 'currency']
    search_fields = ['intent_id', 'idempotency_key']
    readonly_fields = ['intent_id']
    raw_id_fields = ['booking_session', 'payment_transaction', 'booking']


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'attempt_id', 'payment_intent', 'gateway', 'amount',
        'attempt_status', 'created_at',
    ]
    list_filter = ['attempt_status', 'gateway']
    readonly_fields = ['attempt_id', 'gateway_response']
    raw_id_fields = ['payment_intent']


@admin.register(PaymentWebhook)
class PaymentWebhookAdmin(admin.ModelAdmin):
    list_display = [
        'webhook_id', 'gateway', 'event_type', 'processed_status',
        'processed_at', 'created_at',
    ]
    list_filter = ['gateway', 'processed_status', 'event_type']
    readonly_fields = ['webhook_id', 'payload', 'headers']
    raw_id_fields = ['payment_attempt', 'payment_transaction']


@admin.register(BookingAnalytics)
class BookingAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'session_id', 'property_id',
        'revenue_amount', 'device_type', 'event_timestamp',
    ]
    list_filter = ['event_type', 'device_type', 'event_timestamp']
    search_fields = ['session_id']
    readonly_fields = ['event_id', 'metadata']


@admin.register(FunnelConversionDaily)
class FunnelConversionDailyAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'city', 'search_views', 'hotel_clicks',
        'checkout_starts', 'booking_successes',
        'overall_conversion_rate', 'total_revenue',
    ]
    list_filter = ['city', 'date']


@admin.register(BookingRiskScore)
class BookingRiskScoreAdmin(admin.ModelAdmin):
    list_display = [
        'risk_id', 'user', 'risk_score', 'risk_level',
        'action_taken', 'ip_address', 'created_at',
    ]
    list_filter = ['risk_level', 'action_taken']
    search_fields = ['ip_address', 'user__email']
    readonly_fields = ['risk_id', 'risk_factors']
    raw_id_fields = ['booking_session', 'booking', 'user']
