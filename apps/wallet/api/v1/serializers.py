"""Wallet API serializers for v1."""
from decimal import Decimal

from rest_framework import serializers
from apps.wallet.models import Wallet, WalletTransaction, OwnerWallet, OwnerWalletTransaction


class WalletSerializer(serializers.ModelSerializer):
    """Customer wallet balance response."""

    class Meta:
        model = Wallet
        fields = ['balance', 'locked_balance', 'currency', 'is_active', 'updated_at']
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['total_balance'] = str(instance.total_balance)
        return data


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Single wallet transaction (immutable audit record)."""

    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'uid', 'txn_type', 'amount', 'amount_display',
            'balance_after', 'reference', 'note',
            'is_reversed', 'created_at',
        ]
        read_only_fields = fields

    def get_amount_display(self, obj):
        sign = '+' if obj.amount >= 0 else ''
        return f'{sign}₹{abs(obj.amount):,.2f}'


class TopUpSerializer(serializers.Serializer):
    """Request to add money to wallet."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1.00'))
    note = serializers.CharField(max_length=200, default='Manual top-up', required=False)

    def validate_amount(self, value):
        if value > Decimal('100000'):
            raise serializers.ValidationError('Cannot top-up more than ₹1,00,000 in a single transaction.')
        return value


class OwnerWalletSerializer(serializers.ModelSerializer):
    """Owner (property) wallet balance."""

    class Meta:
        model = OwnerWallet
        fields = [
            'balance', 'pending_balance', 'total_earned',
            'currency', 'is_verified',
            'bank_name', 'upi_id',
            'updated_at',
        ]
        read_only_fields = fields


class OwnerTransactionSerializer(serializers.ModelSerializer):
    """Owner wallet transaction record."""

    class Meta:
        model = OwnerWalletTransaction
        fields = [
            'uid', 'txn_type', 'amount', 'balance_after',
            'booking_reference', 'note', 'created_at',
        ]
        read_only_fields = fields
