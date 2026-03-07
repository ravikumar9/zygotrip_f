"""
Inventory Management Models - Production Grade (OTA Freeze)

Phase 2/3: Full inventory system with date-based calendar, hold management,
adjustment tracking, and audit logs.

Models:
  - SupplierPropertyMap   — external supplier identity mapping
  - PropertyInventory     — property-level aggregate (legacy compat)
  - PriceHistory          — immutable price audit trail
  - InventoryCalendar     — date-based room availability (source of truth)
  - InventoryHold         — time-limited inventory holds (TTL 15 min)
  - InventoryAdjustment   — owner/admin inventory changes with audit
  - InventoryLog          — immutable event log for all inventory mutations
"""

import uuid as _uuid_module
from decimal import Decimal
from datetime import date

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.hotels.models import Property


class SupplierPropertyMap(TimeStampedModel):
    """
    Maps internal properties to external supplier properties.
    - One property can map to multiple suppliers
    - Each supplier property maps to exactly one internal property
    - Immutable once verified (prevents accidental remappings)
    """
    
    SUPPLIER_CHOICES = [
        ('booking', 'Booking.com'),
        ('airbnb', 'Airbnb'),
        ('expedia', 'Expedia'),
        ('oyo', 'OYO'),
        ('tripadvisor', 'TripAdvisor'),
    ]
    
    # Relationship (many-to-one: one property has many suppliers)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='supplier_maps'
    )
    
    # Supplier identification (unique per supplier)
    supplier_name = models.CharField(
        max_length=50,
        choices=SUPPLIER_CHOICES,
        db_index=True
    )
    external_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Supplier's internal ID for this property"
    )
    
    # Supplier property details (for validation)
    supplier_property_name = models.CharField(max_length=255)
    supplier_city = models.CharField(max_length=80)
    supplier_lat = models.FloatField(
        null=True,
        blank=True,
        help_text="Latitude from supplier data"
    )
    supplier_lng = models.FloatField(
        null=True,
        blank=True,
        help_text="Longitude from supplier data"
    )
    
    # Matching confidence
    confidence_score = models.FloatField(
        default=0.0,
        help_text="0.0-1.0 matching confidence score"
    )
    verified = models.BooleanField(
        default=False,
        help_text="Manual verification flag (immutable after True)"
    )

    # Manual override flag
    manual_override = models.BooleanField(
        default=False,
        help_text="True when mapping was manually overridden"
    )
    
    # Audit trail
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_supplier_maps'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('supplier_name', 'external_id')
        indexes = [
            models.Index(fields=['supplier_name', 'external_id']),
            models.Index(fields=['property', 'verified']),
        ]
        ordering = ['-verified', '-confidence_score']
    
    def __str__(self):
        return f"{self.property.name} → {self.supplier_name} ({self.external_id})"
    
    def clean(self):
        """Validate mapping before save"""
        # Cannot unverify once verified
        if self.pk:
            existing = SupplierPropertyMap.objects.get(pk=self.pk)
            if existing.verified and not self.verified:
                raise ValidationError("Cannot unverify a mapping")
        
        # Confidence must be between 0 and 1
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValidationError("Confidence score must be between 0.0 and 1.0")
        
        # If verified, confidence must be >= 0.8
        if self.verified and self.confidence_score < 0.8:
            raise ValidationError("Verified mappings must have confidence >= 0.8")

        # Manual override requires verified mapping
        if self.manual_override and not self.verified:
            raise ValidationError("Manual override requires verified=True")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PropertyInventory(TimeStampedModel):
    """
    Tracks real-time inventory per property.
    Used for concurrency-safe deductions.
    """
    
    property = models.OneToOneField(
        Property,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    
    # Available rooms
    total_rooms = models.PositiveIntegerField(default=0)
    available_rooms = models.PositiveIntegerField(default=0)
    
    # Sync status
    last_supplier_sync = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('syncing', 'Syncing'),
            ('synced', 'Synced'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    # Version for optimistic locking
    version = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Property Inventories"
    
    def __str__(self):
        return f"{self.property.name}: {self.available_rooms}/{self.total_rooms}"
    
    def clean(self):
        """Validate inventory constraints"""
        if self.available_rooms > self.total_rooms:
            raise ValidationError("Available rooms cannot exceed total rooms")
        if self.available_rooms < 0 or self.total_rooms < 0:
            raise ValidationError("Room counts cannot be negative")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PriceHistory(TimeStampedModel):
    """
    Immutable price history log.
    NEVER UPDATE existing rows - only insert new ones.
    Provides complete audit trail for pricing decisions.
    """
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='price_history'
    )
    
    # Pricing data (immutable after creation)
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base price before multipliers"
    )
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final calculated price"
    )
    
    # Pricing factors
    demand_score = models.PositiveSmallIntegerField(
        default=50,
        help_text="0-100 demand indicator"
    )
    competitor_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Competitor reference price"
    )
    
    # Change from previous price
    price_change_percent = models.FloatField(
        default=0.0,
        help_text="% change from previous price"
    )
    
    # Calculated by
    calculated_by = models.CharField(
        max_length=50,
        default='system',
        help_text="Which engine calculated this"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property', '-created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name_plural = "Price Histories"
    
    def __str__(self):
        return f"{self.property.name} @ ₹{self.final_price} ({self.created_at.date()})"

    def save(self, *args, **kwargs):
        # Enforce 2-decimal precision by rounding
        if self.base_price is not None:
            self.base_price = Decimal(str(self.base_price)).quantize(Decimal('0.01'))
        if self.final_price is not None:
            self.final_price = Decimal(str(self.final_price)).quantize(Decimal('0.01'))
        if self.competitor_price is not None:
            self.competitor_price = Decimal(str(self.competitor_price)).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


# ============================================================================
# PHASE 2: INVENTORY CALENDAR — Date-based room availability (source of truth)
# ============================================================================

class InventoryCalendar(TimeStampedModel):
    """
    Date-based inventory for each room type — the authoritative availability source.

    RULES:
    1. One row per (room_type, date) — enforced by unique_together
    2. total_rooms = physical rooms of this type
    3. available_rooms = total_rooms - booked_rooms - blocked_rooms - held_rooms
    4. DB constraint: available_rooms >= 0
    5. All mutations MUST use select_for_update() (concurrency-safe)
    6. Supports min_stay, max_stay, CTA (close to arrival), CTD (close to departure)
    """
    room_type = models.ForeignKey(
        'rooms.RoomType',
        on_delete=models.PROTECT,
        related_name='inventory_calendar',
    )
    date = models.DateField(db_index=True)

    # Capacity
    total_rooms = models.PositiveIntegerField(
        default=0,
        help_text="Total physical rooms of this type",
    )
    available_rooms = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Rooms available for booking (computed: total - booked - blocked - held)",
    )
    booked_rooms = models.PositiveIntegerField(
        default=0,
        help_text="Rooms with confirmed bookings",
    )
    blocked_rooms = models.PositiveIntegerField(
        default=0,
        help_text="Rooms blocked by owner (maintenance, VIP, etc.)",
    )
    held_rooms = models.PositiveIntegerField(
        default=0,
        help_text="Rooms in active hold (TTL-limited)",
    )

    # Date-specific pricing override (nullable → falls back to RoomType.base_price)
    rate_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Date-specific rate; NULL = use RoomType.base_price",
    )

    # Restrictions
    is_closed = models.BooleanField(
        default=False, db_index=True,
        help_text="Close this date for all bookings",
    )
    min_stay = models.PositiveIntegerField(
        default=1,
        help_text="Minimum length of stay starting this date",
    )
    max_stay = models.PositiveIntegerField(
        default=30,
        help_text="Maximum length of stay starting this date",
    )
    close_to_arrival = models.BooleanField(
        default=False,
        help_text="CTA — no new check-ins on this date",
    )
    close_to_departure = models.BooleanField(
        default=False,
        help_text="CTD — no check-outs on this date",
    )

    class Meta:
        app_label = 'inventory'
        unique_together = [('room_type', 'date')]
        indexes = [
            models.Index(fields=['room_type', 'date']),
            models.Index(fields=['date', 'is_closed']),
            models.Index(fields=['room_type', 'date', 'is_closed']),
            models.Index(fields=['room_type', 'date', 'available_rooms'],
                         name='invcal_avail_range_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(available_rooms__gte=0),
                name='invcal_available_non_negative',
            ),
            models.CheckConstraint(
                check=models.Q(min_stay__gte=1),
                name='invcal_min_stay_positive',
            ),
        ]
        ordering = ['room_type', 'date']

    def __str__(self):
        return (
            f"{self.room_type.name} {self.date}: "
            f"{self.available_rooms}/{self.total_rooms} avail"
        )

    def recompute_available(self):
        """Recompute available_rooms from components. Call inside select_for_update()."""
        computed = self.total_rooms - self.booked_rooms - self.blocked_rooms - self.held_rooms
        self.available_rooms = max(0, computed)

    @property
    def effective_rate(self):
        """Return date rate or fallback to room type base_price."""
        if self.rate_override is not None:
            return self.rate_override
        return self.room_type.base_price


