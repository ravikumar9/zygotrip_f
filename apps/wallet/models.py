"""
Closed-loop wallet system for ZygoTrip.
Phase 2: WalletTransaction with full type coverage.
Phase 3: OwnerWallet for property settlement payouts.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import TimeStampedModel


# S6: Import ledger models for migration discovery
from apps.wallet.ledger import Account, JournalEntry, LedgerEntry  # noqa: F401, E402


class Wallet(TimeStampedModel):
    """Customer wallet - real-time balance + locked balance for in-flight payments."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Available balance (spendable immediately)"
    )
    locked_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Funds held for in-flight bookings (not spendable)"
    )
    currency = models.CharField(max_length=10, default='INR')
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'wallet'

    def __str__(self):
        return f"Wallet({self.user}, Rs.{self.balance})"

    @property
    def total_balance(self):
        return self.balance + self.locked_balance

    def can_debit(self, amount):
        return self.balance >= amount

    def credit(self, amount, txn_type, reference='', note=''):
        """Add funds to wallet and record transaction."""
        self.balance += Decimal(str(amount))
        self.save(update_fields=['balance', 'updated_at'])
        return WalletTransaction.objects.create(
            wallet=self, txn_type=txn_type, amount=amount,
            balance_after=self.balance, reference=reference, note=note,
        )

    def debit(self, amount, txn_type, reference='', note=''):
        """Remove funds from wallet and record transaction."""
        amount = Decimal(str(amount))
        if not self.can_debit(amount):
            raise ValueError(f"Insufficient wallet balance: Rs.{self.balance} < Rs.{amount}")
        self.balance -= amount
        self.save(update_fields=['balance', 'updated_at'])
        return WalletTransaction.objects.create(
            wallet=self, txn_type=txn_type, amount=-amount,
            balance_after=self.balance, reference=reference, note=note,
        )

    def lock(self, amount, reference=''):
        """Move funds from available to locked (booking hold)."""
        amount = Decimal(str(amount))
        if not self.can_debit(amount):
            raise ValueError(f"Cannot lock Rs.{amount}: insufficient balance Rs.{self.balance}")
        self.balance -= amount
        self.locked_balance += amount
        self.save(update_fields=['balance', 'locked_balance', 'updated_at'])
        return WalletTransaction.objects.create(
            wallet=self, txn_type=WalletTransaction.TYPE_LOCK, amount=-amount,
            balance_after=self.balance, reference=reference,
            note=f"Locked for booking {reference}",
        )

    def unlock(self, amount, reference=''):
        """Release locked funds back to available (booking released/cancelled)."""
        amount = Decimal(str(amount))
        self.locked_balance -= amount
        self.balance += amount
        self.save(update_fields=['balance', 'locked_balance', 'updated_at'])
        return WalletTransaction.objects.create(
            wallet=self, txn_type=WalletTransaction.TYPE_UNLOCK, amount=amount,
            balance_after=self.balance, reference=reference,
            note=f"Released lock for {reference}",
        )


class WalletTransaction(TimeStampedModel):
    """
    Immutable audit trail for all wallet movements.
    Uses negative amounts for debits (double-entry convention).
    """

    TYPE_CREDIT = 'credit'
    TYPE_DEBIT = 'debit'
    TYPE_PAYMENT = 'payment'
    TYPE_REFUND = 'refund'
    TYPE_CASHBACK = 'cashback'
    TYPE_SETTLEMENT = 'settlement'
    TYPE_LOCK = 'lock'
    TYPE_UNLOCK = 'unlock'
    TYPE_PROMO = 'promo'

    TYPE_CHOICES = [
        (TYPE_CREDIT, 'Credit'),
        (TYPE_DEBIT, 'Debit'),
        (TYPE_PAYMENT, 'Booking Payment'),
        (TYPE_REFUND, 'Refund'),
        (TYPE_CASHBACK, 'Cashback'),
        (TYPE_SETTLEMENT, 'Settlement'),
        (TYPE_LOCK, 'Lock'),
        (TYPE_UNLOCK, 'Unlock'),
        (TYPE_PROMO, 'Promo Credit'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transactions')
    txn_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Positive=credit, Negative=debit"
    )
    balance_after = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Wallet balance snapshot after this transaction"
    )
    reference = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Booking ID, payment transaction ID, or promo code"
    )
    note = models.CharField(max_length=300, blank=True)
    is_reversed = models.BooleanField(default=False)

    class Meta:
        app_label = 'wallet'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'txn_type'], name='wtxn_wallet_type_idx'),
            models.Index(fields=['reference'], name='wtxn_reference_idx'),
        ]

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"WalletTxn({self.txn_type}, {sign}Rs.{self.amount})"


