from django.contrib import admin
from .models import Wallet, WalletTransaction, OwnerWallet, OwnerWalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'locked_balance', 'currency', 'is_active']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'txn_type', 'amount', 'balance_after', 'reference', 'created_at']
    list_filter = ['txn_type', 'is_reversed']
    search_fields = ['reference', 'wallet__user__email']
    readonly_fields = ['uid', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(OwnerWallet)
class OwnerWalletAdmin(admin.ModelAdmin):
    list_display = ['owner', 'balance', 'pending_balance', 'total_earned', 'currency', 'is_verified']
    search_fields = ['owner__email']
    list_filter = ['is_verified']


@admin.register(OwnerWalletTransaction)
class OwnerWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['owner_wallet', 'txn_type', 'amount', 'balance_after', 'booking_reference', 'created_at']
    list_filter = ['txn_type']
    search_fields = ['booking_reference', 'owner_wallet__owner__email']
    ordering = ['-created_at']