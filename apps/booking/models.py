import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_future_date
from builtins import property as builtin_property


class Booking(TimeStampedModel):
	STATUS_HOLD = 'hold'
	STATUS_PAYMENT_PENDING = 'payment_pending'
	STATUS_CONFIRMED = 'confirmed'
	STATUS_CANCELLED = 'cancelled'
	STATUS_FAILED = 'failed'
	STATUS_REFUND_PENDING = 'refund_pending'
	STATUS_REFUNDED = 'refunded'
	STATUS_SETTLEMENT_PENDING = 'settlement_pending'

	# OTA Lifecycle statuses (Phase 1)
	STATUS_INITIATED = 'initiated'         # Pre-booking: user started the funnel
	STATUS_CHECKED_IN = 'checked_in'       # Guest has checked in at the property
	STATUS_CHECKED_OUT = 'checked_out'     # Guest has checked out — triggers settlement
	STATUS_SETTLED = 'settled'             # Payout released to owner
	
	# Legacy statuses (for migration compatibility)
	STATUS_PENDING = 'pending'
	STATUS_REVIEW = 'review'
	STATUS_PAYMENT = 'payment'

	STATUS_CHOICES = [
		(STATUS_INITIATED, 'Initiated'),
		(STATUS_HOLD, 'Hold'),
		(STATUS_PAYMENT_PENDING, 'Payment Pending'),
		(STATUS_CONFIRMED, 'Confirmed'),
		(STATUS_CHECKED_IN, 'Checked In'),
		(STATUS_CHECKED_OUT, 'Checked Out'),
		(STATUS_CANCELLED, 'Cancelled'),
		(STATUS_FAILED, 'Failed'),
		(STATUS_REFUND_PENDING, 'Refund Pending'),
		(STATUS_REFUNDED, 'Refunded'),
		(STATUS_SETTLEMENT_PENDING, 'Settlement Pending'),
		(STATUS_SETTLED, 'Settled'),
		# Legacy
		(STATUS_PENDING, 'Pending'),
		(STATUS_REVIEW, 'Review'),
		(STATUS_PAYMENT, 'Payment'),
	]
	
	# Full OTA lifecycle state machine
	VALID_TRANSITIONS = {
		STATUS_INITIATED: [STATUS_HOLD, STATUS_PAYMENT_PENDING, STATUS_CANCELLED],
		STATUS_HOLD: [STATUS_PAYMENT_PENDING, STATUS_FAILED, STATUS_CANCELLED],
		STATUS_PAYMENT_PENDING: [STATUS_CONFIRMED, STATUS_FAILED, STATUS_CANCELLED],
		STATUS_CONFIRMED: [STATUS_CHECKED_IN, STATUS_REFUND_PENDING, STATUS_CANCELLED],
		STATUS_CHECKED_IN: [STATUS_CHECKED_OUT, STATUS_CANCELLED],
		STATUS_CHECKED_OUT: [STATUS_SETTLEMENT_PENDING, STATUS_SETTLED],
		STATUS_SETTLEMENT_PENDING: [STATUS_SETTLED, STATUS_REFUND_PENDING, STATUS_CANCELLED],
		STATUS_SETTLED: [],
		STATUS_REFUND_PENDING: [STATUS_REFUNDED, STATUS_CANCELLED],
		STATUS_FAILED: [STATUS_CANCELLED],
		STATUS_CANCELLED: [],
		STATUS_REFUNDED: [],
		# Legacy transitions
		STATUS_PENDING: [STATUS_REVIEW, STATUS_PAYMENT, STATUS_CANCELLED],
		STATUS_REVIEW: [STATUS_PAYMENT, STATUS_CANCELLED],
		STATUS_PAYMENT: [STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_FAILED],
	}

	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	public_booking_id = models.CharField(max_length=50, unique=True, editable=False, db_index=True, null=True, blank=True)
	idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
		related_name='bookings', null=True, blank=True,
		help_text="NULL for guest bookings (anonymous checkout)"
	)
	is_guest_booking = models.BooleanField(
		default=False, db_index=True,
		help_text="True if booked without authentication"
	)
	property = models.ForeignKey('hotels.Property', on_delete=models.PROTECT, related_name='bookings')
	check_in = models.DateField(validators=[validate_future_date], db_index=True)
	check_out = models.DateField(validators=[validate_future_date], db_index=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_HOLD, db_index=True)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	promo_code = models.CharField(max_length=30, blank=True)
	
	# FINANCIAL FIELDS (merchant model)
	gross_amount = models.DecimalField(
		max_digits=12, 
		decimal_places=2, 
		default=0,
		help_text="Total booking value before commission"
	)
	commission_amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="Platform commission (Zygotrip cut)"
	)
	gst_amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="18% GST on gross amount"
	)
	gateway_fee = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="Payment gateway fee"
	)
	net_payable_to_hotel = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="gross_amount - commission_amount - gateway_fee"
	)
	refund_amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="Amount refunded to customer (if cancelled)"
	)
	settlement_status = models.CharField(
		max_length=20,
		choices=[
			('unsettled', 'Unsettled'),
			('settlement_pending', 'Settlement Pending'),
			('settled', 'Settled'),
		],
		default='unsettled',
		db_index=True
	)
	payment_reference_id = models.CharField(
		max_length=100,
		unique=True,
		null=True,
		blank=True,
		db_index=True,
		help_text="Payment gateway transaction ID"
	)
	refund_reference_id = models.CharField(
		max_length=100,
		null=True,
		blank=True,
		db_index=True,
		help_text="Payment gateway refund ID"
	)
	
	# HOLD management
	hold_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
	
	# GUEST DETAILS (directly on booking for easy access)
	guest_name = models.CharField(max_length=120, blank=True)
	guest_email = models.EmailField(blank=True)
	guest_phone = models.CharField(max_length=20, blank=True)
	
	# Booking timer (10 minutes from creation)
	timer_expires_at = models.DateTimeField(null=True, blank=True)
	
	def save(self, *args, **kwargs):
		# Generate public_booking_id on first creation
		if not self.pk and not self.public_booking_id:
			date_str = self.created_at.strftime('%Y%m%d') if self.created_at else timezone.now().strftime('%Y%m%d')
			short_id = str(self.uuid)[:8].upper()
			self.public_booking_id = f"BK-{date_str}-HTL-{short_id}"
		# Set hold_expires_at on HOLD status creation (30 minutes hold window)
		if not self.pk and self.status == self.STATUS_HOLD:
			self.hold_expires_at = timezone.now() + timedelta(minutes=30)
		# Set timer on first creation (only for legacy review and payment statuses)
		if not self.pk and self.status in [self.STATUS_REVIEW, self.STATUS_PAYMENT]:
			self.timer_expires_at = timezone.now() + timedelta(minutes=10)
		super().save(*args, **kwargs)

	def is_hold_expired(self):
		"""Check if this HOLD booking's reservation has expired."""
		if self.status != self.STATUS_HOLD or not self.hold_expires_at:
			return False
		return timezone.now() > self.hold_expires_at

	def is_timer_expired(self):
		if self.timer_expires_at is None:
			return False
		return timezone.now() > self.timer_expires_at

	@builtin_property
	def timer_seconds(self):
		if self.timer_expires_at is None:
			return 0
		remaining = (self.timer_expires_at - timezone.now()).total_seconds()
		return max(0, int(remaining))

	def __str__(self):
		return f"{self.uuid}"

	class Meta:
		app_label = 'booking'
		indexes = [
			models.Index(fields=['status', 'hold_expires_at'], name='bk_status_hold_idx'),
			models.Index(fields=['property', 'status', '-created_at'], name='bk_prop_status_idx'),
			models.Index(fields=['user', 'status', '-created_at'], name='bk_user_status_idx'),
			models.Index(fields=['check_in', 'check_out'], name='bk_dates_idx'),
			models.Index(fields=['property', 'check_in', 'check_out'], name='bk_prop_dates_idx'),
			models.Index(fields=['status', '-created_at'], name='bk_status_created_idx'),
		]


