"""
Pricing models — OTA Freeze Grade.

Phase 4: Consolidated pricing with seasonal/weekend/event modifiers and tax rules.
CompetitorPrice kept for price intelligence.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel
from apps.pricing.discount_engine import PropertyDiscount  # noqa: F401


class CompetitorPrice(models.Model):
    """
    Competitor price snapshot for a property on a given date.

    Populated by the daily price intelligence job (management command:
    update_competitor_prices). Used by GET /api/v1/pricing/intelligence/<property_uuid>/.

    RULES:
    - One row per (property, competitor_name, date)
    - price_per_night is the competitor's advertised rate (INR)
    - source is the platform name (e.g. 'booking.com', 'makemytrip', 'goibibo')
    - fetched_at records when this data was last updated
    """
    property = models.ForeignKey(
        'hotels.Property',
        on_delete=models.PROTECT,
        related_name='competitor_prices',
    )
    competitor_name = models.CharField(
        max_length=100,
        help_text="Competitor platform name (e.g. 'Booking.com', 'MakeMyTrip')",
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source URL or platform identifier",
    )
    price_per_night = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Competitor's advertised price per night (INR)",
    )
    date = models.DateField(
        help_text="Date for which this price applies",
    )
    fetched_at = models.DateTimeField(default=timezone.now)
    is_available = models.BooleanField(
        default=True,
        help_text="Whether the competitor has availability for this date",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'pricing'
        unique_together = ('property', 'competitor_name', 'date')
        indexes = [
            models.Index(fields=['property', 'date']),
            models.Index(fields=['date', 'competitor_name']),
        ]
        ordering = ['date', 'competitor_name']

    def __str__(self):
        return f"{self.competitor_name} @ {self.property} on {self.date}: ₹{self.price_per_night}"


# ============================================================================
# PHASE 4: SEASONAL / WEEKEND / EVENT MODIFIERS
# ============================================================================

class SeasonalPricing(TimeStampedModel):
    """
    Seasonal rate modifier for a property.
    Applies a multiplier to base_price during a date range.
    e.g., Peak season (Dec 20 – Jan 5) → 1.5x multiplier.
    """
    SEASON_PEAK = 'peak'
    SEASON_HIGH = 'high'
    SEASON_SHOULDER = 'shoulder'
    SEASON_LOW = 'low'

    SEASON_CHOICES = [
        (SEASON_PEAK, 'Peak Season'),
        (SEASON_HIGH, 'High Season'),
        (SEASON_SHOULDER, 'Shoulder Season'),
        (SEASON_LOW, 'Low Season'),
    ]

    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='seasonal_pricing',
    )
    name = models.CharField(max_length=100, help_text="e.g., Christmas Peak, Diwali Rush")
    season_type = models.CharField(max_length=20, choices=SEASON_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1,
        help_text="Price multiplier (1.0 = no change, 1.5 = 50% increase, 0.8 = 20% discount)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'pricing'
        ordering = ['start_date']
        indexes = [
            models.Index(fields=['property', 'start_date', 'end_date']),
            models.Index(fields=['is_active', 'start_date']),
        ]

    def __str__(self):
        return f"{self.name} ({self.property.name}): {self.multiplier}x"


class WeekendPricing(TimeStampedModel):
    """
    Weekend/weekday rate modifier per property.
    Applies to Friday+Saturday (configurable) when no seasonal rate exists.
    """
    property = models.OneToOneField(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='weekend_pricing',
    )
    weekend_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1,
        help_text="Multiplier for weekend nights (1.2 = 20% extra)",
    )
    # Which days count as "weekend" (JSON array of isoweekday: Mon=1...Sun=7)
    weekend_days = models.JSONField(
        default=list,
        help_text="ISO weekday numbers considered weekend, e.g. [5, 6] for Fri+Sat",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'pricing'

    def __str__(self):
        return f"Weekend pricing for {self.property.name}: {self.weekend_multiplier}x"

    def save(self, *args, **kwargs):
        if not self.weekend_days:
            self.weekend_days = [5, 6]  # Default: Fri + Sat
        super().save(*args, **kwargs)


class EventPricing(TimeStampedModel):
    """
    Event-based pricing for specific dates (festivals, concerts, etc.).
    Takes priority over seasonal pricing.
    """
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='event_pricing',
    )
    event_name = models.CharField(max_length=200, help_text="e.g., Diwali, IPL Final, New Year")
    date = models.DateField()
    multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1,
        help_text="Price multiplier for this event date",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'pricing'
        unique_together = ('property', 'date')
        indexes = [
            models.Index(fields=['property', 'date']),
            models.Index(fields=['date', 'is_active']),
        ]

    def __str__(self):
        return f"{self.event_name} @ {self.property.name} {self.date}: {self.multiplier}x"


class TaxRule(TimeStampedModel):
    """
    Tax configuration — supports multiple tax regimes.
    Currently: Indian GST slabs for accommodation.
    """
    name = models.CharField(max_length=100, unique=True, help_text="e.g., GST 5%, GST 18%")
    threshold_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Minimum per-night tariff for this slab (inclusive)",
    )
    threshold_max = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Maximum per-night tariff for this slab (inclusive). NULL = no upper bound.",
    )
    rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0.05,
        help_text="Tax rate as decimal (0.05 = 5%, 0.18 = 18%)",
    )
    is_active = models.BooleanField(default=True)
    country = models.CharField(max_length=50, default='IN')

    class Meta:
        app_label = 'pricing'
        ordering = ['threshold_min']

    def __str__(self):
        return f"{self.name}: {self.rate * 100}% (₹{self.threshold_min}–₹{self.threshold_max or '∞'})"


# ============================================================================
# PHASE 5: LENGTH OF STAY (LOS) PRICING
# ============================================================================

class LOSPricing(TimeStampedModel):
    """
    Length-of-Stay pricing — discount/surcharge based on booking duration.

    Incentivizes longer stays with progressive discounts:
      - 3+ nights → 5% off
      - 7+ nights → 10% off
      - 14+ nights → 15% off
      - 30+ nights → 20% off (monthly rate)

    Per-property configuration. Multiplier < 1.0 = discount, > 1.0 = surcharge.
    """
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='los_pricing',
    )
    min_nights = models.PositiveIntegerField(
        help_text="Minimum nights for this LOS tier (inclusive)",
    )
    max_nights = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maximum nights for this LOS tier (inclusive). NULL = unlimited.",
    )
    multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1,
        help_text="Price multiplier (0.90 = 10% discount, 1.0 = no change)",
    )
    label = models.CharField(
        max_length=100, blank=True,
        help_text="Display label e.g. 'Weekly Discount', 'Monthly Rate'",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'pricing'
        ordering = ['property', 'min_nights']
        indexes = [
            models.Index(fields=['property', 'min_nights', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_nights__gte=1),
                name='los_min_nights_positive',
            ),
        ]

    def __str__(self):
        max_str = f'–{self.max_nights}' if self.max_nights else '+'
        return f"LOS {self.property.name}: {self.min_nights}{max_str} nights → {self.multiplier}x"


# ============================================================================
# PHASE 5: CHILD / EXTRA GUEST PRICING
# ============================================================================

class OccupancyPricing(TimeStampedModel):
    """
    Per-room-type occupancy-based pricing for extra adults, children, and infants.

    OTA pricing model:
      - base_occupancy: number of guests included in base rate (default 2)
      - extra_adult_charge: per night per extra adult beyond base_occupancy
      - child_charge: per night per child (age 5-12) — 0 = free
      - infant_charge: per night per infant (age 0-5) — typically 0
      - max_occupancy: hard cap on guests per room

    Used in pricing pipeline step between base price and property discount.
    """
    room_type = models.OneToOneField(
        'rooms.RoomType', on_delete=models.CASCADE,
        related_name='occupancy_pricing',
    )
    base_occupancy = models.PositiveIntegerField(
        default=2,
        help_text="Number of adults included in base room rate",
    )
    max_occupancy = models.PositiveIntegerField(
        default=3,
        help_text="Maximum total guests (adults + children) per room",
    )
    max_children = models.PositiveIntegerField(
        default=2,
        help_text="Maximum children allowed per room",
    )
    extra_adult_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Charge per extra adult per night (INR)",
    )
    child_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Charge per child (age 5-12) per night (INR). 0 = free.",
    )
    infant_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Charge per infant (age 0-5) per night (INR). Usually 0.",
    )
    child_age_min = models.PositiveIntegerField(
        default=5, help_text="Minimum age to be counted as 'child' (below = infant)",
    )
    child_age_max = models.PositiveIntegerField(
        default=12, help_text="Maximum age to be counted as 'child' (above = adult)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'pricing'

    def calculate_extra_charges(self, adults=2, children=0, infants=0, nights=1):
        """
        Calculate extra occupancy charges.

        Returns:
            Dict with extra_adult_total, child_total, infant_total, total_extra
        """
        from decimal import Decimal
        extra_adults = max(0, adults - self.base_occupancy)
        adult_extra = Decimal(str(self.extra_adult_charge)) * extra_adults * nights
        child_total = Decimal(str(self.child_charge)) * children * nights
        infant_total = Decimal(str(self.infant_charge)) * infants * nights
        return {
            'extra_adults': extra_adults,
            'extra_adult_total': adult_extra,
            'children': children,
            'child_total': child_total,
            'infants': infants,
            'infant_total': infant_total,
            'total_extra': adult_extra + child_total + infant_total,
        }

    def __str__(self):
        return (
            f"Occupancy pricing for {self.room_type}: "
            f"base={self.base_occupancy}, max={self.max_occupancy}, "
            f"extra_adult=₹{self.extra_adult_charge}/night"
        )
