from django.contrib import admin
from django.utils import timezone

from .models import Promo, PromoUsage, CashbackCampaign, CashbackCredit


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'discount_type',
        'value',
        'applicable_module',
        'is_active',
        'starts_at',
        'ends_at',
    )
    list_filter = ('discount_type', 'applicable_module', 'is_active')
    search_fields = ('code',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ('activate_promos', 'deactivate_promos')

    @admin.action(description='Activate selected promos')
    def activate_promos(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'Activated {count} promos.')

    @admin.action(description='Deactivate selected promos')
    def deactivate_promos(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {count} promos.')


@admin.register(PromoUsage)
class PromoUsageAdmin(admin.ModelAdmin):
    list_display = ('promo', 'user', 'booking', 'created_at')
    search_fields = ('promo__code', 'user__email', 'booking__public_booking_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CashbackCampaign)
class CashbackCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'status',
        'cashback_type',
        'cashback_value',
        'min_booking_value',
        'start_date',
        'end_date',
    )
    list_filter = ('status', 'cashback_type')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('applicable_properties',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ('mark_active', 'mark_paused', 'mark_expired')

    @admin.action(description='Mark selected campaigns active')
    def mark_active(self, request, queryset):
        updated = queryset.update(status=CashbackCampaign.STATUS_ACTIVE)
        self.message_user(request, f'Marked {updated} campaigns active.')

    @admin.action(description='Mark selected campaigns paused')
    def mark_paused(self, request, queryset):
        updated = queryset.update(status=CashbackCampaign.STATUS_PAUSED)
        self.message_user(request, f'Marked {updated} campaigns paused.')

    @admin.action(description='Mark selected campaigns expired')
    def mark_expired(self, request, queryset):
        today = timezone.now().date()
        updated = queryset.update(status=CashbackCampaign.STATUS_EXPIRED, end_date=today)
        self.message_user(request, f'Marked {updated} campaigns expired.')


@admin.register(CashbackCredit)
class CashbackCreditAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'campaign', 'booking', 'expires_at', 'is_expired')
    list_filter = ('is_expired',)
    search_fields = ('user__email', 'booking__public_booking_id', 'wallet_txn_reference')
    readonly_fields = ('created_at', 'updated_at')