# ============================================================================
# PHASE 3: INVENTORY HOLD — Time-limited reservation holds
# ============================================================================

class InventoryHold(TimeStampedModel):
    """
    Temporary inventory hold with TTL.

    RULES:
    1. Hold TTL = 15 minutes (configurable via HOLD_TTL_MINUTES)
    2. Celery task releases expired holds every 2 minutes
    3. On hold creation: InventoryCalendar.held_rooms += quantity
    4. On hold release:  InventoryCalendar.held_rooms -= quantity, available += quantity
    5. On hold conversion (confirm): held_rooms -= quantity, booked_rooms += quantity
    """
    HOLD_TTL_MINUTES = 15

    STATUS_ACTIVE = 'active'
    STATUS_PAYMENT_PENDING = 'payment_pending'
    STATUS_CONVERTED = 'converted'
    STATUS_EXPIRED = 'expired'
    STATUS_RELEASED = 'released'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAYMENT_PENDING, 'Payment in Progress'),
        (STATUS_CONVERTED, 'Converted to Booking'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_RELEASED, 'Manually Released'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Valid state transitions
    VALID_TRANSITIONS = {
        STATUS_ACTIVE: {STATUS_PAYMENT_PENDING, STATUS_CONVERTED, STATUS_EXPIRED, STATUS_RELEASED, STATUS_CANCELLED},
        STATUS_PAYMENT_PENDING: {STATUS_CONVERTED, STATUS_EXPIRED, STATUS_CANCELLED},
        STATUS_CONVERTED: set(),
        STATUS_EXPIRED: set(),
        STATUS_RELEASED: set(),
        STATUS_CANCELLED: set(),
    }

    hold_id = models.UUIDField(
        default=_uuid_module.uuid4, unique=True, editable=False, db_index=True,
    )
    booking_context = models.ForeignKey(
        'booking.BookingContext',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_holds',
    )
    booking = models.ForeignKey(
        'booking.Booking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_holds',
    )
    room_type = models.ForeignKey(
        'rooms.RoomType',
        on_delete=models.PROTECT,
        related_name='inventory_holds',
    )
    date = models.DateField(db_index=True)
    rooms_held = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True,
    )
    hold_expires_at = models.DateTimeField(db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'inventory'
        indexes = [
            models.Index(fields=['room_type', 'date', 'status']),
            models.Index(fields=['status', 'hold_expires_at']),
            models.Index(fields=['booking_context']),
        ]

    def __str__(self):
        return f"Hold {self.hold_id}: {self.room_type.name} {self.date} x{self.rooms_held} ({self.status})"

    @property
    def is_expired(self):
        return self.status == self.STATUS_ACTIVE and timezone.now() > self.hold_expires_at

    def transition_to(self, new_status):
        """Safe state transition with validation."""
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f'Cannot transition hold from {self.status} to {new_status}'
            )
        self.status = new_status
        if new_status == self.STATUS_PAYMENT_PENDING:
            # Auto-extend hold by 10 minutes when payment starts
            self.hold_expires_at = timezone.now() + timedelta(minutes=10)
        elif new_status in (self.STATUS_RELEASED, self.STATUS_EXPIRED, self.STATUS_CANCELLED):
            self.released_at = timezone.now()
        elif new_status == self.STATUS_CONVERTED:
            self.converted_at = timezone.now()
        self.save()


