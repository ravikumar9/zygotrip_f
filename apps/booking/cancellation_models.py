"""
Phase 4: Cancellation Policy Engine.
Owner-configurable policies with free/partial/non-refundable windows.
"""
from decimal import Decimal
from datetime import datetime, timedelta, timezone as _stdlib_tz
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel


class CancellationPolicy(TimeStampedModel):
    """
    Per-property cancellation policy.
    Defines refund tiers based on hours remaining until check-in.

    Tiers (evaluated in order — first matching window wins):
    1. Free cancellation: full refund if cancelled >= free_cancel_hours before check-in
    2. Partial refund: partial_refund_percent if cancelled >= partial_cancel_hours before check-in
    3. Non-refundable: no refund if cancelled < non_refundable_hours before check-in
    """

    POLICY_TYPE_FLEXIBLE = 'flexible'
    POLICY_TYPE_MODERATE = 'moderate'
    POLICY_TYPE_STRICT = 'strict'
    POLICY_TYPE_NON_REFUNDABLE = 'non_refundable'
    POLICY_TYPE_CUSTOM = 'custom'

    POLICY_TYPE_CHOICES = [
        (POLICY_TYPE_FLEXIBLE, 'Flexible (Free cancel 48h+)'),
        (POLICY_TYPE_MODERATE, 'Moderate (Free cancel 24h+, 50% after)'),
        (POLICY_TYPE_STRICT, 'Strict (50% cancel 7d+, non-refundable after)'),
        (POLICY_TYPE_NON_REFUNDABLE, 'Non-Refundable'),
        (POLICY_TYPE_CUSTOM, 'Custom Policy'),
    ]

    property = models.OneToOneField(
        'hotels.Property',
        on_delete=models.CASCADE,
        related_name='cancellation_policy'
    )
    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPE_CHOICES,
        default=POLICY_TYPE_FLEXIBLE
    )

    # === TIER 1: Free cancellation window ===
    free_cancel_hours = models.PositiveIntegerField(
        default=48,
        help_text="Hours before check-in within which full refund applies. 0 = no free window."
    )

    # === TIER 2: Partial refund window ===
    partial_refund_enabled = models.BooleanField(
        default=True,
        help_text="If True, a partial refund window applies between tiers 1 and 3."
    )
    partial_refund_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        help_text="Percentage of booking value refunded in the partial window."
    )
    partial_cancel_hours = models.PositiveIntegerField(
        default=24,
        help_text="Hours before check-in at which partial refund applies (must be < free_cancel_hours)."
    )

    # === TIER 3: Non-refundable window ===
    non_refundable_hours = models.PositiveIntegerField(
        default=0,
        help_text="Cancellations within this many hours of check-in = 0% refund."
    )

    # === Platform deductions (always withheld) ===
    platform_fee_always_withheld = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.00'),
        help_text="Platform convenience fee % always withheld even in free cancellations."
    )

    display_note = models.CharField(
        max_length=300, blank=True,
        help_text="Human-readable policy summary shown on booking page."
    )

    class Meta:
        app_label = 'booking'

    def __str__(self):
        return f"CancelPolicy({self.property}, {self.policy_type})"

    def get_display_note(self):
        if self.display_note:
            return self.display_note
        if self.policy_type == self.POLICY_TYPE_NON_REFUNDABLE:
            return "Non-refundable — no cancellations allowed."
        if self.free_cancel_hours > 0:
            return (
                f"Free cancellation up to {self.free_cancel_hours}h before check-in. "
                f"Cancel within {self.free_cancel_hours}h: "
                f"{self.partial_refund_percent}% refund."
            )
        return "No free cancellation available."


