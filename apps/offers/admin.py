from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.offers.models import Offer, PropertyOffer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['title', 'coupon_code', 'offer_type_display', 'is_active_badge', 'start_datetime', 'end_datetime', 'status_indicator']
    list_filter = ['is_active', 'is_global', 'offer_type', 'start_datetime']
    search_fields = ['title', 'coupon_code', 'description']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    filter_horizontal = []
    
    fieldsets = (
        ("Offer Details", {
            'fields': ('title', 'description', 'coupon_code', 'offer_type')
        }),
        ("Discount Configuration", {
            'fields': ('discount_percentage', 'discount_flat')
        }),
        ("Scheduling", {
            'fields': ('start_datetime', 'end_datetime')
        }),
        ("Status & Scope", {
            'fields': ('is_active', 'is_global')
        }),
        ("Metadata", {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def offer_type_display(self, obj):
        """Display offer type with styling"""
        colors = {
            'percentage': '#3498db',  # blue
            'flat': '#2ecc71',        # green
            'bogo': '#f39c12',        # orange
            'bundle': '#9b59b6',      # purple
        }
        color = colors.get(obj.offer_type, '#333')
        return format_html(
            '<span style="background: {color}; color: white; padding: 3px 8px; border-radius: 3px;">{type}</span>',
            color=color,
            type=obj.get_offer_type_display()
        )
    offer_type_display.short_description = "Type"
    
    def is_active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"
    
    def status_indicator(self, obj):
        """Show if offer is currently valid (is_active AND within date range)"""
        if obj.is_currently_active():
            return format_html('<span style="color: green;">🟢 LIVE</span>')
        elif obj.is_active:
            now = timezone.now()
            if obj.start_datetime > now:
                return format_html('<span style="color: blue;">🔵 SCHEDULED</span>')
            else:
                return format_html('<span style="color: orange;">🟠 EXPIRED</span>')
        else:
            return format_html('<span style="color: gray;">⚪ DISABLED</span>')
    status_indicator.short_description = "Current Status"
    
    def save_model(self, request, obj, form, change):
        """Set created_by when creating new offer"""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PropertyOffer)
class PropertyOfferAdmin(admin.ModelAdmin):
    list_display = ['offer', 'property', 'created_at']
    list_filter = ['offer__is_active', 'created_at', 'offer__offer_type']
    search_fields = ['offer__title', 'property__name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ("Offer & Property", {
            'fields': ('offer', 'property')
        }),
        ("Metadata", {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
