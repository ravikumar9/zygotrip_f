"""Settlement model for merchant payouts (PHASE 2, PROMPT 5)."""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel


class Settlement(TimeStampedModel):
    """Hotel settlement records - aggregated payable amounts."""
    
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending Payment'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Payment Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    hotel = models.ForeignKey(
        'hotels.Property',
        on_delete=models.PROTECT,
        related_name='settlements'
    )
    
    period_start = models.DateField(
        db_index=True,
        help_text="Settlement period start date"
    )
    period_end = models.DateField(
        db_index=True,
        help_text="Settlement period end date (inclusive)"
    )
    
    # Aggregated amounts from confirmed bookings
    total_gross = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Sum of gross_amount from CONFIRMED bookings"
    )
    total_commission = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Sum of commission_amount (Zygotrip cuts)"
    )
    total_gateway_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Sum of gateway_fee"
    )
    total_payable = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="gross - commission - gateway_fee"
    )
    
    # Total refunds issued (reduces payable)
    total_refunded = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total refunds awarded in this period"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True
    )
    
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When payment was completed"
    )
    
    payment_reference_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Reference ID from payment system"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Settlement notes or issues"
    )
    
    class Meta:
        app_label = 'booking'
        unique_together = ('hotel', 'period_start', 'period_end')
        indexes = [
            models.Index(fields=['hotel', 'status']),
            models.Index(fields=['period_start', 'status']),
        ]
        ordering = ['-period_end']
    
    def __str__(self):
        return (
            f"{self.hotel.name} - {self.period_start} to {self.period_end} "
            f"(₹{self.total_payable})"
        )


class SettlementLineItem(TimeStampedModel):
    """Individual booking reference in settlement."""
    
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    booking = models.ForeignKey(
        'booking.Booking',
        on_delete=models.PROTECT,
        related_name='settlement_line_items'
    )
    
    # Snapshot of booking amounts at settlement time
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    gateway_fee = models.DecimalField(max_digits=12, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        app_label = 'booking'
        indexes = [
            models.Index(fields=['settlement']),
            models.Index(fields=['booking']),
        ]
    
    def __str__(self):
        return f"Settlement Line Item - {self.booking.id}"