class RefundCalculator:
    """
    Service class: computes refund amount based on policy + hours until check-in.
    Used by cancellation flow in booking views and Celery tasks.
    """

    def __init__(self, policy: CancellationPolicy, booking_total: Decimal):
        self.policy = policy
        self.booking_total = Decimal(str(booking_total))

    def compute(self, checkin_date) -> dict:
        """
        Returns a dict with:
          - refund_amount: Decimal — amount to return to customer
          - platform_fee: Decimal — amount kept by platform
          - refund_percent: Decimal — percentage refunded
          - tier: str — which refund tier was applied
          - note: str — human-readable explanation
        """
        now = timezone.now()
        if hasattr(checkin_date, 'date'):
            checkin_dt = checkin_date
        else:
            from datetime import datetime as _dt
            checkin_dt = _dt.combine(checkin_date, _dt.min.time()).replace(tzinfo=_stdlib_tz.utc)

        hours_until_checkin = (checkin_dt - now).total_seconds() / 3600
        policy = self.policy
        platform_fee_amount = (self.booking_total * policy.platform_fee_always_withheld / 100).quantize(Decimal('0.01'))

        # Non-refundable policy: always 0 refund
        if policy.policy_type == CancellationPolicy.POLICY_TYPE_NON_REFUNDABLE:
            return self._result(
                refund_amount=Decimal('0.00'),
                platform_fee=platform_fee_amount,
                refund_percent=Decimal('0.00'),
                tier='non_refundable',
                note="Non-refundable booking — no refund applicable."
            )

        # Within non-refundable window
        if hours_until_checkin < policy.non_refundable_hours:
            return self._result(
                refund_amount=Decimal('0.00'),
                platform_fee=platform_fee_amount,
                refund_percent=Decimal('0.00'),
                tier='non_refundable_window',
                note=f"Cancellation within {policy.non_refundable_hours}h of check-in — no refund."
            )

        # TIER 1: Free cancellation
        if hours_until_checkin >= policy.free_cancel_hours and policy.free_cancel_hours > 0:
            gross_refund = self.booking_total - platform_fee_amount
            return self._result(
                refund_amount=max(Decimal('0.00'), gross_refund),
                platform_fee=platform_fee_amount,
                refund_percent=Decimal('100.00') - policy.platform_fee_always_withheld,
                tier='free_cancel',
                note=f"Free cancellation applied — full refund minus {policy.platform_fee_always_withheld}% platform fee."
            )

        # TIER 2: Partial refund
        if policy.partial_refund_enabled and hours_until_checkin >= policy.partial_cancel_hours:
            partial = (self.booking_total * policy.partial_refund_percent / 100).quantize(Decimal('0.01'))
            gross_refund = partial - platform_fee_amount
            return self._result(
                refund_amount=max(Decimal('0.00'), gross_refund),
                platform_fee=platform_fee_amount,
                refund_percent=policy.partial_refund_percent,
                tier='partial',
                note=f"Partial refund — {policy.partial_refund_percent}% of booking value."
            )

        # TIER 3: Non-refundable (catch-all)
        return self._result(
            refund_amount=Decimal('0.00'),
            platform_fee=platform_fee_amount,
            refund_percent=Decimal('0.00'),
            tier='non_refundable',
            note="Cancellation policy window passed — no refund applicable."
        )

    @staticmethod
    def _result(refund_amount, platform_fee, refund_percent, tier, note):
        return {
            'refund_amount': refund_amount,
            'platform_fee': platform_fee,
            'refund_percent': refund_percent,
            'tier': tier,
            'note': note,
        }


# ── Exceptional Case Handling ──────────────────────────────────────────────────


