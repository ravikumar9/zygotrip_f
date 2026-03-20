"""Loyalty service layer for point earning and redemption."""
import logging
from decimal import Decimal

from django.db import transaction

from apps.loyalty.models import LoyaltyAccount, LoyaltyTier, PointsTransaction, TIER_THRESHOLDS

logger = logging.getLogger(__name__)


TIER_NOTIFICATION_MESSAGES = {
    LoyaltyTier.GOLD: "You've reached Gold tier!",
    LoyaltyTier.PLATINUM: "You've reached Platinum tier!",
    LoyaltyTier.ELITE: "You've reached Elite tier!",
}


def _get_account(user):
    account, _ = LoyaltyAccount.objects.get_or_create(user=user)
    return account


def earn_points_for_booking(booking):
    if not booking.user_id:
        return Decimal('0')

    points = Decimal(int(Decimal(str(booking.total_amount or 0)) / Decimal('10')))
    if points <= 0:
        return Decimal('0')

    with transaction.atomic():
        account = _get_account(booking.user)
        account.points_balance += points
        account.lifetime_points += points
        account.save(update_fields=['points_balance', 'lifetime_points', 'updated_at'])

        PointsTransaction.objects.create(
            account=account,
            transaction_type=PointsTransaction.TYPE_EARNED,
            points=points,
            booking=booking,
            note=f'Earned on booking {booking.public_booking_id}',
        )

        upgraded, tier = account.recalculate_tier()
        if upgraded and tier in TIER_NOTIFICATION_MESSAGES:
            try:
                from apps.notifications.fcm_service import FCMService

                FCMService().send_to_user(
                    booking.user,
                    title='Tier Upgrade Unlocked',
                    body=TIER_NOTIFICATION_MESSAGES[tier],
                    data={'type': 'loyalty_tier_upgrade', 'tier': tier},
                )
            except Exception as exc:
                logger.exception('Tier upgrade push failed: %s', exc)

    return points


def redeem_points(user, points, booking=None):
    points = Decimal(str(points))
    if points <= 0:
        raise ValueError('points must be positive')

    with transaction.atomic():
        account = _get_account(user)
        if points > account.points_balance:
            raise ValueError('Insufficient points balance')

        discount = points / Decimal('100')
        account.points_balance -= points
        account.save(update_fields=['points_balance', 'updated_at'])

        PointsTransaction.objects.create(
            account=account,
            transaction_type=PointsTransaction.TYPE_REDEEMED,
            points=-points,
            booking=booking,
            note=f'Redeemed {points} points',
        )

    return discount


def redeem_estimate(user, booking_amount):
    account = _get_account(user)
    booking_amount = Decimal(str(booking_amount))
    max_discount = account.points_balance / Decimal('100')
    applicable_discount = min(max_discount, booking_amount)
    max_redeemable_points = (applicable_discount * Decimal('100')).quantize(Decimal('1'))
    return {
        'max_redeemable_points': float(max_redeemable_points),
        'max_discount': float(applicable_discount),
        'points_balance': float(account.points_balance),
    }