class BookingRoom(TimeStampedModel):
	booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='rooms')
	room_type = models.ForeignKey('rooms.RoomType', on_delete=models.PROTECT)
	quantity = models.PositiveIntegerField(default=1)

	class Meta:
		app_label = 'booking'


class BookingGuest(TimeStampedModel):
	booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='guests')
	full_name = models.CharField(max_length=120)
	age = models.PositiveIntegerField(default=18)
	email = models.EmailField(blank=True)


class BookingPriceBreakdown(TimeStampedModel):
	booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='price_breakdown')
	base_amount = models.DecimalField(max_digits=12, decimal_places=2)
	meal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	promo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2)


class BookingStatusHistory(TimeStampedModel):
	booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='status_history')
	status = models.CharField(max_length=20, choices=Booking.STATUS_CHOICES)
	note = models.CharField(max_length=200, blank=True)


class BookingContext(TimeStampedModel):
	"""
	Phase 1: Persistent booking session context.
	Captures every parameter of the booking funnel before a Booking record is created.
	Enables session recovery, analytics, and price-lock windows.
	"""
	# UUID primary lookup — all frontend URLs use this, never the numeric PK
	uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

	# Session identity
	session_key = models.CharField(max_length=40, blank=True, db_index=True)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True, blank=True,
		related_name='booking_contexts'
	)

	# What they want to book
	property = models.ForeignKey(
		'hotels.Property',
		on_delete=models.SET_NULL,
		null=True, blank=True,
		related_name='booking_contexts'
	)
	room_type = models.ForeignKey(
		'rooms.RoomType',
		on_delete=models.SET_NULL,
		null=True, blank=True,
		related_name='booking_contexts'
	)
	checkin = models.DateField()
	checkout = models.DateField()
	adults = models.PositiveIntegerField(default=1)
	children = models.PositiveIntegerField(default=0)
	rooms = models.PositiveIntegerField(default=1)
	meal_plan = models.CharField(max_length=50, blank=True)

	# Pricing snapshot at time of context creation
	base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	meal_amount = models.DecimalField(
		max_digits=12, decimal_places=2, default=0,
		help_text='Total meal add-on cost (price_modifier × nights × rooms)'
	)
	property_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	platform_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	promo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	final_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

	# Price lock fields — ensures price cannot change during checkout
	price_locked = models.BooleanField(
		default=False, db_index=True,
		help_text='True when price snapshot is locked for checkout'
	)
	locked_price = models.DecimalField(
		max_digits=12, decimal_places=2, default=0,
		help_text='The exact price the customer will pay (immutable after lock)'
	)
	price_expires_at = models.DateTimeField(
		null=True, blank=True,
		help_text='When the price lock expires (same as expires_at by default)'
	)
	rate_plan_id = models.CharField(
		max_length=100, blank=True,
		help_text='External rate plan identifier (from supplier)'
	)
	supplier_id = models.CharField(
		max_length=100, blank=True,
		help_text='Supplier identifier for this rate'
	)

	# Promo tracking
	promo_code = models.CharField(max_length=30, blank=True)

	# Link to actual booking once created
	booking = models.ForeignKey(
		Booking,
		on_delete=models.SET_NULL,
		null=True, blank=True,
		related_name='contexts'
	)

	# Lifecycle
	STATUS_ACTIVE = 'active'
	STATUS_CONVERTED = 'converted'
	STATUS_EXPIRED = 'expired'
	STATUS_ABANDONED = 'abandoned'
	CONTEXT_STATUS_CHOICES = [
		(STATUS_ACTIVE, 'Active'),
		(STATUS_CONVERTED, 'Converted to Booking'),
		(STATUS_EXPIRED, 'Expired'),
		(STATUS_ABANDONED, 'Abandoned'),
	]
	context_status = models.CharField(
		max_length=20,
		choices=CONTEXT_STATUS_CHOICES,
		default=STATUS_ACTIVE,
		db_index=True
	)
	expires_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		app_label = 'booking'
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['session_key'], name='bkctx_session_idx'),
			models.Index(fields=['user', 'context_status'], name='bkctx_user_status_idx'),
			models.Index(fields=['expires_at'], name='bkctx_expires_idx'),
		]

	def __str__(self):
		return f"BookingContext({self.property}, {self.checkin}→{self.checkout}, {self.context_status})"


