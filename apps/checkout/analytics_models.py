"""
Booking Analytics — Funnel Tracking + Conversion Rate Analysis.

Tracks every step of the booking funnel:
  search_view → hotel_click → room_select → checkout_start
  → payment_start → booking_success → booking_cancel

Used for:
  - Conversion rate dashboards
  - Drop-off analysis
  - A/B testing metrics
  - Revenue attribution
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class BookingAnalytics(TimeStampedModel):
    """
    Individual funnel event tracking.
    One row per event per session.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Event type
    EVENT_SEARCH_VIEW = 'search_view'
    EVENT_HOTEL_CLICK = 'hotel_click'
    EVENT_ROOM_SELECT = 'room_select'
    EVENT_CHECKOUT_START = 'checkout_start'
    EVENT_GUEST_DETAILS = 'guest_details'
    EVENT_PAYMENT_START = 'payment_start'
    EVENT_PAYMENT_SUCCESS = 'payment_success'
    EVENT_PAYMENT_FAILED = 'payment_failed'
    EVENT_BOOKING_SUCCESS = 'booking_success'
    EVENT_BOOKING_CANCEL = 'booking_cancel'

    EVENT_CHOICES = [
        (EVENT_SEARCH_VIEW, 'Search View'),
        (EVENT_HOTEL_CLICK, 'Hotel Click'),
        (EVENT_ROOM_SELECT, 'Room Select'),
        (EVENT_CHECKOUT_START, 'Checkout Start'),
        (EVENT_GUEST_DETAILS, 'Guest Details'),
        (EVENT_PAYMENT_START, 'Payment Start'),
        (EVENT_PAYMENT_SUCCESS, 'Payment Success'),
        (EVENT_PAYMENT_FAILED, 'Payment Failed'),
        (EVENT_BOOKING_SUCCESS, 'Booking Success'),
        (EVENT_BOOKING_CANCEL, 'Booking Cancel'),
    ]

    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    event_timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # Session tracking
    session_id = models.CharField(
        max_length=64, db_index=True,
        help_text='Browser/app session identifier',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='booking_analytics',
    )

    # Context references
    property_id = models.IntegerField(null=True, blank=True, db_index=True)
    room_type_id = models.IntegerField(null=True, blank=True)
    booking_session_id = models.UUIDField(null=True, blank=True, db_index=True)
    booking_id = models.UUIDField(null=True, blank=True)

    # Search context
    search_city = models.CharField(max_length=100, blank=True)
    search_checkin = models.DateField(null=True, blank=True)
    search_checkout = models.DateField(null=True, blank=True)
    search_guests = models.PositiveIntegerField(null=True, blank=True)
    search_rooms = models.PositiveIntegerField(null=True, blank=True)

    # Revenue data (for conversion events)
    revenue_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )

    # Device / attribution
    device_type = models.CharField(max_length=20, blank=True)  # mobile, desktop, tablet
    traffic_source = models.CharField(max_length=100, blank=True)  # google, direct, meta
    campaign_id = models.CharField(max_length=100, blank=True)

    # Extra metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'checkout'
        ordering = ['-event_timestamp']
        indexes = [
            models.Index(fields=['event_type', '-event_timestamp'], name='ba_event_time_idx'),
            models.Index(fields=['session_id', 'event_type'], name='ba_session_event_idx'),
            models.Index(fields=['property_id', 'event_type', '-event_timestamp'], name='ba_prop_event_idx'),
            models.Index(fields=['user', '-event_timestamp'], name='ba_user_time_idx'),
            models.Index(fields=['-event_timestamp'], name='ba_time_idx'),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.event_timestamp}"


