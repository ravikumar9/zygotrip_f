# apps/hotels/admin.py
"""
Django admin configuration for hotels app with filter management.

ADMIN FEATURES:
- Filter configuration (brands, payment types, cancellation policies, amenities, etc.)
- Property management with inline filter assignment
- Filter performance monitoring
- Bulk actions for filter management
"""

from django.contrib import admin, messages
from django.utils.html import format_html
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import (
    Property, PropertyImage, RatingAggregate, 
    Category, PropertyCategory, PropertyPolicy, PropertyAmenity
    # Note: PropertyOffer moved to apps.offers
    # Note: Remaining models commented out - need to be defined in models.py
    # PaymentMethodType, PropertyPaymentSupport,
    # CancellationPolicyOption, PropertyCancellationPolicy,
    # StarRatingOption, PropertyStarRating,
    # PriceRangeFilter, AmenityFilter, PropertyAmenityFilter,
    # DistanceRangeFilter
)


# ============================================================================
# FILTER CONFIGURATION ADMINS (DISABLED - MODELS NOT YET PRESENT)
# ============================================================================

# Note: Re-enable these when models are defined

# class PropertyBrandInline(admin.TabularInline):
#     """Inline editing of property brands"""
#     model = PropertyBrandRelation
#     extra = 1

# @admin.register(PropertyBrand)
# class PropertyBrandAdmin(admin.ModelAdmin):
#     """Admin for property brands"""
#     pass

# @admin.register(PaymentMethodType)
# class PaymentMethodTypeAdmin(admin.ModelAdmin):
#     """Admin for payment method types"""
#     pass

# @admin.register(CancellationPolicyOption)
# class CancellationPolicyOptionAdmin(admin.ModelAdmin):
#     """Admin for cancellation policy templates"""
#     pass

# @admin.register(StarRatingOption)
# class StarRatingOptionAdmin(admin.ModelAdmin):
#     """Admin for star rating categories"""
#     pass


# @admin.register(PriceRangeFilter)
# class PriceRangeFilterAdmin(admin.ModelAdmin):
#     """Admin for price range filter buckets"""
#     list_display = ('label', 'price_range', 'is_active')
#     list_filter = ('is_active', 'min_price')
#     list_editable = ('is_active',)
#     search_fields = ('label',)
#     
#     def price_range(self, obj):
#         return f"₹{obj.min_price} - ₹{obj.max_price}"
    # price_range.short_description = 'Price Range'


# @admin.register(AmenityFilter)
# class AmenityFilterAdmin(admin.ModelAdmin):
#     """Admin for filterable amenities"""
#     list_display = ('name', 'category', 'icon', 'property_count', 'is_active')
#     list_filter = ('is_active', 'category')
#     list_editable = ('is_active',)
#     search_fields = ('name', 'slug')
#     prepopulated_fields = {'slug': ('name',)}
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('name', 'slug', 'icon', 'category', 'description')
#         }),
#         ('Status', {
#             'fields': ('is_active',)
#         }),
#     )
#     
#     def property_count(self, obj):
#         count = obj.properties.count()
#         return format_html(
#             '<span style="background-color: var(--primary); color: var(--bg-card); padding: 3px 10px; border-radius: 3px;">{}</span>',
#             count
#         )
#     property_count.short_description = 'Properties Using'


# @admin.register(DistanceRangeFilter)
# class DistanceRangeFilterAdmin(admin.ModelAdmin):
#     """Admin for distance range filters"""
#     list_display = ('label', 'max_distance_km', 'is_active')
#     list_filter = ('is_active', 'max_distance_km')
#     list_editable = ('is_active',)
#     search_fields = ('label',)


# ============================================================================
# PROPERTY ADMINS WITH FILTER MANAGEMENT
# ============================================================================

# COMMENTED OUT: PropertyPaymentSupport model not defined
# class PropertyPaymentSupportInline(admin.TabularInline):
#     """Inline payment method management"""
#     model = PropertyPaymentSupport
#     extra = 1
#     fields = ('method', 'is_enabled')


# COMMENTED OUT: PropertyCancellationPolicy model not defined
# class PropertyCancellationPolicyInline(admin.TabularInline):
#     """Inline cancellation policy management"""
#     model = PropertyCancellationPolicy
#     extra = 1
#     fields = ('policy', 'is_primary')


# COMMENTED OUT: PropertyAmenityFilter model not defined
# class PropertyAmenityFilterInline(admin.TabularInline):
#     """Inline filterable amenity management"""
#     model = PropertyAmenityFilter
#     extra = 1
#     fields = ('amenity',)


class PropertyImageInline(admin.TabularInline):
    """Inline image management"""
    model = PropertyImage
    extra = 1
    fields = ('image_url', 'is_featured', 'display_order')


