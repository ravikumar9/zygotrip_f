from django.contrib import admin
from apps.core.location_models import Country, State, City, Locality, LocationSearchIndex, RegionGroup
from apps.core.models import PlatformSettings

# Import marketplace admin registrations
from .marketplace_admin import (
    DestinationAdmin,
    CategoryAdmin,
    OfferAdmin,
    SearchIndexAdmin
)


# Location hierarchy admin
@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'country', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('country', 'is_active')
    raw_id_fields = ('country',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'state', 'hotel_count', 'popularity_score', 'is_top_destination')
    search_fields = ('name', 'code', 'alternate_names')
    list_filter = ('state', 'is_top_destination', 'is_active')
    raw_id_fields = ('state',)
    list_editable = ('popularity_score', 'is_top_destination')


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'locality_type', 'hotel_count', 'popularity_score')
    search_fields = ('name', 'landmarks')
    list_filter = ('city', 'locality_type', 'is_active')
    raw_id_fields = ('city',)


@admin.register(RegionGroup)
class RegionGroupAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_popular', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_popular', 'is_active')


# ==========================================
# PHASE 5: PLATFORM SETTINGS ADMIN (NEW)
# ==========================================

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
	"""Admin interface for platform-wide commission and policy settings"""
	
	list_display = ('platform_name', 'default_property_commission', 'default_cab_commission', 'updated_at')
	readonly_fields = ('created_at', 'updated_at')
	
	fieldsets = (
		('Platform Identity', {
			'fields': ('platform_name', 'support_email'),
			'description': 'Platform name and support contact details'
		}),
		('Default Commission Percentages', {
			'fields': (
				'default_property_commission',
				'default_cab_commission',
				'default_bus_commission',
				'default_package_commission',
			),
			'description': 'Default commission percentages applied to new vendor listings. Can be overridden per property.'
		}),
		('Global Policies', {
			'fields': ('require_agreement_signature',),
			'description': 'Global platform policies affecting all vendors'
		}),
		('Audit', {
			'fields': ('created_at', 'updated_at'),
			'classes': ('collapse',)
		}),
	)
	
	def has_add_permission(self, request):
		"""Only allow one PlatformSettings instance (singleton pattern)"""
		return not PlatformSettings.objects.exists()
	
	def has_delete_permission(self, request, obj=None):
		"""Prevent deletion of PlatformSettings"""
		return False

# HolidayCalendar admin (System 2)
try:
    from apps.core.models import HolidayCalendar

    @admin.register(HolidayCalendar)
    class HolidayCalendarAdmin(admin.ModelAdmin):
        list_display = ['holiday_name', 'date', 'holiday_type', 'demand_multiplier', 'country', 'state', 'is_active']
        list_filter = ['holiday_type', 'country', 'state', 'is_active']
        search_fields = ['holiday_name', 'country', 'state']
        date_hierarchy = 'date'
        ordering = ['date']
except Exception:
    pass