# ============================================================================
# INVENTORY ADJUSTMENT — Owner/admin inventory changes with audit trail
# ============================================================================

class InventoryAdjustment(TimeStampedModel):
    """
    Records every manual inventory change by owner or admin.
    Immutable audit trail — never update, only insert.
    """
    REASON_INITIAL = 'initial_setup'
    REASON_OWNER_UPDATE = 'owner_update'
    REASON_MAINTENANCE = 'maintenance'
    REASON_ADMIN_OVERRIDE = 'admin_override'
    REASON_SYNC = 'supplier_sync'
    REASON_CORRECTION = 'correction'

    REASON_CHOICES = [
        (REASON_INITIAL, 'Initial Setup'),
        (REASON_OWNER_UPDATE, 'Owner Update'),
        (REASON_MAINTENANCE, 'Maintenance Block'),
        (REASON_ADMIN_OVERRIDE, 'Admin Override'),
        (REASON_SYNC, 'Supplier Sync'),
        (REASON_CORRECTION, 'Data Correction'),
    ]

    uuid = models.UUIDField(default=_uuid_module.uuid4, unique=True, editable=False)
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.PROTECT, related_name='inventory_adjustments',
    )
    date_start = models.DateField()
    date_end = models.DateField(help_text="Inclusive end date")
    field_changed = models.CharField(
        max_length=30,
        help_text="Which field was changed: total_rooms, blocked_rooms, is_closed, rate_override, etc.",
    )
    old_value = models.CharField(max_length=50, blank=True)
    new_value = models.CharField(max_length=50)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    note = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_adjustments',
    )

    class Meta:
        app_label = 'inventory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_type', '-created_at']),
            models.Index(fields=['reason']),
        ]

    def __str__(self):
        return (
            f"Adj {self.room_type.name} {self.date_start}→{self.date_end}: "
            f"{self.field_changed} {self.old_value}→{self.new_value}"
        )