# PropertyOffer moved to apps.offers - see apps/offers/admin.py
# class PropertyOfferInline(admin.TabularInline):
#     """Inline offer management"""
#     model = PropertyOffer
#     extra = 0
#     fields = ('title', 'discount_percentage', 'valid_from', 'valid_until', 'is_active')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    """Main property admin with comprehensive filter configuration and commission control"""
    
    list_display = (
        'name', 'owner', 'status_badge', 'city', 'rating', 'commission_display',
        'agreement_badge', 'is_active'
    )
    list_filter = (
        'is_active', 'status', 'city', 'rating', 'has_free_cancellation',
        'agreement_signed', 'is_trending', 'created_at'
    )
    list_editable = ('is_active',)
    search_fields = ('name', 'city', 'owner__email', 'owner__full_name')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('owner', 'name', 'slug', 'property_type', 'description')
        }),
        ('Location', {
            'fields': ('city', 'locality', 'area', 'landmark', 'country', 'address', 'latitude', 'longitude')
        }),
        ('Classification', {
            'fields': ('star_rating',),
            'description': 'Star rating category for filter grouping'
        }),
        ('Guest Intelligence', {
            'fields': ('rating', 'review_count', 'popularity_score', 'bookings_today', 'bookings_this_week', 'is_trending')
        }),
        ('Policies', {
            'fields': ('has_free_cancellation', 'cancellation_hours')
        }),
        # ==========================================
        # PHASE 5 & 6: COMMISSION & AGREEMENT FIELDS (NEW)
        # ==========================================
        ('Vendor Management', {
            'fields': ('status', 'commission_percentage', 'agreement_file', 'agreement_signed'),
            'description': 'Approval workflow, commission settings, and agreement management'
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [
        PropertyImageInline,
        # PropertyPaymentSupportInline,  # COMMENTED OUT: PropertyPaymentSupport not defined
        # PropertyCancellationPolicyInline,  # COMMENTED OUT: PropertyCancellationPolicy not defined
        # PropertyAmenityFilterInline,  # COMMENTED OUT: PropertyAmenityFilter not defined
        # PropertyBrandInline,  # COMMENTED OUT: PropertyBrandRelation not defined
        # PropertyOfferInline,  # MOVED: PropertyOffer now in apps.offers
    ]
    
    readonly_fields = ('created_at', 'updated_at', 'slug')
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': '#FF9800',
            'approved': '#4CAF50',
            'rejected': '#F44336',
            'suspended': '#9C27B0',
        }
        color = colors.get(obj.status, '#757575')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def commission_display(self, obj):
        """Display commission percentage"""
        return format_html('{}%', obj.commission_percentage)
    commission_display.short_description = 'Commission'
    
    def agreement_badge(self, obj):
        """Display agreement status"""
        if obj.agreement_signed:
            return format_html('<span style="color: green;">✓ Signed</span>')
        elif obj.agreement_file:
            return format_html('<span style="color: orange;">⚠ Pending Signature</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Generated</span>')
    agreement_badge.short_description = 'Agreement'
    
    def free_cancellation_badge(self, obj):
        color = 'var(--success)' if obj.has_free_cancellation else 'var(--danger)'
        text = 'Free Cancel' if obj.has_free_cancellation else 'Paid Cancel'
        return format_html(
            '<span style="background-color: {}; color: var(--bg-card); padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, text
        )
    free_cancellation_badge.short_description = 'Cancellation'
    
    def is_trending_badge(self, obj):
        color = 'var(--warning)' if obj.is_trending else 'var(--secondary)'
        icon = '🔥' if obj.is_trending else '-'
        return format_html(
            '<span style="background-color: {}; color: var(--bg-card); padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, icon
        )
    is_trending_badge.short_description = 'Trending'
    
    actions = [
        'mark_free_cancellation',
        'mark_paid_cancellation',
        'mark_not_trending',
        'mark_trending',
        'approve_properties',
        'reject_properties',
        'generate_agreements',
        'suspend_properties',
    ]
    
    def mark_free_cancellation(self, request, queryset):
        count = queryset.update(has_free_cancellation=True)
        messages.success(request, f'{count} properties marked with free cancellation')
    mark_free_cancellation.short_description = 'Mark free cancellation'
    
    def mark_paid_cancellation(self, request, queryset):
        count = queryset.update(has_free_cancellation=False)
        messages.success(request, f'{count} properties marked with paid cancellation')
    mark_paid_cancellation.short_description = 'Mark paid cancellation'
    
    def mark_trending(self, request, queryset):
        count = queryset.update(is_trending=True)
        messages.success(request, f'{count} properties marked as trending')
    mark_trending.short_description = 'Mark as trending'
    
    def mark_not_trending(self, request, queryset):
        count = queryset.update(is_trending=False)
        messages.success(request, f'{count} properties unmarked as trending')
    mark_not_trending.short_description = 'Unmark as trending'
    
    # ==========================================
    # PHASE 5 & 6: ADMIN APPROVAL & AGREEMENT ACTIONS (NEW)
    # ==========================================
    
    def approve_properties(self, request, queryset):
        """Approve properties and generate agreements"""
        from .services import save_property_agreement
        
        count = 0
        for property_obj in queryset.filter(status='pending'):
            property_obj.status = 'approved'
            property_obj.save()
            
            # Auto-generate agreement
            save_property_agreement(property_obj)
            count += 1
        
        messages.success(request, f'{count} properties approved and agreements generated')
    approve_properties.short_description = 'Approve properties (generates agreements)'
    
    def reject_properties(self, request, queryset):
        """Reject properties"""
        count = queryset.filter(status='pending').update(status='rejected')
        messages.success(request, f'{count} properties rejected')
    reject_properties.short_description = 'Reject properties'
    
    def suspend_properties(self, request, queryset):
        """Suspend properties from listing"""
        count = queryset.update(status='suspended')
        messages.success(request, f'{count} properties suspended')
    suspend_properties.short_description = 'Suspend properties'
    
    def generate_agreements(self, request, queryset):
        """Manually generate/regenerate agreements"""
        from .services import save_property_agreement
        
        count = 0
        for property_obj in queryset:
            if save_property_agreement(property_obj):
                count += 1
        
        messages.success(request, f'Agreements generated for {count} properties')
    generate_agreements.short_description = 'Generate/Regenerate agreements'


# ============================================================================
# SUPPORT ADMINS
# ============================================================================

@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    """Admin for property images"""
    list_display = ('property', 'is_featured', 'display_order', 'created_at')
    list_filter = ('is_featured', 'property', 'created_at')
    list_editable = ('is_featured', 'display_order')
    search_fields = ('property__name',)


@admin.register(PropertyPolicy)
class PropertyPolicyAdmin(admin.ModelAdmin):
    """Admin for property policies"""
    list_display = ('property', 'title')
    list_filter = ('property', 'created_at')
    search_fields = ('property__name', 'title')


@admin.register(PropertyAmenity)
class PropertyAmenityAdmin(admin.ModelAdmin):
    """Admin for property amenities"""
    list_display = ('property', 'name', 'icon')
    list_filter = ('property', 'created_at')
    search_fields = ('property__name', 'name')


@admin.register(RatingAggregate)
class RatingAggregateAdmin(admin.ModelAdmin):
    """Admin for rating breakdowns"""
    list_display = (
        'property', 'overall_rating', 'cleanliness', 'service',
        'location', 'amenities', 'value_for_money', 'total_reviews'
    )
    list_filter = ('property__city', 'created_at')
    search_fields = ('property__name',)
    
    fieldsets = (
        ('Property', {
            'fields': ('property',)
        }),
        ('Rating Breakdown', {
            'fields': (
                'cleanliness', 'service', 'location',
                'amenities', 'value_for_money'
            ),
            'description': 'Individual category ratings (0-5 scale)'
        }),
        ('Stats', {
            'fields': ('total_reviews',)
        }),
    )
    
    def overall_rating(self, obj):
        avg = (
            obj.cleanliness + obj.service + obj.location +
            obj.amenities + obj.value_for_money
        ) / 5
        return f"⭐ {avg:.1f}"
    overall_rating.short_description = 'Overall'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for property categories"""
    list_display = ('name', 'slug', 'icon', 'property_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')
    
    def property_count(self, obj):
        count = obj.propertycategory_set.count()
        return format_html(
            '<span style="background-color: var(--primary); color: var(--bg-card); padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    property_count.short_description = 'Properties'


# PropertyOffer admin moved to apps.offers.admin
# @admin.register(PropertyOffer)
# class PropertyOfferAdmin(admin.ModelAdmin):
#     """Admin for promotional offers"""
#     list_display = (
#         'property', 'title', 'discount_display', 'valid_from',
#         'valid_until', 'is_active', 'code'
#     )
#     list_filter = ('is_active', 'valid_from', 'valid_until', 'property__city')
#     list_editable = ('is_active',)
#     search_fields = ('property__name', 'title', 'code')
#     
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('property', 'title', 'description', 'code')
#         }),
#         ('Discount', {
#             'fields': ('discount_percentage', 'discount_amount'),
#             'description': 'Either percentage or amount (one or both)'
#         }),
#         ('Validity', {
#             'fields': ('valid_from', 'valid_until', 'is_active')
#         }),
#     )
#     
#     def discount_display(self, obj):
#         if obj.discount_percentage:
#             return f"{obj.discount_percentage}%"
#         elif obj.discount_amount:
#             return f"₹{obj.discount_amount}"
#         return "-"
#     discount_display.short_description = 'Discount'