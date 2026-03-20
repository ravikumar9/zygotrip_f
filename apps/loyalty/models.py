"""Loyalty/rewards system — points, tiers, redemption."""
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class LoyaltyTier(models.TextChoices):
    SILVER = 'silver', 'Silver'
    GOLD = 'gold', 'Gold'
    PLATINUM = 'platinum', 'Platinum'
    ELITE = 'elite', 'Elite'


TIER_THRESHOLDS = {
    LoyaltyTier.SILVER: Decimal('0'),
    LoyaltyTier.GOLD: Decimal('10000'),
    LoyaltyTier.PLATINUM: Decimal('50000'),
    LoyaltyTier.ELITE: Decimal('100000'),
}


def resolve_tier(lifetime_points: Decimal) -> str:
    for tier, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if lifetime_points >= threshold:
            return tier
    return LoyaltyTier.SILVER


class LoyaltyAccount(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='loyalty_program_account',
        related_query_name='loyalty_program_account',
    )
    points_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    lifetime_points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    tier = models.CharField(
        max_length=20,
        choices=LoyaltyTier.choices,
        default=LoyaltyTier.SILVER,
        db_index=True,
    )
    last_tier_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'loyalty'

    def __str__(self):
        return f"LoyaltyAccount({self.user}, {self.points_balance}pts, {self.tier})"

    def recalculate_tier(self):
        new_tier = resolve_tier(self.lifetime_points)
        if new_tier == self.tier:
            return False, self.tier
        self.tier = new_tier
        from django.utils import timezone
        self.last_tier_update = timezone.now()
        self.save(update_fields=['tier', 'last_tier_update', 'updated_at'])
        return True, self.tier


class PointsTransaction(TimeStampedModel):
    TYPE_EARNED = 'earned'
    TYPE_REDEEMED = 'redeemed'
    TYPE_EXPIRED = 'expired'
    TYPE_BONUS = 'bonus'

    TYPE_CHOICES = [
        (TYPE_EARNED, 'Earned'),
        (TYPE_REDEEMED, 'Redeemed'),
        (TYPE_EXPIRED, 'Expired'),
        (TYPE_BONUS, 'Bonus'),
    ]

    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True,
    )
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    points = models.DecimalField(max_digits=14, decimal_places=2)
    booking = models.ForeignKey(
        'booking.Booking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='loyalty_transactions',
        db_index=True,
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'loyalty'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['account', '-created_at'], name='loyalty_acct_date_idx')]

    def __str__(self):
        return f"Points({self.points}, {self.transaction_type})"
