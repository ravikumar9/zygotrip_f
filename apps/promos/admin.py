from django.contrib import admin
from .models import Promo, PromoUsage


admin.site.register(Promo)
admin.site.register(PromoUsage)

# Register your models here.

from .models import CashbackCampaign, CashbackCredit

@admin.register(CashbackCampaign)
class CashbackCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'cashback_type', 'cashback_value', 'min_booking_value', 'status', 'start_date', 'end_date']
    list_filter = ['status', 'cashback_type']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(CashbackCredit)
class CashbackCreditAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'campaign', 'booking', 'expires_at', 'is_expired']
    list_filter = ['is_expired']
    search_fields = ['user__email', 'booking__public_booking_id']