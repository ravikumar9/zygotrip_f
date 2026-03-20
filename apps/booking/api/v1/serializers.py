"""
Booking API serializers for v1.

OTA-grade validation: every field that affects pricing or inventory
is validated server-side. Frontend must NEVER be trusted for prices.
"""
from datetime import date, timedelta
from decimal import Decimal
import re
from rest_framework import serializers
from apps.booking.models import Booking, BookingContext, BookingPriceBreakdown, BookingRoom, BookingGuest

# Booking limits
MAX_ROOMS_PER_BOOKING = 10
MAX_NIGHTS_PER_BOOKING = 90
MAX_ADULTS_PER_ROOM = 4
MAX_CHILDREN_PER_ROOM = 3
MAX_ADVANCE_DAYS = 365  # Can book up to 1 year ahead


class BookingContextCreateSerializer(serializers.Serializer):
    """
    Input for creating a BookingContext (price-locked session).

    OTA-grade validation:
      - checkin must be today or later
      - checkout must be after checkin
      - max 90 nights, max 10 rooms
      - room_type_id must belong to property_id (validated in view)
      - meal_plan validated against allowed codes
    """

    property_id = serializers.IntegerField()
    room_type_id = serializers.IntegerField(required=False, allow_null=True)
    checkin = serializers.DateField()
    checkout = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, max_value=MAX_ADULTS_PER_ROOM * MAX_ROOMS_PER_BOOKING, default=1)
    children = serializers.IntegerField(min_value=0, max_value=MAX_CHILDREN_PER_ROOM * MAX_ROOMS_PER_BOOKING, default=0)
    rooms = serializers.IntegerField(min_value=1, max_value=MAX_ROOMS_PER_BOOKING, default=1)
    meal_plan = serializers.CharField(max_length=50, default='', required=False)
    promo_code = serializers.CharField(max_length=30, default='', required=False)

    # Allowed meal plan codes (empty = room only)
    _VALID_MEAL_PLANS = {
        '', 'R', 'R+B', 'R+B+L/D', 'R+A',
        'room_only', 'breakfast', 'room_breakfast',
        'half_board', 'halfboard', 'full_board', 'fullboard',
        'all_inclusive', 'all_meals', 'none',
    }

    def validate_meal_plan(self, value):
        if value and value.strip().lower() not in {v.lower() for v in self._VALID_MEAL_PLANS}:
            raise serializers.ValidationError(
                f'Invalid meal plan code "{value}". '
                f'Allowed: {", ".join(sorted(c for c in self._VALID_MEAL_PLANS if c))}.'
            )
        return value.strip()

    def validate(self, data):
        checkin = data['checkin']
        checkout = data['checkout']
        today = date.today()

        if checkin < today:
            raise serializers.ValidationError({'checkin': 'Check-in date cannot be in the past.'})

        if checkin >= checkout:
            raise serializers.ValidationError({'checkout': 'Checkout must be after check-in.'})

        nights = (checkout - checkin).days
        if nights > MAX_NIGHTS_PER_BOOKING:
            raise serializers.ValidationError(
                {'checkout': f'Maximum stay is {MAX_NIGHTS_PER_BOOKING} nights.'}
            )

        if checkin > today + timedelta(days=MAX_ADVANCE_DAYS):
            raise serializers.ValidationError(
                {'checkin': f'Cannot book more than {MAX_ADVANCE_DAYS} days in advance.'}
            )

        rooms = data.get('rooms', 1)
        adults = data.get('adults', 1)
        if adults < rooms:
            raise serializers.ValidationError(
                {'adults': 'At least 1 adult per room is required.'}
            )

        return data


