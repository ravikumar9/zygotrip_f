"""
Pricing models — OTA Freeze Grade.

Phase 4: Consolidated pricing with seasonal/weekend/event modifiers and tax rules.
CompetitorPrice kept for price intelligence.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel


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
