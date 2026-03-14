"""
Loyalty & Rewards System - OTA-grade points program.

Tier system:
  - Bronze (default): 1x points
  - Silver (5000+ points): 1.25x points, free cancellation on cabs
  - Gold (15000+ points): 1.5x points, priority support, 5% extra discount
  - Platinum (50000+ points): 2x points, lounge access, 10% extra discount

Points: 10 per 100 INR spent. 100 points = 10 INR discount. Min 500 to redeem.

Vertical multipliers:
  Hotels: 1.0x, Flights: 1.2x, Cabs: 0.8x, Buses: 0.8x, Activities: 1.0x, Packages: 1.5x
"""
import logging
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.loyalty')

# ── Vertical-specific earn multipliers ──
VERTICAL_MULTIPLIERS = {
    'hotel': Decimal('1.0'),
    'flight': Decimal('1.2'),
    'cab': Decimal('0.8'),
    'bus': Decimal('0.8'),
    'activity': Decimal('1.0'),
    'package': Decimal('1.5'),
}

# ── Tier-based perks ──
TIER_PERKS = {
    'bronze': {
        'points_multiplier': Decimal('1.0'),
        'extra_discount_percent': Decimal('0'),
        'free_cancellation': False,
        'priority_support': False,
        'lounge_access': False,
        'welcome_bonus': 0,
    },
    'silver': {
        'points_multiplier': Decimal('1.25'),
        'extra_discount_percent': Decimal('2'),
        'free_cancellation': True,  # on cabs only
        'priority_support': False,
        'lounge_access': False,
        'welcome_bonus': 500,
    },
    'gold': {
        'points_multiplier': Decimal('1.5'),
        'extra_discount_percent': Decimal('5'),
        'free_cancellation': True,
        'priority_support': True,
        'lounge_access': False,
        'welcome_bonus': 2000,
    },
    'platinum': {
        'points_multiplier': Decimal('2.0'),
        'extra_discount_percent': Decimal('10'),
        'free_cancellation': True,
        'priority_support': True,
        'lounge_access': True,
        'welcome_bonus': 5000,
    },
}


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
def earn_points(user, amount_spent, reference_type='booking', reference_id='', vertical='hotel'):
    """Earn loyalty points with tier multiplier and vertical multiplier."""
    account = get_or_create_loyalty_account(user)
    tier_multiplier = LoyaltyTier.MULTIPLIERS.get(account.tier, Decimal('1.0'))
    vertical_multiplier = VERTICAL_MULTIPLIERS.get(vertical, Decimal('1.0'))
    base_points = int(Decimal(str(amount_spent)) / 100) * 10
    final_points = int(Decimal(base_points) * tier_multiplier * vertical_multiplier)
    if final_points <= 0:
        return 0
    account.total_points_earned += final_points
    account.available_points += final_points
    account.save(update_fields=['total_points_earned', 'available_points', 'updated_at'])
    LoyaltyTransaction.objects.create(
        account=account, txn_type=LoyaltyTransaction.TYPE_EARN, points=final_points,
        description=f'Earned {final_points} pts ({vertical})',
        reference_type=reference_type, reference_id=str(reference_id),
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


def get_tier_perks(user):
    """Get the perks for a user's current loyalty tier."""
    account = get_or_create_loyalty_account(user)
    perks = TIER_PERKS.get(account.tier, TIER_PERKS['bronze']).copy()
    perks['tier'] = account.tier
    perks['total_points_earned'] = account.total_points_earned
    perks['available_points'] = account.available_points
    next_tier = _get_next_tier(account.tier)
    if next_tier:
        threshold = LoyaltyTier.THRESHOLDS[next_tier]
        perks['next_tier'] = next_tier
        perks['points_to_next_tier'] = max(0, threshold - account.total_points_earned)
    else:
        perks['next_tier'] = None
        perks['points_to_next_tier'] = 0
    return perks


def _get_next_tier(current_tier):
    order = [LoyaltyTier.BRONZE, LoyaltyTier.SILVER, LoyaltyTier.GOLD, LoyaltyTier.PLATINUM]
    try:
        idx = order.index(current_tier)
        return order[idx + 1] if idx + 1 < len(order) else None
    except ValueError:
        return LoyaltyTier.SILVER


# ── Point Expiry & Tier Maintenance ──

POINT_EXPIRY_MONTHS = 12  # Points expire after 12 months of inactivity


@transaction.atomic
def expire_inactive_points(dry_run=False):
    """
    Expire points for accounts with no earn/redeem activity in POINT_EXPIRY_MONTHS.
    Returns list of (user_id, expired_points) tuples.
    """
    cutoff = timezone.now() - timedelta(days=POINT_EXPIRY_MONTHS * 30)
    expired = []

    accounts = LoyaltyAccount.objects.filter(
        available_points__gt=0,
    ).select_for_update()

    for account in accounts:
        last_activity = LoyaltyTransaction.objects.filter(
            account=account,
            txn_type__in=[LoyaltyTransaction.TYPE_EARN, LoyaltyTransaction.TYPE_REDEEM],
        ).order_by('-created_at').values_list('created_at', flat=True).first()

        if last_activity and last_activity < cutoff:
            pts = account.available_points
            if not dry_run:
                LoyaltyTransaction.objects.create(
                    account=account,
                    txn_type=LoyaltyTransaction.TYPE_EXPIRE,
                    points=-pts,
                    description=f'Points expired after {POINT_EXPIRY_MONTHS} months inactivity',
                )
                account.available_points = 0
                account.save(update_fields=['available_points', 'updated_at'])
            expired.append((account.user_id, pts))
            logger.info(
                'Expired %d points for user %s (last activity: %s)',
                pts, account.user_id, last_activity,
            )

    return expired


@transaction.atomic
def refresh_all_tiers():
    """
    Recalculate tiers for all accounts. Handles both upgrades and downgrades.
    Returns list of (user_id, old_tier, new_tier) changes.
    """
    changes = []
    for account in LoyaltyAccount.objects.select_for_update().iterator():
        old_tier = account.tier
        new_tier = LoyaltyTier.for_points(account.total_points_earned)
        if old_tier != new_tier:
            account.tier = new_tier
            account.save(update_fields=['tier', 'updated_at'])
            changes.append((account.user_id, old_tier, new_tier))
            logger.info(
                'Tier change user %s: %s → %s',
                account.user_id, old_tier, new_tier,
            )
    return changes


def get_loyalty_summary(user):
    """Full loyalty summary for user profile / dashboard."""
    account = get_or_create_loyalty_account(user)
    perks = TIER_PERKS.get(account.tier, TIER_PERKS['bronze']).copy()
    next_tier = _get_next_tier(account.tier)

    recent_txns = LoyaltyTransaction.objects.filter(
        account=account,
    ).order_by('-created_at')[:10].values(
        'txn_type', 'points', 'description', 'created_at',
    )

    return {
        'tier': account.tier,
        'total_earned': account.total_points_earned,
        'available': account.available_points,
        'points_value_inr': Decimal(account.available_points) / 10,
        'multiplier': perks['points_multiplier'],
        'extra_discount': perks['extra_discount_percent'],
        'perks': perks,
        'next_tier': next_tier,
        'points_to_next': max(0, LoyaltyTier.THRESHOLDS.get(next_tier, 0) - account.total_points_earned) if next_tier else 0,
        'recent_transactions': list(recent_txns),
    }