class OwnerWallet(TimeStampedModel):
    """
    Phase 3: Settlement wallet for property owners.
    Receives payouts ONLY after booking status == checked_out.
    """
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owner_wallet'
    )
    balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text="Total settled earnings available for withdrawal"
    )
    pending_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text="Earnings from confirmed bookings not yet checked out"
    )
    total_earned = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text="Lifetime total settled to this wallet"
    )
    currency = models.CharField(max_length=10, default='INR')
    bank_account_name = models.CharField(max_length=120, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_ifsc_code = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    upi_id = models.CharField(max_length=50, blank=True)
    is_verified = models.BooleanField(
        default=False,
        help_text="Bank/UPI details verified by admin before payout"
    )

    class Meta:
        app_label = 'wallet'

    def __str__(self):
        return f"OwnerWallet({self.owner}, Rs.{self.balance})"

    def credit_settlement(self, amount, booking_reference, note=''):
        """Credit funds after guest CHECKED_OUT - the only valid trigger."""
        amount = Decimal(str(amount))
        self.balance += amount
        self.total_earned += amount
        if self.pending_balance >= amount:
            self.pending_balance -= amount
        self.save(update_fields=['balance', 'total_earned', 'pending_balance', 'updated_at'])
        return OwnerWalletTransaction.objects.create(
            owner_wallet=self,
            txn_type=OwnerWalletTransaction.TYPE_SETTLEMENT,
            amount=amount,
            balance_after=self.balance,
            booking_reference=booking_reference,
            note=note or f"Settlement for booking {booking_reference}",
        )

    def mark_pending(self, amount, booking_reference):
        """Track expected earnings before checkout."""
        amount = Decimal(str(amount))
        self.pending_balance += amount
        self.save(update_fields=['pending_balance', 'updated_at'])
        return OwnerWalletTransaction.objects.create(
            owner_wallet=self,
            txn_type=OwnerWalletTransaction.TYPE_PENDING,
            amount=amount,
            balance_after=self.balance,
            booking_reference=booking_reference,
            note=f"Pending: booking {booking_reference} confirmed, awaiting checkout",
        )


class OwnerWalletTransaction(TimeStampedModel):
    """Immutable ledger for owner wallet movements."""

    TYPE_SETTLEMENT = 'settlement'
    TYPE_PENDING = 'pending'
    TYPE_REVERSAL = 'reversal'
    TYPE_WITHDRAWAL = 'withdrawal'
    TYPE_ADJUSTMENT = 'adjustment'

    TYPE_CHOICES = [
        (TYPE_SETTLEMENT, 'Settlement'),
        (TYPE_PENDING, 'Pending Settlement'),
        (TYPE_REVERSAL, 'Reversal'),
        (TYPE_WITHDRAWAL, 'Bank Withdrawal'),
        (TYPE_ADJUSTMENT, 'Manual Adjustment'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner_wallet = models.ForeignKey(
        OwnerWallet, on_delete=models.PROTECT, related_name='transactions'
    )
    txn_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    booking_reference = models.CharField(max_length=100, blank=True, db_index=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'wallet'
        ordering = ['-created_at']

    def __str__(self):
        return f"OwnerTxn({self.txn_type}, Rs.{self.amount}, {self.booking_reference})"


class CommissionRule(TimeStampedModel):
    """
    Phase 7: Per-property or global commission rules.
    Applied to compute platform cut from each booking.

    Priority: property-specific > property_type-specific > global default
    """
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='commission_rules',
        help_text="NULL = global rule for property_type or all",
    )
    property_type = models.CharField(
        max_length=80, blank=True,
        help_text="Apply to all properties of this type (e.g., Hotel, Homestay). Empty = global.",
    )
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text="Platform commission percentage",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'wallet'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['property', 'is_active']),
            models.Index(fields=['property_type', 'is_active']),
        ]

    def __str__(self):
        target = self.property.name if self.property else self.property_type or 'GLOBAL'
        return f"Commission {self.commission_percent}% for {target}"


class OwnerPayout(TimeStampedModel):
    """
    Phase 7: Tracks actual payouts from platform to owner bank/UPI.
    Created when admin triggers a payout from OwnerWallet.
    """
    STATUS_INITIATED = 'initiated'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner_wallet = models.ForeignKey(
        OwnerWallet, on_delete=models.PROTECT,
        related_name='payouts',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    payout_method = models.CharField(
        max_length=20,
        choices=[('bank', 'Bank Transfer'), ('upi', 'UPI')],
        default='bank',
    )
    bank_reference = models.CharField(max_length=100, blank=True)
    failure_reason = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='initiated_payouts',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'wallet'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner_wallet', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Payout {self.uid}: Rs.{self.amount} ({self.status})"