# ============================================================================
# INVENTORY LOG — Immutable event stream for all inventory mutations
# ============================================================================

class InventoryLog(TimeStampedModel):
    """
    Append-only log of every inventory mutation.
    Used for debugging, reconciliation, and analytics.
    """
    EVENT_HOLD_CREATED = 'hold_created'
    EVENT_HOLD_RELEASED = 'hold_released'
    EVENT_HOLD_EXPIRED = 'hold_expired'
    EVENT_HOLD_CONVERTED = 'hold_converted'
    EVENT_BOOKING_CONFIRMED = 'booking_confirmed'
    EVENT_BOOKING_CANCELLED = 'booking_cancelled'
    EVENT_ADJUSTMENT = 'adjustment'
    EVENT_SYNC = 'supplier_sync'

    EVENT_CHOICES = [
        (EVENT_HOLD_CREATED, 'Hold Created'),
        (EVENT_HOLD_RELEASED, 'Hold Released'),
        (EVENT_HOLD_EXPIRED, 'Hold Expired'),
        (EVENT_HOLD_CONVERTED, 'Hold Converted'),
        (EVENT_BOOKING_CONFIRMED, 'Booking Confirmed'),
        (EVENT_BOOKING_CANCELLED, 'Booking Cancelled'),
        (EVENT_ADJUSTMENT, 'Manual Adjustment'),
        (EVENT_SYNC, 'Supplier Sync'),
    ]

    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.PROTECT, related_name='inventory_logs',
    )
    date = models.DateField(db_index=True)
    event = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    quantity = models.IntegerField(help_text="Rooms affected (positive or negative)")
    available_before = models.PositiveIntegerField()
    available_after = models.PositiveIntegerField()
    reference_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Booking UUID, hold UUID, or adjustment UUID",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_log_entries',
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'inventory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_type', 'date', '-created_at']),
            models.Index(fields=['event', '-created_at']),
            models.Index(fields=['reference_id']),
        ]

    def __str__(self):
        return f"InvLog {self.event}: {self.room_type.name} {self.date} Δ{self.quantity}"


# ============================================================================
# SUPPLIER AGGREGATION MODELS (OTA-grade multi-supplier inventory)
# ============================================================================


