"""
Payment Models — Production OTA Payment System.
Supports Wallet, Cashfree, Stripe, and Paytm UPI gateways.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """
    Legacy-compatible Payment record.
    Created by webhook handler on successful payment confirmation.
    """
    booking = models.ForeignKey(
        'booking.Booking', on_delete=models.PROTECT,
        null=True, blank=True, related_name='payments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ])

    class Meta:
        app_label = 'payments'

    def __str__(self):
        return f"Payment {self.id} — ₹{self.amount} ({self.status})"


class PaymentTransaction(TimeStampedModel):
    """
    Authoritative payment transaction record across all gateways.
    One PaymentTransaction per payment attempt (idempotent on idempotency_key).
    """
    GATEWAY_WALLET = 'wallet'
    GATEWAY_CASHFREE = 'cashfree'
    GATEWAY_STRIPE = 'stripe'
    GATEWAY_PAYTM = 'paytm_upi'

    GATEWAY_CHOICES = [
        (GATEWAY_WALLET, 'ZygoTrip Wallet'),
        (GATEWAY_CASHFREE, 'Cashfree'),
        (GATEWAY_STRIPE, 'Stripe'),
        (GATEWAY_PAYTM, 'Paytm UPI'),
    ]

    STATUS_INITIATED = 'initiated'
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    # Internal transaction ID (our reference)
    transaction_id = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text='Our internal transaction reference',
    )
    # Idempotency key — prevents duplicate payment attempts
    idempotency_key = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True,
        help_text='Client-generated idempotency key',
    )
    # Gateway's own transaction/order ID
    gateway_transaction_id = models.CharField(
        max_length=200, blank=True, db_index=True,
        help_text="Gateway's transaction/order ID",
    )

    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='payment_transactions',
    )
    booking = models.ForeignKey(
        'booking.Booking', on_delete=models.PROTECT,
        related_name='payment_transactions', null=True, blank=True,
    )
    booking_reference = models.CharField(
        max_length=100, db_index=True,
        help_text='Booking UUID string',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED,
    )

    # Gateway interaction data
    gateway_response = models.JSONField(blank=True, null=True)
    failure_reason = models.TextField(blank=True)

    # Webhook tracking
    webhook_received = models.BooleanField(default=False)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    webhook_data = models.JSONField(blank=True, null=True)

    # Refund tracking
    refund_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
    )
    refund_initiated_at = models.DateTimeField(null=True, blank=True)
    refund_completed_at = models.DateTimeField(null=True, blank=True)
    refund_gateway_id = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='ptxn_user_status_idx'),
            models.Index(fields=['booking_reference'], name='ptxn_booking_ref_idx'),
            models.Index(fields=['gateway', 'status'], name='ptxn_gw_status_idx'),
            models.Index(
                fields=['gateway_transaction_id'],
                name='ptxn_gw_txn_idx',
            ),
        ]

    def __str__(self):
        return f"{self.transaction_id} — {self.gateway} ₹{self.amount} ({self.status})"

    # --- State helpers ---

    def mark_pending(self, gateway_txn_id='', gateway_response=None):
        self.status = self.STATUS_PENDING
        if gateway_txn_id:
            self.gateway_transaction_id = gateway_txn_id
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            'status', 'gateway_transaction_id', 'gateway_response', 'updated_at',
        ])

    def mark_success(self, gateway_txn_id='', gateway_response=None):
        self.status = self.STATUS_SUCCESS
        if gateway_txn_id:
            self.gateway_transaction_id = gateway_txn_id
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            'status', 'gateway_transaction_id', 'gateway_response', 'updated_at',
        ])

    def mark_failed(self, reason='', gateway_response=None):
        self.status = self.STATUS_FAILED
        self.failure_reason = reason
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            'status', 'failure_reason', 'gateway_response', 'updated_at',
        ])

    def record_webhook(self, data):
        self.webhook_received = True
        self.webhook_received_at = timezone.now()
        self.webhook_data = data
        self.save(update_fields=[
            'webhook_received', 'webhook_received_at', 'webhook_data', 'updated_at',
        ])

    def initiate_refund(self, amount=None):
        if self.status != self.STATUS_SUCCESS:
            raise ValueError('Can only refund successful transactions')
        refund_amount = Decimal(str(amount)) if amount else self.amount
        if refund_amount > self.amount:
            raise ValueError('Refund amount cannot exceed transaction amount')
        self.refund_amount = refund_amount
        self.refund_initiated_at = timezone.now()
        self.status = self.STATUS_REFUNDED
        self.save(update_fields=[
            'refund_amount', 'refund_initiated_at', 'status', 'updated_at',
        ])


class PaymentReconciliation(TimeStampedModel):
    """
    Daily reconciliation record matching gateway settlements
    against our PaymentTransaction records.
    One row per (date, gateway) — NOT unique on date alone.
    """
    date = models.DateField(db_index=True)
    gateway = models.CharField(max_length=20, choices=PaymentTransaction.GATEWAY_CHOICES)
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    settled_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discrepancy = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transactions_matched = models.IntegerField(default=0)
    transactions_unmatched = models.IntegerField(default=0)
    details = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('discrepancy', 'Discrepancy'),
    ], default='pending')

    class Meta:
        app_label = 'payments'
        unique_together = ('date', 'gateway')
        ordering = ['-date']

    def __str__(self):
        return f"Recon {self.date} {self.gateway}: {self.status}"


# S13: Payment Idempotency model (for migration discovery)
from .idempotency import IdempotencyRecord  # noqa: F401, E402

# S7: Reconciliation line item model (for migration discovery)
from .reconciliation_engine import ReconciliationLineItem  # noqa: F401, E402