from django.contrib import admin

from .models import Referral, ReferralProfile


@admin.register(ReferralProfile)
class ReferralProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'referral_code',
        'total_referrals',
        'successful_referrals',
        'total_wallet_credits',
        'total_loyalty_points',
        'updated_at',
    )
    search_fields = ('user__email', 'referral_code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        'referrer',
        'referee',
        'referral_code',
        'status',
        'referee_wallet_credit',
        'referrer_loyalty_points',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('referrer__email', 'referee__email', 'referral_code')
    readonly_fields = ('created_at', 'updated_at')