class FunnelConversionDaily(TimeStampedModel):
    """
    Pre-aggregated daily funnel conversion metrics.
    Populated by background job from BookingAnalytics events.
    """

    date = models.DateField(db_index=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)

    # Funnel counts
    search_views = models.IntegerField(default=0)
    hotel_clicks = models.IntegerField(default=0)
    room_selects = models.IntegerField(default=0)
    checkout_starts = models.IntegerField(default=0)
    payment_starts = models.IntegerField(default=0)
    payment_successes = models.IntegerField(default=0)
    booking_successes = models.IntegerField(default=0)
    booking_cancels = models.IntegerField(default=0)

    # Conversion rates (precomputed)
    search_to_click_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    click_to_checkout_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    checkout_to_payment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    payment_to_booking_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Revenue
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    avg_booking_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        app_label = 'checkout'
        unique_together = ('date', 'city')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date', 'city'], name='fcd_date_city_idx'),
        ]

    def __str__(self):
        return f"Funnel({self.date}, {self.city or 'ALL'})"


# ============================================================================
# FRAUD PROTECTION
# ============================================================================

class BookingRiskScore(TimeStampedModel):
    """
    Risk assessment for each booking session.
    Computed at checkout start and updated during payment.

    Score 0-100:
      0-30:   Low risk (auto-approve)
      31-60:  Medium risk (flag for review)
      61-80:  High risk (require additional verification)
      81-100: Critical (auto-reject)
    """

    risk_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Session/booking references
    booking_session = models.OneToOneField(
        'checkout.BookingSession', on_delete=models.CASCADE,
        null=True, blank=True, related_name='risk_score',
    )
    booking = models.OneToOneField(
        'booking.Booking', on_delete=models.CASCADE,
        null=True, blank=True, related_name='risk_score',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='risk_scores',
    )

    # Overall score
    risk_score = models.IntegerField(default=0, db_index=True)
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Risk'),
        ],
        default='low', db_index=True,
    )

    # Individual risk factors (0-100 each)
    ip_risk = models.IntegerField(default=0, help_text='Risk from IP analysis')
    device_risk = models.IntegerField(default=0, help_text='Risk from device fingerprint')
    velocity_risk = models.IntegerField(default=0, help_text='Risk from booking frequency')
    payment_risk = models.IntegerField(default=0, help_text='Risk from payment pattern')
    location_risk = models.IntegerField(default=0, help_text='Risk from geo mismatch')

    # Raw signals
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.CharField(max_length=64, blank=True)
    ip_country = models.CharField(max_length=3, blank=True)
    ip_is_vpn = models.BooleanField(default=False)
    ip_is_proxy = models.BooleanField(default=False)

    # Velocity signals
    bookings_last_hour = models.IntegerField(default=0)
    bookings_last_day = models.IntegerField(default=0)
    payment_attempts_last_hour = models.IntegerField(default=0)
    failed_payments_last_day = models.IntegerField(default=0)

    # Location signals
    billing_country = models.CharField(max_length=3, blank=True)
    hotel_country = models.CharField(max_length=3, blank=True)
    location_mismatch = models.BooleanField(default=False)

    # Outcome
    action_taken = models.CharField(
        max_length=20,
        choices=[
            ('approved', 'Auto-Approved'),
            ('flagged', 'Flagged for Review'),
            ('blocked', 'Blocked'),
            ('manual_approved', 'Manually Approved'),
            ('manual_rejected', 'Manually Rejected'),
        ],
        default='approved', db_index=True,
    )
    review_notes = models.TextField(blank=True)

    # Detailed risk breakdown
    risk_factors = models.JSONField(
        default=dict, blank=True,
        help_text='Detailed risk factor breakdown with explanations',
    )

    class Meta:
        app_label = 'checkout'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['risk_level', '-created_at'], name='brs_level_idx'),
            models.Index(fields=['ip_address'], name='brs_ip_idx'),
            models.Index(fields=['user', '-created_at'], name='brs_user_idx'),
            models.Index(fields=['action_taken', '-created_at'], name='brs_action_idx'),
        ]

    def __str__(self):
        return f"Risk({self.risk_score}, {self.risk_level}, {self.action_taken})"

    def compute_risk_level(self):
        """Compute risk level from score."""
        if self.risk_score <= 30:
            self.risk_level = 'low'
        elif self.risk_score <= 60:
            self.risk_level = 'medium'
        elif self.risk_score <= 80:
            self.risk_level = 'high'
        else:
            self.risk_level = 'critical'
        return self.risk_level
