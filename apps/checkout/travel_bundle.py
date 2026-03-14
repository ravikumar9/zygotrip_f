"""
Travel Orchestration — Bundle Builder & Multi-Product Trip Management.

Enables:
  - TravelBundle: group hotel + flight + cab + activity into a single trip
  - Dynamic package builder: auto-suggest complementary products
  - Unified booking lifecycle across verticals
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import TimeStampedModel


class TravelBundle(TimeStampedModel):
    """A travel bundle grouping multiple product bookings into one trip."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('partially_confirmed', 'Partially Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    bundle_ref = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name='travel_bundles')
    title = models.CharField(max_length=200, blank=True,
                             help_text="e.g. 'Goa Trip Dec 2025'")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')

    # Trip dates
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    destination_city = models.CharField(max_length=100, blank=True)

    # Financials
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    final_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    # Bundle discount (for booking 3+ products together)
    bundle_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        help_text="Extra discount for multi-product bundle")

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.bundle_ref} — {self.title or self.destination_city}"

    def save(self, *args, **kwargs):
        if not self.bundle_ref:
            date_str = timezone.now().strftime('%Y%m%d')
            short = str(self.uuid)[:6].upper()
            self.bundle_ref = f"TRIP-{date_str}-{short}"
        super().save(*args, **kwargs)

    def recalculate_totals(self):
        """Recalculate bundle totals from items."""
        items = self.items.filter(is_active=True)
        subtotal = sum(item.amount for item in items)
        self.total_amount = subtotal

        # Bundle discount for 3+ items
        item_count = items.count()
        if item_count >= 4:
            self.bundle_discount_percent = Decimal('10')
        elif item_count >= 3:
            self.bundle_discount_percent = Decimal('5')
        else:
            self.bundle_discount_percent = Decimal('0')

        bundle_disc = (subtotal * self.bundle_discount_percent / 100).quantize(Decimal('0.01'))
        self.discount_amount = bundle_disc
        self.final_amount = subtotal - bundle_disc
        self.save(update_fields=[
            'total_amount', 'discount_amount', 'final_amount',
            'bundle_discount_percent', 'updated_at'])


class BundleItem(TimeStampedModel):
    """Individual item in a travel bundle."""
    PRODUCT_TYPE_CHOICES = [
        ('hotel', 'Hotel'),
        ('flight', 'Flight'),
        ('cab', 'Cab'),
        ('bus', 'Bus'),
        ('activity', 'Activity'),
        ('package', 'Package'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    bundle = models.ForeignKey(TravelBundle, on_delete=models.CASCADE, related_name='items')
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)
    product_id = models.PositiveIntegerField(help_text="FK to the booking in the respective app")
    product_ref = models.CharField(max_length=100, blank=True,
                                   help_text="PNR, booking_ref, or public_booking_id")

    # Snapshot
    description = models.CharField(max_length=300, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Scheduling
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'checkout'
        ordering = ['start_datetime', 'created_at']
        indexes = [
            models.Index(fields=['bundle', 'product_type']),
        ]

    def __str__(self):
        return f"{self.product_type}: {self.description or self.product_ref}"


# ============================================================================
# MULTI-PRODUCT CART
# ============================================================================

class Cart(TimeStampedModel):
    """Multi-product shopping cart supporting all verticals."""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='carts')
    session_key = models.CharField(max_length=64, blank=True, db_index=True,
                                   help_text="For anonymous carts before login")
    expires_at = models.DateTimeField()

    class Meta:
        app_label = 'checkout'

    def __str__(self):
        return f"Cart {self.uuid}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items.filter(is_active=True))

    @property
    def item_count(self):
        return self.items.filter(is_active=True).count()


class CartItem(TimeStampedModel):
    """Individual item in the cart (any vertical)."""
    PRODUCT_TYPE_CHOICES = [
        ('hotel', 'Hotel'),
        ('flight', 'Flight'),
        ('cab', 'Cab'),
        ('bus', 'Bus'),
        ('activity', 'Activity'),
        ('package', 'Package'),
    ]

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)

    # Generic reference to the product
    product_id = models.PositiveIntegerField()
    product_snapshot = models.JSONField(default=dict, blank=True,
                                       help_text="Snapshot of product at time of add-to-cart")

    # Pricing
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    # Hold
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'checkout'
        indexes = [
            models.Index(fields=['cart', 'product_type']),
        ]

    def __str__(self):
        return f"{self.product_type} #{self.product_id} (x{self.quantity})"

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)
