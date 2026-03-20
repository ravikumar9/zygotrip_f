from django.contrib import admin
from apps.core.location_models import Country, State, City, Locality, LocationSearchIndex, RegionGroup
from apps.core.models import PlatformSettings
from apps.core.feature_flags import FeatureFlag, feature_flags

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
	
	list_display = (
		'platform_name',
		'min_app_version_android',
		'min_app_version_ios',
		'hotels_enabled',
		'buses_enabled',
		'cabs_enabled',
		'packages_enabled',
		'bookings_enabled',
		'payments_enabled',
		'maintenance_mode',
		'updated_at',
	)
	list_editable = (
		'hotels_enabled',
		'buses_enabled',
		'cabs_enabled',
		'packages_enabled',
		'bookings_enabled',
		'payments_enabled',
		'maintenance_mode',
	)
	readonly_fields = ('created_at', 'updated_at')
	
	fieldsets = (
		('Platform Identity', {
			'fields': (
				'platform_name',
				'default_currency',
				'support_email',
				'support_phone',
				'system_notice',
				'maintenance_message',
			),
			'description': 'Platform name and support contact details'
		}),
		('App Version Gate', {
			'fields': ('min_app_version_android', 'min_app_version_ios'),
			'description': 'If set, clients below these app versions should force-update.'
		}),
		('Vertical Service Switches', {
			'fields': (
				'hotels_enabled',
				'buses_enabled',
				'cabs_enabled',
				'packages_enabled',
				'flights_enabled',
				'activities_enabled',
				'ai_assistant_enabled',
				'loyalty_enabled',
				'promos_enabled',
			),
			'description': 'Hard switches used by API guards. Changes are instant after cache invalidation.'
		}),
		('Operational Kill Switches', {
			'fields': ('maintenance_mode', 'bookings_enabled', 'payments_enabled', 'max_coupon_discount_percent'),
			'description': 'Global safety controls for traffic and monetisation.'
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
			'fields': ('service_fee_percent', 'require_agreement_signature'),
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


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
	list_display = (
		'name',
		'is_enabled',
		'rollout_percentage',
		'is_active',
		'expires_at',
		'updated_at',
	)
	list_editable = ('is_enabled', 'rollout_percentage', 'is_active')
	search_fields = ('name', 'description')
	list_filter = ('is_enabled', 'is_active')
	readonly_fields = ('created_at', 'updated_at')
	ordering = ('name',)

	fieldsets = (
		('Flag Basics', {'fields': ('name', 'description', 'is_enabled', 'is_active')}),
		('Rollout', {'fields': ('rollout_percentage', 'allowed_groups', 'allowed_users')}),
		('Advanced', {'fields': ('metadata', 'expires_at')}),
		('Audit', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
	)

	actions = ('enable_flags', 'disable_flags', 'invalidate_selected_cache', 'invalidate_all_cache')

	@admin.action(description='Enable selected flags')
	def enable_flags(self, request, queryset):
		updated = queryset.update(is_enabled=True)
		for flag_name in queryset.values_list('name', flat=True):
			feature_flags.invalidate_cache(flag_name)
		self.message_user(request, f'Enabled {updated} feature flags.')

	@admin.action(description='Disable selected flags')
	def disable_flags(self, request, queryset):
		updated = queryset.update(is_enabled=False)
		for flag_name in queryset.values_list('name', flat=True):
			feature_flags.invalidate_cache(flag_name)
		self.message_user(request, f'Disabled {updated} feature flags.')

	@admin.action(description='Invalidate cache for selected flags')
	def invalidate_selected_cache(self, request, queryset):
		for flag_name in queryset.values_list('name', flat=True):
			feature_flags.invalidate_cache(flag_name)
		self.message_user(request, 'Invalidated cache for selected flags.')

	@admin.action(description='Invalidate all feature flag cache')
	def invalidate_all_cache(self, request, queryset):
		feature_flags.invalidate_cache()
		self.message_user(request, 'Invalidated all feature flag cache entries.')

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
