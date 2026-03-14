"""Activities admin configuration."""
from django.contrib import admin
from .models import (
    ActivityCategory, Activity, ActivityImage, ActivityTimeSlot,
    ActivityBooking, ActivityBookingParticipant, ActivityPriceBreakdown,
    ActivityReview, ActivityCancellationPolicy,
)


class ActivityImageInline(admin.TabularInline):
    model = ActivityImage
    extra = 0


class ActivityTimeSlotInline(admin.TabularInline):
    model = ActivityTimeSlot
    extra = 0


class ActivityCancellationPolicyInline(admin.TabularInline):
    model = ActivityCancellationPolicy
    extra = 0


class ActivityParticipantInline(admin.TabularInline):
    model = ActivityBookingParticipant
    extra = 0


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['title', 'city', 'category', 'adult_price',
                    'avg_rating', 'review_count', 'is_featured', 'is_active']
    list_filter = ['city', 'category', 'difficulty', 'is_featured', 'is_active']
    search_fields = ['title', 'city', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ActivityImageInline, ActivityTimeSlotInline,
               ActivityCancellationPolicyInline]
    raw_id_fields = ['supplier', 'category']


@admin.register(ActivityBooking)
class ActivityBookingAdmin(admin.ModelAdmin):
    list_display = ['booking_ref', 'user', 'activity', 'status',
                    'final_amount', 'created_at']
    list_filter = ['status']
    search_fields = ['booking_ref', 'contact_email', 'user__email']
    readonly_fields = ['uuid', 'booking_ref']
    inlines = [ActivityParticipantInline]
    raw_id_fields = ['user', 'activity', 'time_slot']


@admin.register(ActivityReview)
class ActivityReviewAdmin(admin.ModelAdmin):
    list_display = ['activity', 'user', 'rating', 'is_verified', 'created_at']
    list_filter = ['rating', 'is_verified']
