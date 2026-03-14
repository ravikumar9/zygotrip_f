"""
Checkout API Serializers — OTA-grade request/response validation.

Handles:
  - Session creation (start checkout)
  - Guest details submission
  - Payment initiation
  - Session status response
"""
from datetime import date, timedelta

from rest_framework import serializers


# ============================================================================
# REQUEST SERIALIZERS
# ============================================================================

class StartCheckoutSerializer(serializers.Serializer):
    """POST /api/v1/checkout/start/"""
    property_id = serializers.IntegerField()
    room_type_id = serializers.IntegerField()
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    guests = serializers.IntegerField(default=2, min_value=1, max_value=20)
    rooms = serializers.IntegerField(default=1, min_value=1, max_value=10)
    rate_plan_id = serializers.CharField(required=False, default='', allow_blank=True)
    meal_plan_code = serializers.CharField(required=False, default='', allow_blank=True)
    promo_code = serializers.CharField(required=False, default='', allow_blank=True)

    def validate_check_in(self, value):
        if value < date.today():
            raise serializers.ValidationError("check_in cannot be in the past")
        return value

    def validate(self, data):
        if data['check_out'] <= data['check_in']:
            raise serializers.ValidationError("check_out must be after check_in")
        nights = (data['check_out'] - data['check_in']).days
        if nights > 30:
            raise serializers.ValidationError("Maximum 30 nights per booking")
        return data


class GuestDetailsSerializer(serializers.Serializer):
    """POST /api/v1/checkout/{session_id}/guest-details/"""
    name = serializers.CharField(max_length=200, min_length=2)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, min_length=10)
    special_requests = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=1000,
    )


class InitiatePaymentSerializer(serializers.Serializer):
    """POST /api/v1/checkout/{session_id}/pay/"""
    gateway = serializers.ChoiceField(choices=[
        ('wallet', 'Wallet'),
        ('cashfree', 'Cashfree'),
        ('stripe', 'Stripe'),
        ('paytm_upi', 'Paytm UPI'),
        ('dev_simulate', 'Dev Simulate'),
    ])
    idempotency_key = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=128,
    )


# ============================================================================
# RESPONSE SERIALIZERS
# ============================================================================

class PriceSnapshotSerializer(serializers.Serializer):
    base_price = serializers.CharField()
    meal_amount = serializers.CharField()
    service_fee = serializers.CharField()
    gst = serializers.CharField()
    total = serializers.CharField()
    tariff_per_night = serializers.CharField()
    property_discount = serializers.CharField(required=False, default='0')
    platform_discount = serializers.CharField(required=False, default='0')
    demand_adjustment = serializers.CharField(required=False, default='0')
    advance_modifier = serializers.CharField(required=False, default='0')


class InventoryTokenResponseSerializer(serializers.Serializer):
    token_id = serializers.UUIDField()
    token_status = serializers.CharField()
    date_start = serializers.DateField()
    date_end = serializers.DateField()
    reserved_rooms = serializers.IntegerField()
    expires_at = serializers.DateTimeField()


class CheckoutSessionResponseSerializer(serializers.Serializer):
    """Full session response."""
    session_id = serializers.UUIDField()
    session_status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    property_id = serializers.IntegerField(source='hotel.id')
    property_name = serializers.CharField(source='hotel.name')
    room_type_id = serializers.IntegerField(source='room_type.id')
    room_type_name = serializers.CharField(source='room_type.name')
    search_snapshot = serializers.JSONField()
    price_snapshot = serializers.JSONField()
    guest_details = serializers.JSONField()
    price_revalidated_at = serializers.DateTimeField()
    price_changed = serializers.BooleanField()
    inventory_token = InventoryTokenResponseSerializer(allow_null=True)
    created_at = serializers.DateTimeField()


class PaymentIntentResponseSerializer(serializers.Serializer):
    """Payment intent response."""
    intent_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    original_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    price_revalidated = serializers.BooleanField()
    price_delta = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_status = serializers.CharField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()


class PaymentAttemptResponseSerializer(serializers.Serializer):
    """Payment attempt response."""
    attempt_id = serializers.UUIDField()
    gateway = serializers.CharField()
    attempt_status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    failure_reason = serializers.CharField()
    created_at = serializers.DateTimeField()


class BookingConfirmationSerializer(serializers.Serializer):
    """Final booking confirmation response."""
    booking_uuid = serializers.UUIDField(source='uuid')
    booking_id = serializers.CharField(source='public_booking_id')
    status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    property_name = serializers.SerializerMethodField()
    room_type_name = serializers.SerializerMethodField()

    def get_property_name(self, obj):
        return getattr(obj.property, 'name', '') if obj.property else ''

    def get_room_type_name(self, obj):
        booking_room = obj.rooms.select_related('room_type').first()
        if not booking_room or not booking_room.room_type:
            return ''
        return booking_room.room_type.name


class RiskScoreResponseSerializer(serializers.Serializer):
    """Risk score response (admin only)."""
    risk_score = serializers.IntegerField()
    risk_level = serializers.CharField()
    action_taken = serializers.CharField()
