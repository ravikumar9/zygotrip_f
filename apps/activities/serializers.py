"""Activity API serializers."""
from rest_framework import serializers
from .models import (
    ActivityCategory, Activity, ActivityImage, ActivityTimeSlot,
    ActivityBooking, ActivityBookingParticipant, ActivityPriceBreakdown,
    ActivityReview,
)


class ActivityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCategory
        fields = ['id', 'name', 'slug', 'icon', 'description']


class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['id', 'image', 'caption', 'is_primary']


class ActivityTimeSlotSerializer(serializers.ModelSerializer):
    available_spots = serializers.IntegerField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ActivityTimeSlot
        fields = ['id', 'date', 'start_time', 'end_time',
                  'max_capacity', 'booked_count', 'available_spots',
                  'effective_price']


class ActivityListSerializer(serializers.ModelSerializer):
    category = ActivityCategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'uuid', 'title', 'slug', 'category', 'city',
                  'short_description', 'duration_display', 'adult_price',
                  'child_price', 'avg_rating', 'review_count',
                  'is_instant_confirmation', 'is_free_cancellation',
                  'is_featured', 'primary_image']

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        return img.image.url if img else None


class ActivityDetailSerializer(serializers.ModelSerializer):
    category = ActivityCategorySerializer(read_only=True)
    images = ActivityImageSerializer(many=True, read_only=True)
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'uuid', 'title', 'slug', 'category', 'city',
                  'address', 'latitude', 'longitude', 'description',
                  'short_description', 'highlights', 'inclusions',
                  'exclusions', 'duration_display', 'duration_minutes',
                  'max_participants', 'min_participants', 'difficulty',
                  'min_age', 'languages', 'adult_price', 'child_price',
                  'group_discount_percent', 'min_group_size',
                  'avg_rating', 'review_count', 'is_instant_confirmation',
                  'is_free_cancellation', 'is_featured', 'images']


class ActivityParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityBookingParticipant
        fields = ['id', 'name', 'pax_type', 'age', 'phone']


class ActivityPriceBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityPriceBreakdown
        fields = ['adult_subtotal', 'child_subtotal', 'group_discount',
                  'service_fee', 'gst', 'promo_discount', 'total_amount']


class ActivityBookingSerializer(serializers.ModelSerializer):
    participants = ActivityParticipantSerializer(many=True, read_only=True)
    price_breakdown = ActivityPriceBreakdownSerializer(read_only=True)
    activity_title = serializers.CharField(source='activity.title', read_only=True)
    slot_date = serializers.DateField(source='time_slot.date', read_only=True)
    slot_time = serializers.TimeField(source='time_slot.start_time', read_only=True)

    class Meta:
        model = ActivityBooking
        fields = ['id', 'uuid', 'booking_ref', 'status',
                  'activity_title', 'slot_date', 'slot_time',
                  'adults', 'children', 'total_amount', 'discount_amount',
                  'final_amount', 'promo_code', 'contact_name',
                  'contact_email', 'contact_phone', 'special_requests',
                  'participants', 'price_breakdown', 'created_at']


class ActivityReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityReview
        fields = ['id', 'rating', 'title', 'comment', 'is_verified',
                  'user_name', 'created_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class ActivitySearchInputSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=100)
    date = serializers.DateField(required=False)
    category = serializers.CharField(max_length=120, required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    difficulty = serializers.ChoiceField(
        choices=['easy', 'moderate', 'challenging', 'extreme'],
        required=False)
    sort_by = serializers.ChoiceField(
        choices=['rating', 'price_low', 'price_high', 'popular'],
        default='rating')


class ActivityBookingInputSerializer(serializers.Serializer):
    activity_id = serializers.IntegerField()
    time_slot_id = serializers.IntegerField()
    adults = serializers.IntegerField(min_value=1, max_value=50, default=1)
    children = serializers.IntegerField(min_value=0, max_value=20, default=0)
    contact_name = serializers.CharField(max_length=150)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=15)
    special_requests = serializers.CharField(required=False, default='')
    promo_code = serializers.CharField(max_length=50, required=False, default='')
    participants = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=50)