class SupplierRoom(TimeStampedModel):
    """
    Maps a supplier's room type to an internal RoomType.
    Enables inventory aggregation across multiple suppliers (Booking.com,
    Expedia, Airbnb, etc.) into a single canonical room.
    """
    supplier_map = models.ForeignKey(
        SupplierPropertyMap, on_delete=models.CASCADE,
        related_name='supplier_rooms',
    )
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplier_rooms',
        help_text='Matched internal room type (null if unmatched)',
    )
    external_room_id = models.CharField(max_length=100, db_index=True)
    supplier_room_name = models.CharField(max_length=255)
    canonical_name = models.CharField(
        max_length=100, blank=True,
        help_text='Normalized room name (e.g. Deluxe, Standard)',
    )
    capacity = models.PositiveIntegerField(default=2)
    bed_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    match_confidence = models.FloatField(
        default=0.0, help_text='0.0-1.0 room matching confidence',
    )

    class Meta:
        app_label = 'inventory'
        unique_together = ('supplier_map', 'external_room_id')
        indexes = [
            models.Index(fields=['room_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.supplier_map.supplier_name}:{self.supplier_room_name} → {self.room_type}"


class SupplierRatePlan(TimeStampedModel):
    """
    Rate plans from external suppliers.
    A single SupplierRoom may have multiple rate plans (e.g. non-refundable,
    free cancellation, pay-at-hotel, member rate).
    """
    PLAN_TYPE_CHOICES = [
        ('standard', 'Standard'),
        ('non_refundable', 'Non-Refundable'),
        ('member', 'Member Rate'),
        ('pay_at_hotel', 'Pay at Hotel'),
        ('free_cancel', 'Free Cancellation'),
    ]

    supplier_room = models.ForeignKey(
        SupplierRoom, on_delete=models.CASCADE,
        related_name='rate_plans',
    )
    external_rate_plan_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    plan_type = models.CharField(
        max_length=30, choices=PLAN_TYPE_CHOICES, default='standard',
    )
    meal_plan_code = models.CharField(
        max_length=30, blank=True,
        help_text='Supplier meal plan code (mapped to RoomMealPlan.code)',
    )
    is_refundable = models.BooleanField(default=True)
    cancellation_deadline_hours = models.PositiveIntegerField(
        default=24, help_text='Hours before check-in for free cancellation',
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = 'inventory'
        unique_together = ('supplier_room', 'external_rate_plan_id')

    def __str__(self):
        return f"{self.supplier_room.supplier_map.supplier_name}:{self.name}"


class SupplierInventory(TimeStampedModel):
    """
    Daily inventory snapshot from an external supplier.
    Aggregated into InventoryCalendar via InventoryAggregationService.

    Strategy: min rate wins (best price for guest), max availability shown.
    """
    supplier_room = models.ForeignKey(
        SupplierRoom, on_delete=models.CASCADE,
        related_name='inventory_entries',
    )
    rate_plan = models.ForeignKey(
        SupplierRatePlan, on_delete=models.CASCADE,
        related_name='inventory_entries', null=True, blank=True,
    )
    date = models.DateField(db_index=True)
    available_rooms = models.PositiveIntegerField(default=0)
    rate_per_night = models.DecimalField(max_digits=12, decimal_places=2)
    min_stay = models.PositiveIntegerField(default=1)
    max_stay = models.PositiveIntegerField(default=30)
    is_closed = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'inventory'
        unique_together = ('supplier_room', 'rate_plan', 'date')
        indexes = [
            models.Index(fields=['date', 'is_closed']),
            models.Index(fields=['supplier_room', 'date']),
        ]

    def __str__(self):
        return f"{self.supplier_room} {self.date}: {self.available_rooms}@₹{self.rate_per_night}"


# ============================================================================
# INVENTORY POOL — Aggregated availability across direct + all suppliers
# ============================================================================

class InventoryPool(TimeStampedModel):
    """
    Aggregated availability for a (room_type, date) combining direct inventory
    and all supplier inventory.  Search APIs read ONLY from this table.

    Recomputed by ``recompute_pool()`` whenever any source changes.
    """
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE, related_name='inventory_pool',
    )
    date = models.DateField(db_index=True)

    # Direct (InventoryCalendar)
    direct_available = models.PositiveIntegerField(default=0)
    direct_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Supplier aggregate
    supplier_available = models.PositiveIntegerField(default=0)
    best_supplier_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    best_supplier_name = models.CharField(max_length=50, blank=True)

    # Composite
    total_available = models.PositiveIntegerField(default=0)
    best_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_closed = models.BooleanField(default=False)

    # Metadata
    last_recomputed = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'inventory'
        unique_together = ('room_type', 'date')
        indexes = [
            models.Index(fields=['room_type', 'date', 'is_closed']),
            models.Index(fields=['date', 'total_available']),
        ]

    def __str__(self):
        return f"Pool {self.room_type} {self.date}: {self.total_available}@₹{self.best_rate}"

    @classmethod
    def recompute(cls, room_type, target_date):
        """
        Recompute the pool row from InventoryCalendar + all SupplierInventory
        for this (room_type, date).
        """
        # Direct inventory
        direct_avail = 0
        direct_rate = Decimal('0')
        try:
            cal = InventoryCalendar.objects.get(room_type=room_type, date=target_date)
            direct_avail = cal.available_rooms
            direct_rate = cal.effective_rate
        except InventoryCalendar.DoesNotExist:
            pass

        # Supplier inventory
        supplier_rows = SupplierInventory.objects.filter(
            supplier_room__room_type=room_type,
            date=target_date,
            is_closed=False,
        ).select_related('supplier_room__supplier_map')

        sup_avail = 0
        best_sup_rate = Decimal('0')
        best_sup_name = ''
        for si in supplier_rows:
            sup_avail += si.available_rooms
            if si.rate_per_night > 0 and (best_sup_rate == 0 or si.rate_per_night < best_sup_rate):
                best_sup_rate = si.rate_per_night
                best_sup_name = si.supplier_room.supplier_map.supplier_name

        total = direct_avail + sup_avail
        best = direct_rate
        if best_sup_rate > 0 and (best == 0 or best_sup_rate < best):
            best = best_sup_rate

        pool, _ = cls.objects.update_or_create(
            room_type=room_type, date=target_date,
            defaults={
                'direct_available': direct_avail,
                'direct_rate': direct_rate,
                'supplier_available': sup_avail,
                'best_supplier_rate': best_sup_rate,
                'best_supplier_name': best_sup_name,
                'total_available': total,
                'best_rate': best,
                'is_closed': total == 0,
            },
        )
        return pool


# ============================================================================
# SUPPLIER HEALTH — Live performance tracking
# ============================================================================

class SupplierHealth(TimeStampedModel):
    """
    Rolling performance metrics for each supplier.
    Updated on every API call; checked before routing bookings.
    """
    supplier_name = models.CharField(max_length=50, unique=True, db_index=True)
    total_requests = models.PositiveIntegerField(default=0)
    successful_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)
    timeout_requests = models.PositiveIntegerField(default=0)
    avg_latency_ms = models.FloatField(default=0)
    p99_latency_ms = models.FloatField(default=0)
    error_rate = models.FloatField(default=0, help_text='0-1 ratio')
    is_healthy = models.BooleanField(default=True, db_index=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=200, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'inventory'

    def __str__(self):
        status = 'HEALTHY' if self.is_healthy else 'DEGRADED'
        return f"{self.supplier_name} [{status}] err={self.error_rate:.2%} lat={self.avg_latency_ms:.0f}ms"

    def record_success(self, latency_ms):
        self.total_requests += 1
        self.successful_requests += 1
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_requests - 1) + latency_ms) / self.total_requests
        )
        self.last_success_at = timezone.now()
        self._recompute_health()
        self.save()

    def record_failure(self, latency_ms=0, is_timeout=False):
        self.total_requests += 1
        self.failed_requests += 1
        if is_timeout:
            self.timeout_requests += 1
        self.last_failure_at = timezone.now()
        self._recompute_health()
        self.save()

    def _recompute_health(self):
        if self.total_requests > 0:
            self.error_rate = self.failed_requests / self.total_requests
        else:
            self.error_rate = 0
        # Auto-disable if error rate > 30% over last 50+ requests
        if self.total_requests >= 50 and self.error_rate > 0.30:
            if self.is_healthy:
                self.is_healthy = False
                self.disabled_at = timezone.now()
                self.disabled_reason = f'Error rate {self.error_rate:.0%} exceeded 30% threshold'
        elif self.error_rate < 0.10 and not self.is_healthy:
            # Auto-recover when error rate drops below 10%
            self.is_healthy = True
            self.disabled_at = None
            self.disabled_reason = ''


# S4: Channel Manager models (for migration discovery)
from .channel_manager import (  # noqa: F401, E402
    ChannelConnection, ChannelRateSync,
    ChannelAvailabilitySync, ChannelWebhookLog,
)