class BookingContextSerializer(serializers.ModelSerializer):
    """
    Full BookingContext response.

    Phase 5 additions:
      gst_amount       — alias for `tax` (explicit GST amount)
      gst_percentage   — computed GST rate (5% or 18%) per Indian slab
      total_price      — alias for `final_price` (canonical booking total)
    """

    property_id = serializers.IntegerField(source='property.id', read_only=True)
    property_name = serializers.CharField(source='property.name', read_only=True)
    property_slug = serializers.CharField(source='property.slug', read_only=True)
    room_type_id = serializers.IntegerField(source='room_type.id', read_only=True)
    room_type_name = serializers.CharField(source='room_type.name', read_only=True, default='')
    nights = serializers.SerializerMethodField()

    # Phase 5: GST fields
    gst_amount = serializers.DecimalField(source='tax', max_digits=12, decimal_places=2, read_only=True)
    gst_percentage = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(source='final_price', max_digits=12, decimal_places=2, read_only=True)
    payment_split = serializers.SerializerMethodField()

    class Meta:
        model = BookingContext
        fields = [
            'id', 'uuid', 'property_id', 'property_name', 'property_slug',
            'room_type_id',
            'room_type_name', 'checkin', 'checkout', 'nights',
            'adults', 'children', 'rooms', 'meal_plan',
            'base_price', 'meal_amount', 'property_discount', 'platform_discount',
            'promo_discount', 'tax', 'service_fee', 'final_price',
            # Price lock fields
            'price_locked', 'locked_price', 'price_expires_at',
            'rate_plan_id', 'supplier_id',
            # Phase 5 additions
            'gst_amount', 'gst_percentage', 'total_price',
            'payment_split',
            'promo_code', 'context_status', 'expires_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_nights(self, obj):
        return (obj.checkout - obj.checkin).days

    def get_gst_percentage(self, obj):
        """
        Derive GST slab from the per-night room tariff.
        Indian GST for accommodation:
          ≤ ₹7500/night → 5%
          > ₹7500/night → 18%
        """
        try:
            nights = max(1, (obj.checkout - obj.checkin).days)
            rooms = max(1, obj.rooms or 1)
            if obj.base_price and nights > 0 and rooms > 0:
                # base_price = tariff_per_night * nights * rooms
                tariff_per_night = Decimal(str(obj.base_price)) / Decimal(str(nights * rooms))
                return '5' if tariff_per_night <= Decimal('7500') else '18'
        except Exception:
            pass
        return '18'  # safe default

    def get_payment_split(self, obj):
        return None


class BookingCreateSerializer(serializers.Serializer):
    """
    Create a Booking from a confirmed BookingContext.

    OTA-grade validation:
      - context_uuid or context_id required
      - guest name must be 2+ characters (no single initials)
      - guest phone validated for Indian/intl format
      - payment_method must be a supported gateway
    """

    # UUID-based lookup (preferred) — all new clients must use this
    context_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)
    # Legacy integer ID (kept for backward compat)
    context_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    guest_name = serializers.CharField(max_length=120, min_length=2, required=False, allow_blank=True)
    guest_email = serializers.EmailField(required=False)
    guest_phone = serializers.RegexField(
        regex=r'^\+?[1-9]\d{6,14}$',
        max_length=20,
        required=False,
        error_messages={'invalid': 'Enter a valid phone number (7-15 digits, optional + prefix).'},
    )
    guest_age = serializers.IntegerField(min_value=0, max_value=150, required=False, default=0)
    guests = serializers.ListField(child=serializers.DictField(), required=False, allow_empty=False)
    # Phase 5: payment method and idempotency support
    payment_method = serializers.ChoiceField(
        choices=['wallet', 'gateway', 'split', 'cod', 'pay_at_hotel'],
        default='wallet',
        required=False,
    )
    payment_split = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('context_uuid') and not data.get('context_id'):
            raise serializers.ValidationError(
                'Either context_uuid or context_id must be provided.'
            )

        # Backward compatibility: accept guests[0] payload used by Flutter/web.
        if (not data.get('guest_name') or not data.get('guest_email') or not data.get('guest_phone')) and data.get('guests'):
            first_guest = data['guests'][0] if data['guests'] else {}
            data['guest_name'] = (first_guest.get('name') or first_guest.get('full_name') or '').strip()
            data['guest_email'] = (first_guest.get('email') or '').strip()
            data['guest_phone'] = (first_guest.get('phone') or '').strip()

        if not data.get('guest_name'):
            raise serializers.ValidationError({'guest_name': 'This field is required.'})
        if not data.get('guest_email'):
            raise serializers.ValidationError({'guest_email': 'This field is required.'})
        if not data.get('guest_phone'):
            raise serializers.ValidationError({'guest_phone': 'This field is required.'})
        if not re.match(r'^\+?[1-9]\d{6,14}$', str(data['guest_phone'])):
            raise serializers.ValidationError({'guest_phone': 'Enter a valid phone number (7-15 digits, optional + prefix).'})

        return data


class BookingRoomSerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)
    room_type_id = serializers.IntegerField(source='room_type.id', read_only=True)

    class Meta:
        model = BookingRoom
        fields = ['room_type_id', 'room_type_name', 'quantity']


class BookingPriceBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingPriceBreakdown
        fields = [
            'base_amount', 'meal_amount', 'service_fee',
            'gst', 'promo_discount', 'total_amount',
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    """Full booking detail returned to the client."""

    property_name = serializers.CharField(source='property.name', read_only=True)
    property_slug = serializers.CharField(source='property.slug', read_only=True)
    rooms = BookingRoomSerializer(many=True, read_only=True)
    price_breakdown = BookingPriceBreakdownSerializer(read_only=True)
    nights = serializers.SerializerMethodField()
    hold_minutes_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'uuid', 'public_booking_id',
            'property_name', 'property_slug',
            'check_in', 'check_out', 'nights',
            'status', 'settlement_status', 'is_guest_booking',
            'total_amount', 'gross_amount', 'gst_amount',
            'refund_amount',
            'guest_name', 'guest_email', 'guest_phone',
            'rooms', 'price_breakdown',
            'hold_expires_at', 'hold_minutes_remaining',
            'created_at',
        ]
        read_only_fields = fields

    def get_nights(self, obj):
        return (obj.check_out - obj.check_in).days

    def get_hold_minutes_remaining(self, obj):
        if obj.status != Booking.STATUS_HOLD or not obj.hold_expires_at:
            return None
        from django.utils import timezone
        remaining = (obj.hold_expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining // 60))


class BookingListSerializer(serializers.ModelSerializer):
    """Compact booking summary for list views."""

    property_name = serializers.CharField(source='property.name', read_only=True)
    property_slug = serializers.CharField(source='property.slug', read_only=True)
    nights = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'uuid', 'public_booking_id',
            'property_name', 'property_slug',
            'check_in', 'check_out', 'nights',
            'status', 'total_amount',
            'created_at',
        ]
        read_only_fields = fields

    def get_nights(self, obj):
        return (obj.check_out - obj.check_in).days