class GuestBookingContext(TimeStampedModel):
	"""
	Phase 1 (17-Phase Freeze): Guest checkout support.
	Captures guest identity + device fingerprint for anonymous bookings.
	Linked to BookingContext via UUID for session recovery.
	"""
	booking = models.OneToOneField(
		Booking, on_delete=models.CASCADE,
		related_name='guest_context', null=True, blank=True,
	)
	booking_context = models.ForeignKey(
		BookingContext, on_delete=models.SET_NULL,
		related_name='guest_contexts', null=True, blank=True,
	)
	email = models.EmailField(db_index=True)
	phone = models.CharField(max_length=20, blank=True)
	full_name = models.CharField(max_length=150, blank=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	session_key = models.CharField(max_length=40, blank=True, db_index=True)
	device_fingerprint = models.ForeignKey(
		'core.DeviceFingerprint', on_delete=models.SET_NULL,
		null=True, blank=True, related_name='guest_bookings',
	)
	fraud_score = models.IntegerField(
		default=0, help_text="Fraud score at time of booking (0-100)"
	)

	class Meta:
		app_label = 'booking'
		indexes = [
			models.Index(fields=['email'], name='gbc_email_idx'),
			models.Index(fields=['session_key'], name='gbc_session_idx'),
		]

	def __str__(self):
		return f"GuestBooking({self.email}, booking={self.booking_id})"


# Import models from distributed_locks for migration generation
from .distributed_locks import BookingRetryQueue
from .settlement_models import Settlement, SettlementLineItem
from .cancellation_models import CancellationPolicy, CancellationException
from .voucher_service import BookingVoucher
from .supplier_reconciliation import SupplierReconciliation, SupplierReconciliationItem  # noqa: F401

# ============================================================================
# BOOKING INVOICE — GST-Compliant Invoice System (System 14)
# ============================================================================

class BookingInvoice(TimeStampedModel):
    """
    GST-compliant booking invoice for Indian OTA regulations.

    Invoice number format: ZT-YYYYMMDD-XXXXXX (sequential per day)
    Separate customer and supplier invoice numbers for B2B support.

    RULES:
    - Auto-generated on booking confirmation (CONFIRMED status)
    - commission_amount = hotel_amount * commission_pct / 100
    - owner_payout_amount = hotel_amount - commission_amount
    - GST on OTA commission (18% standard B2B rate)
    - Customer pays: final_customer_price (inclusive of all taxes)
    - Owner receives: owner_payout_amount
    """
    INVOICE_DRAFT = 'draft'
    INVOICE_ISSUED = 'issued'
    INVOICE_CANCELLED = 'cancelled'
    INVOICE_AMENDED = 'amended'

    STATUS_CHOICES = [
        (INVOICE_DRAFT, 'Draft'),
        (INVOICE_ISSUED, 'Issued'),
        (INVOICE_CANCELLED, 'Cancelled'),
        (INVOICE_AMENDED, 'Amended'),
    ]

    booking = models.OneToOneField(
        Booking, on_delete=models.PROTECT, related_name='invoice',
    )

    # Invoice identifiers
    invoice_number = models.CharField(
        max_length=50, unique=True,
        help_text='e.g. ZT-20260311-000042'
    )
    supplier_invoice_number = models.CharField(
        max_length=50, blank=True,
        help_text='Supplier/hotel invoice number for B2B settlement'
    )

    # Customer details for GST
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_gstin = models.CharField(
        max_length=15, blank=True,
        help_text='Customer GSTIN for business travel (optional)'
    )
    customer_address = models.TextField(blank=True)

    # Property / Supplier details
    supplier_name = models.CharField(max_length=200, blank=True)
    supplier_gstin = models.CharField(max_length=15, blank=True)
    supplier_address = models.TextField(blank=True)

    # Financial breakdown (all amounts in INR)
    hotel_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Base room + meal charge before any discounts'
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Total discount (promo + property + platform)'
    )
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='OTA commission percentage (e.g. 15.00)'
    )
    commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='OTA commission = hotel_amount * commission_pct / 100'
    )
    commission_gst = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='18% GST on OTA commission (B2B rate)'
    )
    gst_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='GST on accommodation (5% or 18% per slab)'
    )
    gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='GST rate applied (0, 5, or 18)'
    )
    service_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Platform service fee (5%, capped Rs.500)'
    )
    final_customer_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Total amount charged to customer'
    )
    owner_payout_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Amount to be paid to property owner after commission'
    )

    # Invoice metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=INVOICE_DRAFT, db_index=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=200, blank=True)

    # Booking dates snapshot (denormalized for invoice archival)
    booking_date = models.DateField(null=True, blank=True)
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)
    nights = models.PositiveIntegerField(default=1)
    rooms = models.PositiveIntegerField(default=1)
    property_name = models.CharField(max_length=200, blank=True)
    room_type_name = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='inv_status_created_idx'),
            models.Index(fields=['booking'], name='inv_booking_idx'),
            models.Index(fields=['issued_at'], name='inv_issued_idx'),
        ]
        verbose_name = 'Booking Invoice'
        verbose_name_plural = 'Booking Invoices'

    def __str__(self):
        return f"Invoice {self.invoice_number} — {self.booking.public_booking_id}"

    def issue(self):
        """Mark invoice as issued (call after booking confirmed)."""
        from django.utils import timezone
        self.status = self.INVOICE_ISSUED
        self.issued_at = timezone.now()
        self.save(update_fields=['status', 'issued_at', 'updated_at'])
        return self
