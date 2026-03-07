"""
Loyalty & Rewards System - OTA-grade points program.

Tier system:
  - Bronze (default): 1x points
  - Silver (5000+ points): 1.25x points
  - Gold (15000+ points): 1.5x points
  - Platinum (50000+ points): 2x points

Points: 10 per 100 INR spent. 100 points = 10 INR discount. Min 500 to redeem.
"""
import logging
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.loyalty')


class LoyaltyTier:
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'

    THRESHOLDS = {BRONZE: 0, SILVER: 5000, GOLD: 15000, PLATINUM: 50000}
    MULTIPLIERS = {BRONZE: Decimal('1.0'), SILVER: Decimal('1.25'), GOLD: Decimal('1.5'), PLATINUM: Decimal('2.0')}

    @classmethod
    def for_points(cls, total_points):
        if total_points >= cls.THRESHOLDS[cls.PLATINUM]:
            return cls.PLATINUM
        elif total_points >= cls.THRESHOLDS[cls.GOLD]:
            return cls.GOLD
        elif total_points >= cls.THRESHOLDS[cls.SILVER]:
            return cls.SILVER
        return cls.BRONZE


class LoyaltyAccount(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_account')
    total_points_earned = models.IntegerField(default=0)
    available_points = models.IntegerField(default=0)
    tier = models.CharField(max_length=10, default=LoyaltyTier.BRONZE, choices=[
        (LoyaltyTier.BRONZE, 'Bronze'), (LoyaltyTier.SILVER, 'Silver'),
        (LoyaltyTier.GOLD, 'Gold'), (LoyaltyTier.PLATINUM, 'Platinum'),
    ])

    class Meta:
        app_label = 'core'
        db_table = 'core_loyalty_account'

    def __str__(self):
        return f'{self.user_id} - {self.tier} ({self.available_points} pts)'

    def _refresh_tier(self):
        new_tier = LoyaltyTier.for_points(self.total_points_earned)
        if new_tier != self.tier:
            self.tier = new_tier
            self.save(update_fields=['tier', 'updated_at'])


class LoyaltyTransaction(TimeStampedModel):
    TYPE_EARN = 'earn'
    TYPE_REDEEM = 'redeem'
    TYPE_EXPIRE = 'expire'
    TYPE_BONUS = 'bonus'
    TYPE_CHOICES = [(TYPE_EARN, 'Earn'), (TYPE_REDEEM, 'Redeem'), (TYPE_EXPIRE, 'Expire'), (TYPE_BONUS, 'Bonus')]

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    txn_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    points = models.IntegerField()
    description = models.CharField(max_length=200, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)

    class Meta:
        app_label = 'core'
        db_table = 'core_loyalty_transaction'
        ordering = ['-created_at']


def get_or_create_loyalty_account(user):
    account, _ = LoyaltyAccount.objects.get_or_create(user=user)
    return account


@transaction.atomic
def earn_points(user, amount_spent, reference_type='booking', reference_id=''):
    account = get_or_create_loyalty_account(user)
    multiplier = LoyaltyTier.MULTIPLIERS.get(account.tier, Decimal('1.0'))
    base_points = int(Decimal(str(amount_spent)) / 100) * 10
    final_points = int(Decimal(base_points) * multiplier)
    if final_points <= 0:
        return 0
    account.total_points_earned += final_points
    account.available_points += final_points
    account.save(update_fields=['total_points_earned', 'available_points', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, txn_type=LoyaltyTransaction.TYPE_EARN, points=final_points,
        description=f'Earned {final_points} pts', reference_type=reference_type, reference_id=str(reference_id),
    )
    account._refresh_tier()
    return final_points


@transaction.atomic
def redeem_points(user, points_to_redeem):
    if points_to_redeem < 500:
        raise ValueError('Minimum 500 points required')
    account = get_or_create_loyalty_account(user)
    if account.available_points < points_to_redeem:
        raise ValueError(f'Insufficient points: {account.available_points} available')
    discount = Decimal(points_to_redeem) / 100 * 10
    account.available_points -= points_to_redeem
    account.save(update_fields=['available_points', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, txn_type=LoyaltyTransaction.TYPE_REDEEM, points=-points_to_redeem,
        description=f'Redeemed {points_to_redeem} pts for INR {discount} discount',
    )
    return discount


@transaction.atomic
def award_bonus(user, points, description, reference_type='', reference_id=''):
    account = get_or_create_loyalty_account(user)
    account.total_points_earned += points
    account.available_points += points
    account.save(update_fields=['total_points_earned', 'available_points', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, txn_type=LoyaltyTransaction.TYPE_BONUS, points=points,
        description=description, reference_type=reference_type, reference_id=str(reference_id),
    )
    account._refresh_tier()
    return points
