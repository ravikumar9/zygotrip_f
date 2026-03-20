"""Loyalty Celery tasks."""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('zygotrip.loyalty.tasks')


@shared_task
def expire_loyalty_points():
    """
    Monthly task: expire points older than 1 year.
    Creates negative PointsTransaction for expired points.
    """
    from apps.loyalty.models import LoyaltyAccount, PointsTransaction
    from django.db import transaction as db_transaction

    now = timezone.now()
    expired_txns = PointsTransaction.objects.filter(
        expires_at__lte=now,
        transaction_type__in=[PointsTransaction.EARNED_BOOKING, PointsTransaction.BONUS, PointsTransaction.REFERRAL],
        points__gt=0,  # only positive (earned) transactions
    ).select_related('account')

    total_expired = 0
    for txn in expired_txns:
        try:
            with db_transaction.atomic():
                account = txn.account
                # Expire however many points remain
                pts_to_expire = min(txn.points, account.points_balance)
                if pts_to_expire <= 0:
                    continue

                account.points_balance -= pts_to_expire
                account.save(update_fields=['points_balance', 'updated_at'])

                PointsTransaction.objects.create(
                    account=account,
                    transaction_type=PointsTransaction.EXPIRED,
                    points=-pts_to_expire,
                    description=f'Expired: original txn {txn.id}',
                )
                # Mark original as expired (set expires_at to past)
                txn.expires_at = now
                txn.save(update_fields=['expires_at'])
                total_expired += pts_to_expire
        except Exception as exc:
            logger.warning('expire_points: txn=%s err=%s', txn.id, exc)

    logger.info('expire_loyalty_points: expired %d points', total_expired)
    return {'expired_points': total_expired}