class CancellationException(TimeStampedModel):
    """
    Exceptional overrides for normal cancellation policy.
    Handles force majeure, medical emergencies, duplicate bookings, etc.
    """

    REASON_FORCE_MAJEURE = 'force_majeure'
    REASON_MEDICAL = 'medical'
    REASON_DUPLICATE = 'duplicate'
    REASON_PROPERTY_ISSUE = 'property_issue'
    REASON_PLATFORM_ERROR = 'platform_error'
    REASON_GOODWILL = 'goodwill'

    REASON_CHOICES = [
        (REASON_FORCE_MAJEURE, 'Force Majeure (natural disaster, pandemic, etc.)'),
        (REASON_MEDICAL, 'Medical Emergency'),
        (REASON_DUPLICATE, 'Duplicate Booking'),
        (REASON_PROPERTY_ISSUE, 'Property Issue (overbooking, closure)'),
        (REASON_PLATFORM_ERROR, 'Platform Error'),
        (REASON_GOODWILL, 'Goodwill Gesture'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    booking = models.ForeignKey(
        'booking.Booking', on_delete=models.CASCADE,
        related_name='cancellation_exceptions',
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    evidence_urls = models.JSONField(default=list, blank=True, help_text='List of uploaded evidence URLs')
    override_refund_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.00'),
        help_text='Refund percentage to grant if approved',
    )
    waive_platform_fee = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_exceptions',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']

    def __str__(self):
        return f"CancelException({self.booking_id}, {self.reason}, {self.status})"


class ExceptionalRefundCalculator:
    """
    Computes refund for exceptional cancellation cases.
    Overrides the standard policy when an approved exception exists.
    """

    @staticmethod
    def compute(booking, exception_record=None):
        """
        Check if booking has an approved exception and compute accordingly.
        Falls back to standard RefundCalculator if no exception.
        """
        from apps.booking.cancellation_models import CancellationException

        # Check for approved exception
        if exception_record is None:
            exception_record = CancellationException.objects.filter(
                booking=booking,
                status=CancellationException.STATUS_APPROVED,
            ).first()

        if not exception_record:
            # Fall back to standard policy
            try:
                policy = booking.property.cancellation_policy
            except CancellationPolicy.DoesNotExist:
                # Default flexible policy
                return {
                    'refund_amount': booking.total_amount,
                    'platform_fee': Decimal('0.00'),
                    'refund_percent': Decimal('100.00'),
                    'tier': 'no_policy_default',
                    'note': 'No cancellation policy configured — full refund by default.',
                    'exceptional': False,
                }
            calculator = RefundCalculator(policy, booking.total_amount)
            result = calculator.compute(booking.check_in)
            result['exceptional'] = False
            return result

        # Apply exceptional override
        booking_total = Decimal(str(booking.total_amount))
        refund_pct = exception_record.override_refund_percent
        refund_amount = (booking_total * refund_pct / 100).quantize(Decimal('0.01'))

        if not exception_record.waive_platform_fee:
            try:
                policy = booking.property.cancellation_policy
                platform_fee = (booking_total * policy.platform_fee_always_withheld / 100).quantize(Decimal('0.01'))
            except CancellationPolicy.DoesNotExist:
                platform_fee = Decimal('0.00')
            refund_amount = max(Decimal('0.00'), refund_amount - platform_fee)
        else:
            platform_fee = Decimal('0.00')

        return {
            'refund_amount': refund_amount,
            'platform_fee': platform_fee,
            'refund_percent': refund_pct,
            'tier': 'exceptional',
            'note': f'Exceptional cancellation ({exception_record.get_reason_display()}): '
                    f'{refund_pct}% refund granted.',
            'exceptional': True,
            'exception_reason': exception_record.reason,
        }


# ── Rate Plan Policies (Room-Level) ───────────────────────────────────────────


class RatePlanPolicy(TimeStampedModel):
    """
    Per-room-type rate plan with its own cancellation terms.

    Supports multiple rate plans per room (e.g. "Free Cancellation" at ₹5500
    vs "Non-Refundable" at ₹4200 for the same room type).

    Used by the booking flow to show rate plan options and calculate
    cancellation penalties at the rate-plan level (overrides property-level
    CancellationPolicy when present).
    """

    PLAN_FREE_CANCEL = 'free_cancel'
    PLAN_PARTIAL_REFUND = 'partial_refund'
    PLAN_NON_REFUNDABLE = 'non_refundable'

    PLAN_CHOICES = [
        (PLAN_FREE_CANCEL, 'Free Cancellation'),
        (PLAN_PARTIAL_REFUND, 'Partial Refund'),
        (PLAN_NON_REFUNDABLE, 'Non-Refundable'),
    ]

    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE,
        related_name='rate_plans',
    )
    plan_name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_FREE_CANCEL)

    # Pricing modifier: % adjustment on base price (e.g. -15 for non-refundable discount)
    price_modifier_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Price adjustment vs base rate. Negative = discount (e.g. -15 for non-refundable).',
    )

    # Cancellation terms (override property-level policy)
    free_cancel_hours = models.PositiveIntegerField(
        default=24,
        help_text='Hours before check-in for full refund. 0 for non-refundable plans.',
    )
    partial_refund_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        help_text='Refund % in partial window.',
    )
    partial_cancel_hours = models.PositiveIntegerField(
        default=12,
        help_text='Hours before check-in for partial refund.',
    )

    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'booking'
        ordering = ['display_order', 'plan_type']

    def __str__(self):
        return f"{self.plan_name} ({self.get_plan_type_display()}) — {self.room_type}"

    def get_display_note(self) -> str:
        if self.plan_type == self.PLAN_NON_REFUNDABLE:
            return 'Non-refundable — no cancellation allowed.'
        if self.plan_type == self.PLAN_FREE_CANCEL:
            return f'Free cancellation up to {self.free_cancel_hours}h before check-in.'
        return (
            f'{self.partial_refund_percent}% refund if cancelled '
            f'{self.partial_cancel_hours}h+ before check-in.'
        )


