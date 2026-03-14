"""
Hotel Rate Plan & Cancellation Policy Engine.

Supports OTA-standard rate plans:
- Refundable / Non-refundable
- Breakfast included / Room only
- Long stay discounts
- Corporate rates

Cancellation policies with date-based penalty tiers.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.hotels')


class RatePlan(TimeStampedModel):
    """
    Rate plan defines pricing rules and conditions for a room type.
    Each room type can have multiple rate plans (refundable, non-refundable, etc.).
    """
    PLAN_STANDARD = 'standard'
    PLAN_NON_REFUNDABLE = 'non_refundable'
    PLAN_BREAKFAST = 'breakfast_included'
    PLAN_HALF_BOARD = 'half_board'
    PLAN_FULL_BOARD = 'full_board'
    PLAN_CORPORATE = 'corporate'
    PLAN_LONG_STAY = 'long_stay'
    PLAN_MEMBER = 'member'

    PLAN_TYPE_CHOICES = [
        (PLAN_STANDARD, 'Standard (Refundable)'),
        (PLAN_NON_REFUNDABLE, 'Non-Refundable'),
        (PLAN_BREAKFAST, 'Breakfast Included'),
        (PLAN_HALF_BOARD, 'Half Board (B+D)'),
        (PLAN_FULL_BOARD, 'Full Board (B+L+D)'),
        (PLAN_CORPORATE, 'Corporate Rate'),
        (PLAN_LONG_STAY, 'Long Stay Discount'),
        (PLAN_MEMBER, 'Member Exclusive'),
    ]

    room_type = models.ForeignKey(
        'rooms.RoomType', on_delete=models.CASCADE, related_name='hotel_rate_plans',
    )
    plan_type = models.CharField(max_length=30, choices=PLAN_TYPE_CHOICES, default=PLAN_STANDARD)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    # Pricing
    price_modifier_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        help_text='% adjustment from base price. -15 = 15% discount, +20 = 20% surcharge',
    )
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Override price per night (ignores modifier if set)',
    )

    # Conditions
    is_refundable = models.BooleanField(default=True)
    includes_breakfast = models.BooleanField(default=False)
    includes_lunch = models.BooleanField(default=False)
    includes_dinner = models.BooleanField(default=False)

    # Booking constraints
    min_nights = models.PositiveIntegerField(default=1)
    max_nights = models.PositiveIntegerField(default=365)
    min_advance_days = models.PositiveIntegerField(
        default=0, help_text='Minimum days before check-in to book this plan',
    )
    max_advance_days = models.PositiveIntegerField(
        default=365, help_text='Maximum days before check-in to book this plan',
    )

    # Payment
    pay_at_hotel = models.BooleanField(default=False)
    prepayment_required = models.BooleanField(default=True)

    # Cancellation link
    cancellation_policy = models.ForeignKey(
        'hotels.CancellationPolicy', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rate_plans',
    )

    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'hotels'
        ordering = ['sort_order', 'price_modifier_percent']
        indexes = [
            models.Index(fields=['room_type', 'is_active'], name='rateplan_room_active_idx'),
            models.Index(fields=['plan_type', 'is_active'], name='rateplan_type_active_idx'),
        ]

    def __str__(self):
        return f"{self.room_type.name} - {self.name}"

    def calculate_price(self, base_price, nights=1):
        """Calculate price for this rate plan."""
        if self.price_override is not None:
            nightly = self.price_override
        else:
            modifier = Decimal('1') + (self.price_modifier_percent / Decimal('100'))
            nightly = base_price * modifier
        return max(nightly * nights, Decimal('0'))

    def is_available_for_dates(self, check_in, check_out):
        """Check if this rate plan is bookable for given dates."""
        if not self.is_active:
            return False
        nights = (check_out - check_in).days
        if nights < self.min_nights or nights > self.max_nights:
            return False
        days_ahead = (check_in - date.today()).days
        if days_ahead < self.min_advance_days or days_ahead > self.max_advance_days:
            return False
        return True


class CancellationPolicy(TimeStampedModel):
    """
    Named cancellation policy that can be attached to rate plans.
    Supports multiple time-based penalty tiers.
    """
    POLICY_FREE = 'free'
    POLICY_MODERATE = 'moderate'
    POLICY_STRICT = 'strict'
    POLICY_NON_REFUNDABLE = 'non_refundable'
    POLICY_CUSTOM = 'custom'

    POLICY_TYPE_CHOICES = [
        (POLICY_FREE, 'Free Cancellation'),
        (POLICY_MODERATE, 'Moderate'),
        (POLICY_STRICT, 'Strict'),
        (POLICY_NON_REFUNDABLE, 'Non-Refundable'),
        (POLICY_CUSTOM, 'Custom'),
    ]

    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='cancellation_policies',
    )
    name = models.CharField(max_length=150)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES, default=POLICY_MODERATE)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False, help_text='Default policy for this property',
    )

    class Meta:
        app_label = 'hotels'
        verbose_name_plural = 'Cancellation Policies'

    def __str__(self):
        return f"{self.property.name} - {self.name}"

    def calculate_refund(self, total_amount, check_in_date):
        """
        Calculate refund amount based on time until check-in.
        Returns (refund_amount, penalty_amount, tier_applied).
        """
        now = timezone.now()
        checkin_dt = timezone.make_aware(
            timezone.datetime.combine(check_in_date, timezone.datetime.min.time())
        )
        hours_until = max(0, (checkin_dt - now).total_seconds() / 3600)

        # Get applicable tier (ordered by hours descending — most generous first)
        tiers = self.tiers.filter(is_active=True).order_by('-hours_before_checkin')

        for tier in tiers:
            if hours_until >= tier.hours_before_checkin:
                refund = total_amount * (tier.refund_percentage / Decimal('100'))
                penalty = total_amount - refund
                return refund, penalty, tier.name

        # No tier matched — no refund (too close to check-in)
        return Decimal('0'), total_amount, 'No refund (past deadline)'


class CancellationTier(TimeStampedModel):
    """
    Time-based cancellation penalty tier.
    Example: Cancel 72h+ before → 100% refund, 24-72h → 50%, <24h → 0%.
    """
    policy = models.ForeignKey(
        CancellationPolicy, on_delete=models.CASCADE, related_name='tiers',
    )
    name = models.CharField(max_length=100, help_text='e.g. "Free cancellation", "50% refund"')
    hours_before_checkin = models.PositiveIntegerField(
        help_text='Minimum hours before check-in for this tier to apply',
    )
    refund_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Refund percentage (0-100)',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'hotels'
        ordering = ['-hours_before_checkin']
        unique_together = ['policy', 'hours_before_checkin']

    def __str__(self):
        return f"{self.policy.name}: {self.hours_before_checkin}h+ → {self.refund_percentage}%"


def get_rate_plans_for_room(room_type, check_in=None, check_out=None):
    """Get available rate plans for a room type, optionally filtered by dates."""
    plans = RatePlan.objects.filter(room_type=room_type, is_active=True)

    if check_in and check_out:
        result = []
        for plan in plans:
            if plan.is_available_for_dates(check_in, check_out):
                nights = (check_out - check_in).days
                price = plan.calculate_price(room_type.base_price, nights)
                result.append({
                    'plan': plan,
                    'total_price': price,
                    'nightly_price': plan.calculate_price(room_type.base_price, 1),
                    'nights': nights,
                    'is_refundable': plan.is_refundable,
                    'includes_breakfast': plan.includes_breakfast,
                    'cancellation_policy': plan.cancellation_policy,
                })
        return sorted(result, key=lambda x: x['total_price'])

    return plans.select_related('cancellation_policy')


def get_cheapest_rate(room_type, check_in, check_out):
    """Get the cheapest available rate for a room type and date range."""
    plans = get_rate_plans_for_room(room_type, check_in, check_out)
    if plans:
        return plans[0]
    # Fallback to base price
    nights = (check_out - check_in).days
    return {
        'plan': None,
        'total_price': room_type.base_price * nights,
        'nightly_price': room_type.base_price,
        'nights': nights,
        'is_refundable': True,
        'includes_breakfast': False,
        'cancellation_policy': None,
    }
