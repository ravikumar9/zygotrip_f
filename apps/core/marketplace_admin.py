"""
Django admin registration for marketplace models.
"""
from django.contrib import admin
from .marketplace_models import Destination, Category, Offer, SearchIndex


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'state', 'is_trending', 'priority', 'search_count']
    list_filter = ['is_trending', 'country']
    search_fields = ['name', 'country', 'state']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_trending', 'priority']
    ordering = ['-priority', '-search_count']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'priority']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active', 'priority']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['title', 'offer_type', 'discount_value', 'code', 'is_active', 'valid_from', 'valid_until', 'priority']
    list_filter = ['offer_type', 'is_active', 'category']
    search_fields = ['title', 'code']
    date_hierarchy = 'valid_from'
    list_editable = ['is_active', 'priority']
    readonly_fields = ['code']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'subtitle', 'offer_type', 'discount_value')
        }),
        ('Conditions', {
            'fields': ('min_booking_amount', 'max_discount', 'category')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'is_active')
        }),
        ('Code & Display', {
            'fields': ('code', 'image', 'priority')
        }),
    )


@admin.register(SearchIndex)
class SearchIndexAdmin(admin.ModelAdmin):
    list_display = ['name', 'search_type', 'city', 'state', 'search_count', 'is_active']
    list_filter = ['search_type', 'is_active', 'city']
    search_fields = ['name', 'normalized_name', 'city']
    list_editable = ['is_active']
    ordering = ['-search_count', 'name']