class CancellationPenaltyCalculator:
    """
    Unified penalty calculator supporting both property-level and rate-plan-level policies.

    Usage:
        penalty = CancellationPenaltyCalculator.calculate(booking)
        # Returns: {refund_amount, penalty_amount, refund_percent, tier, note, rate_plan}
    """

    @staticmethod
    def calculate(booking, rate_plan: RatePlanPolicy | None = None) -> dict:
        """
        Calculate cancellation penalty for a booking.

        If a rate_plan is provided (or found on the booking), uses rate-plan-level terms.
        Otherwise falls back to property-level CancellationPolicy.
        """
        booking_total = Decimal(str(booking.total_amount))

        # Try to resolve rate plan from booking metadata
        if rate_plan is None:
            rate_plan_id = getattr(booking, 'rate_plan_id', None)
            if rate_plan_id:
                try:
                    rate_plan = RatePlanPolicy.objects.get(id=rate_plan_id)
                except RatePlanPolicy.DoesNotExist:
                    rate_plan = None

        if rate_plan:
            return CancellationPenaltyCalculator._from_rate_plan(booking, rate_plan, booking_total)

        # Fall back to property-level policy
        try:
            policy = booking.property.cancellation_policy
            calc = RefundCalculator(policy, booking_total)
            result = calc.compute(booking.check_in)
            result['penalty_amount'] = booking_total - result['refund_amount']
            result['rate_plan'] = None
            return result
        except CancellationPolicy.DoesNotExist:
            return {
                'refund_amount': booking_total,
                'penalty_amount': Decimal('0.00'),
                'platform_fee': Decimal('0.00'),
                'refund_percent': Decimal('100.00'),
                'tier': 'no_policy_default',
                'note': 'No cancellation policy — full refund.',
                'rate_plan': None,
            }

    @staticmethod
    def _from_rate_plan(booking, rate_plan: RatePlanPolicy, booking_total: Decimal) -> dict:
        """Calculate penalty using rate-plan-level terms."""
        now = timezone.now()
        checkin_date = booking.check_in
        if hasattr(checkin_date, 'date'):
            checkin_dt = checkin_date
        else:
            checkin_dt = datetime.combine(checkin_date, datetime.min.time()).replace(
                tzinfo=_stdlib_tz.utc
            )

        hours_until = (checkin_dt - now).total_seconds() / 3600
        platform_fee = (booking_total * Decimal('0.02')).quantize(Decimal('0.01'))  # 2% platform fee

        if rate_plan.plan_type == RatePlanPolicy.PLAN_NON_REFUNDABLE:
            return {
                'refund_amount': Decimal('0.00'),
                'penalty_amount': booking_total,
                'platform_fee': platform_fee,
                'refund_percent': Decimal('0.00'),
                'tier': 'non_refundable_plan',
                'note': 'Non-refundable rate plan — no cancellation refund.',
                'rate_plan': rate_plan.plan_name,
            }

        # Free cancellation window
        if hours_until >= rate_plan.free_cancel_hours and rate_plan.free_cancel_hours > 0:
            refund = booking_total - platform_fee
            return {
                'refund_amount': max(Decimal('0.00'), refund),
                'penalty_amount': platform_fee,
                'platform_fee': platform_fee,
                'refund_percent': Decimal('98.00'),
                'tier': 'free_cancel',
                'note': f'Free cancellation applied ({rate_plan.plan_name}).',
                'rate_plan': rate_plan.plan_name,
            }

        # Partial refund window
        if hours_until >= rate_plan.partial_cancel_hours:
            partial = (booking_total * rate_plan.partial_refund_percent / 100).quantize(Decimal('0.01'))
            refund = partial - platform_fee
            return {
                'refund_amount': max(Decimal('0.00'), refund),
                'penalty_amount': booking_total - max(Decimal('0.00'), refund),
                'platform_fee': platform_fee,
                'refund_percent': rate_plan.partial_refund_percent,
                'tier': 'partial',
                'note': f'{rate_plan.partial_refund_percent}% refund ({rate_plan.plan_name}).',
                'rate_plan': rate_plan.plan_name,
            }

        # Past all windows
        return {
            'refund_amount': Decimal('0.00'),
            'penalty_amount': booking_total,
            'platform_fee': platform_fee,
            'refund_percent': Decimal('0.00'),
            'tier': 'no_refund',
            'note': f'Cancellation past all refund windows ({rate_plan.plan_name}).',
            'rate_plan': rate_plan.plan_name,
        }
