"""
Production Checkout Architecture — BookingSession + PaymentIntent System.

This module extends the existing BookingContext with a formal checkout session
lifecycle and adds PaymentIntent/PaymentAttempt/PaymentWebhook models for
production-grade payment safety.

BookingSession Lifecycle:
  SEARCH → ROOM_SELECTED → SESSION_CREATED → GUEST_DETAILS
  → PAYMENT_INITIATED → PAYMENT_PROCESSING → BOOKING_CONFIRMED

PaymentIntent → PaymentAttempt → PaymentWebhook flow ensures:
  - No duplicate payments (idempotency)
  - No stale price payments (revalidation)
  - Safe retries (attempt tracking)
  - Webhook reconciliation
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


# ============================================================================
# BOOKING SESSION (extends BookingContext with formal lifecycle)
# ============================================================================

class BookingSession(TimeStampedModel):
    """
    Dedicated checkout session — created when user selects a room.
    Booking is NOT created until payment succeeds.

    Links to existing BookingContext for price-lock + search snapshot,
    and to InventoryToken for inventory reservation.
    """

    # Session identity
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='booking_sessions',
    )
    session_key = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text='Anonymous browser session key for guest checkout ownership',
    )

    # Property + room selection
    hotel = models.ForeignKey(
        'hotels.Property', on_delete=models.PROTECT,
        related_name='booking_sessions',
    )
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.PROTECT,
        related_name='booking_sessions',
    )
    rate_plan_id = models.CharField(
        max_length=100, blank=True,
        help_text='External rate plan identifier (from supplier or internal)',
    )

    # Search context snapshot (immutable after creation)
    search_snapshot = models.JSONField(
        default=dict, blank=True,
        help_text='Frozen search parameters: city, dates, guests, filters',
    )

    # Price snapshot (revalidated before payment)
    price_snapshot = models.JSONField(
        default=dict, blank=True,
        help_text='Frozen price breakdown: base, meals, tax, service_fee, total',
    )
    price_revalidated_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Last time price was revalidated against pricing engine',
    )
    price_changed = models.BooleanField(
        default=False,
        help_text='True if price changed during revalidation',
    )

    # Inventory reservation
    inventory_token = models.OneToOneField(
        'checkout.InventoryToken', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='booking_session',
        help_text='Active inventory reservation for this session',
    )

    # Guest details (populated during checkout)
    guest_details = models.JSONField(
        default=dict, blank=True,
        help_text='Guest info: name, email, phone, special_requests',
    )

    # Link to existing BookingContext (for backward compatibility)
    booking_context = models.OneToOneField(
        'booking.BookingContext', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checkout_session',
    )

    # Link to final Booking (set after payment success)
    booking = models.OneToOneField(
        'booking.Booking', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checkout_session',
    )

    # Session lifecycle
    STATUS_CREATED = 'created'
    STATUS_ROOM_SELECTED = 'room_selected'
    STATUS_GUEST_DETAILS = 'guest_details'
    STATUS_PAYMENT_INITIATED = 'payment_initiated'
    STATUS_PAYMENT_PROCESSING = 'payment_processing'
    STATUS_COMPLETED = 'completed'
    STATUS_EXPIRED = 'expired'
    STATUS_ABANDONED = 'abandoned'
    STATUS_FAILED = 'failed'

    SESSION_STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_ROOM_SELECTED, 'Room Selected'),
        (STATUS_GUEST_DETAILS, 'Guest Details Provided'),
        (STATUS_PAYMENT_INITIATED, 'Payment Initiated'),
        (STATUS_PAYMENT_PROCESSING, 'Payment Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ABANDONED, 'Abandoned'),
        (STATUS_FAILED, 'Failed'),
    ]

    VALID_TRANSITIONS = {
        STATUS_CREATED: [STATUS_ROOM_SELECTED, STATUS_EXPIRED, STATUS_ABANDONED],
        STATUS_ROOM_SELECTED: [STATUS_GUEST_DETAILS, STATUS_EXPIRED, STATUS_ABANDONED],
        STATUS_GUEST_DETAILS: [STATUS_PAYMENT_INITIATED, STATUS_EXPIRED, STATUS_ABANDONED],
        STATUS_PAYMENT_INITIATED: [STATUS_PAYMENT_PROCESSING, STATUS_FAILED, STATUS_EXPIRED],
        STATUS_PAYMENT_PROCESSING: [STATUS_COMPLETED, STATUS_FAILED, STATUS_EXPIRED],
        STATUS_COMPLETED: [],  # terminal
        STATUS_EXPIRED: [],    # terminal
        STATUS_ABANDONED: [],  # terminal
        STATUS_FAILED: [STATUS_PAYMENT_INITIATED],  # allow retry
    }

    session_status = models.CharField(
        max_length=30, choices=SESSION_STATUS_CHOICES,
        default=STATUS_CREATED, db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)

    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'session_status'], name='bs_user_status_idx'),
            models.Index(fields=['session_key', 'session_status'], name='bs_session_status_idx'),
            models.Index(fields=['session_status', 'expires_at'], name='bs_status_exp_idx'),
            models.Index(fields=['hotel', '-created_at'], name='bs_prop_created_idx'),
        ]

    def __str__(self):
        return f"Session({self.session_id}, {self.session_status})"

    def transition_to(self, new_status):
        """Validate and apply state transition."""
        allowed = self.VALID_TRANSITIONS.get(self.session_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.session_status} → {new_status}. "
                f"Allowed: {allowed}"
            )
        self.session_status = new_status
        self.save(update_fields=['session_status', 'updated_at'])
        return self

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def total_amount(self):
        """Extract total from price snapshot."""
        return Decimal(str(self.price_snapshot.get('total', 0)))


# ============================================================================
# INVENTORY TOKEN (formal inventory reservation)
# ============================================================================

class InventoryToken(TimeStampedModel):
    """
    Formal inventory reservation token.
    Links to existing InventoryHold records for actual date-level holds.

    Guarantees:
      - Inventory is reserved when token is active
      - Token expires automatically if checkout not completed
      - One token per booking session
    """

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    hotel = models.ForeignKey(
        'hotels.Property', on_delete=models.PROTECT,
        related_name='inventory_tokens',
    )
    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.PROTECT,
        related_name='inventory_tokens',
    )
    rate_plan_id = models.CharField(max_length=100, blank=True)

    # Date range for reservation
    date_start = models.DateField()
    date_end = models.DateField()
    reserved_rooms = models.PositiveIntegerField(default=1)

    # Token lifecycle
    STATUS_ACTIVE = 'active'
    STATUS_PAYMENT_PENDING = 'payment_pending'
    STATUS_CONVERTED = 'converted'
    STATUS_EXPIRED = 'expired'
    STATUS_RELEASED = 'released'

    TOKEN_STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAYMENT_PENDING, 'Payment Pending'),
        (STATUS_CONVERTED, 'Converted to Booking'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_RELEASED, 'Released'),
    ]

    token_status = models.CharField(
        max_length=20, choices=TOKEN_STATUS_CHOICES,
        default=STATUS_ACTIVE, db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)

    # Link to existing InventoryHold records
    hold_ids = models.JSONField(
        default=list, blank=True,
        help_text='List of InventoryHold IDs managed by this token',
    )

    class Meta:
        app_label = 'checkout'
        indexes = [
            models.Index(fields=['token_status', 'expires_at'], name='it_status_exp_idx'),
            models.Index(fields=['room_type', 'date_start', 'date_end'], name='it_room_dates_idx'),
        ]

    def __str__(self):
        return f"InvToken({self.token_id}, {self.token_status})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


# ============================================================================
# PAYMENT INTENT (replaces direct booking → payment)
# ============================================================================

class PaymentIntent(TimeStampedModel):
    """
    Payment intent for a booking session.
    Created when user initiates payment. Ensures:
      - Price is revalidated before payment
      - Multiple payment attempts are tracked
      - Idempotency prevents duplicate bookings
    """

    intent_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    booking_session = models.ForeignKey(
        BookingSession, on_delete=models.PROTECT,
        related_name='payment_intents',
    )
    idempotency_key = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True,
        help_text='Client-generated key to prevent duplicate intent creation',
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')

    # Price revalidation
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Amount at session creation (before revalidation)',
    )
    price_revalidated = models.BooleanField(default=False)
    price_delta = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Difference between original and revalidated price',
    )

    # Intent lifecycle
    STATUS_CREATED = 'created'
    STATUS_PROCESSING = 'processing'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    INTENT_STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    payment_status = models.CharField(
        max_length=20, choices=INTENT_STATUS_CHOICES,
        default=STATUS_CREATED, db_index=True,
    )

    # Link to existing PaymentTransaction (for backward compatibility)
    payment_transaction = models.OneToOneField(
        'payments.PaymentTransaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_intent',
    )

    # Link to final Booking (set after success)
    booking = models.ForeignKey(
        'booking.Booking', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_intents',
    )

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_status', '-created_at'], name='pi_status_idx'),
            models.Index(fields=['booking_session', 'payment_status'], name='pi_session_idx'),
        ]

    def __str__(self):
        return f"Intent({self.intent_id}, ₹{self.amount}, {self.payment_status})"


class PaymentAttempt(TimeStampedModel):
    """
    Individual payment attempt within an intent.
    Tracks each gateway interaction separately.
    """

    attempt_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    payment_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.CASCADE,
        related_name='attempts',
    )

    gateway = models.CharField(max_length=30, db_index=True)
    gateway_order_id = models.CharField(max_length=200, blank=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    STATUS_INITIATED = 'initiated'
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_TIMEOUT = 'timeout'

    ATTEMPT_STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    attempt_status = models.CharField(
        max_length=20, choices=ATTEMPT_STATUS_CHOICES,
        default=STATUS_INITIATED, db_index=True,
    )
    failure_reason = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']

    def __str__(self):
        return f"Attempt({self.attempt_id}, {self.gateway}, {self.attempt_status})"


class PaymentWebhook(TimeStampedModel):
    """
    Raw webhook event log from payment gateways.
    Stored for reconciliation and audit.
    """

    webhook_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    gateway = models.CharField(max_length=30, db_index=True)
    event_type = models.CharField(max_length=100, blank=True, db_index=True)
    payload = models.JSONField()
    headers = models.JSONField(default=dict, blank=True)

    # Processing
    STATUS_RECEIVED = 'received'
    STATUS_PROCESSED = 'processed'
    STATUS_FAILED = 'failed'
    STATUS_DUPLICATE = 'duplicate'

    WEBHOOK_STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DUPLICATE, 'Duplicate'),
    ]

    processed_status = models.CharField(
        max_length=20, choices=WEBHOOK_STATUS_CHOICES,
        default=STATUS_RECEIVED, db_index=True,
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    # Linked records
    payment_attempt = models.ForeignKey(
        PaymentAttempt, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='webhooks',
    )
    payment_transaction = models.ForeignKey(
        'payments.PaymentTransaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='webhook_events',
    )

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gateway', 'processed_status'], name='pw_gw_status_idx'),
            models.Index(fields=['event_type', '-created_at'], name='pw_event_idx'),
        ]

    def __str__(self):
        return f"Webhook({self.webhook_id}, {self.gateway}, {self.processed_status})"


# Import analytics & fraud models for Django migration discovery
from .analytics_models import BookingAnalytics, FunnelConversionDaily, BookingRiskScore  # noqa: F401, E402

# Import travel bundle & cart models for migration discovery
from .travel_bundle import TravelBundle, BundleItem, Cart, CartItem  # noqa: F401, E402
