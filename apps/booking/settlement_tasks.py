"""
Settlement Automation — System 15: OTA Settlement Engine.

Schedule:
  Weekly  : every Monday 2 AM IST
  Monthly : 1st of each month 3 AM IST
  Daily   : refund adjustments at 1 AM IST

Settlement flow per owner:
  1. Collect all checked_out bookings (with 24h grace)
  2. Compute: gross − commission − pending_refunds = net_payout
  3. Create Settlement + SettlementLineItem records
  4. Credit OwnerWallet
  5. Mark bookings as settled
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.settlement')


@shared_task(name='booking.run_weekly_settlements', bind=True, max_retries=3)
def run_weekly_settlements(self):
    """Weekly settlement — triggered every Monday."""
    try:
        return _run_settlements('weekly')
    except Exception as exc:
        logger.error('Weekly settlement failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc, countdown=3600)


@shared_task(name='booking.run_monthly_settlements', bind=True, max_retries=3)
def run_monthly_settlements(self):
    """Monthly settlement — triggered 1st of month."""
    try:
        return _run_settlements('monthly')
    except Exception as exc:
        logger.error('Monthly settlement failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc, countdown=3600)


@shared_task(name='booking.process_refund_adjustments')
def process_refund_adjustments():
    """
    Daily refund processing task.
    Bookings in refund_pending for >2 hours → credit customer wallet + mark refunded.
    """
    from apps.booking.models import Booking
    from apps.wallet.models import Wallet, WalletTransaction

    cutoff   = timezone.now() - timedelta(hours=2)
    bookings = Booking.objects.filter(
        status=Booking.STATUS_REFUND_PENDING,
        updated_at__lte=cutoff,
    ).select_related('user', 'property')

    processed = 0
    for booking in bookings:
        try:
            with transaction.atomic():
                refund_amt = Decimal(str(booking.refund_amount or 0))
                if refund_amt > 0 and booking.user:
                    wallet, _ = Wallet.objects.get_or_create(user=booking.user,
                                                              defaults={'balance': Decimal('0')})
                    wallet.balance += refund_amt
                    wallet.save(update_fields=['balance'])
                    WalletTransaction.objects.create(
                        wallet    = wallet,
                        txn_type  = 'refund',
                        amount    = refund_amt,
                        balance_after = wallet.balance,
                        reference = booking.public_booking_id,
                        note      = f'Refund for booking {booking.public_booking_id}',
                    )
                booking.status = Booking.STATUS_REFUNDED
                booking.save(update_fields=['status', 'updated_at'])
                processed += 1
        except Exception as exc:
            logger.error('Refund adjustment failed for %s: %s', booking.public_booking_id, exc)

    logger.info('Refund adjustments processed: %d', processed)
    return {'processed': processed}


def _run_settlements(period: str) -> dict:
    """Core settlement logic — group checked_out bookings by owner and settle."""
    from apps.booking.models import Booking, Settlement, SettlementLineItem

    cutoff = timezone.now() - timedelta(hours=24)
    eligible = (
        Booking.objects
        .filter(status=Booking.STATUS_CHECKED_OUT, check_out__lte=cutoff.date())
        .select_related('property__owner', 'property')
        .order_by('property__owner')
    )

    if not eligible.exists():
        logger.info('[%s] No eligible bookings for settlement.', period)
        return {'period': period, 'settlements': 0, 'total_payout': '0'}

    # Group by owner
    by_owner: dict = {}
    for bk in eligible:
        if not (bk.property and bk.property.owner_id):
            continue
        oid = bk.property.owner_id
        by_owner.setdefault(oid, {'owner': bk.property.owner, 'bookings': []})
        by_owner[oid]['bookings'].append(bk)

    total_settlements = 0
    total_payout      = Decimal('0')

    for oid, group in by_owner.items():
        owner    = group['owner']
        bookings = group['bookings']
        try:
            with transaction.atomic():
                gross      = sum(Decimal(str(b.gross_amount or 0)) for b in bookings)
                commission = sum(Decimal(str(b.commission_amount or 0)) for b in bookings)
                refunds    = sum(Decimal(str(b.refund_amount or 0)) for b in bookings)
                net_payout = gross - commission - refunds

                if net_payout <= 0:
                    logger.warning('[%s] Zero/negative payout for owner %s — skipping', period, oid)
                    continue

                settlement = Settlement.objects.create(
                    hotel        = bookings[0].property,
                    period_start = min((b.check_in  for b in bookings if b.check_in),  default=None),
                    period_end   = max((b.check_out for b in bookings if b.check_out), default=None),
                    total_bookings     = len(bookings),
                    gross_revenue      = gross,
                    commission_deducted= commission,
                    refunds_deducted   = refunds,
                    net_payout         = net_payout,
                    status             = 'pending',
                )

                for bk in bookings:
                    try:
                        SettlementLineItem.objects.create(
                            settlement     = settlement,
                            booking        = bk,
                            booking_amount = Decimal(str(bk.gross_amount or 0)),
                            commission     = Decimal(str(bk.commission_amount or 0)),
                            refund         = Decimal(str(bk.refund_amount or 0)),
                            net            = Decimal(str(bk.net_payable_to_hotel or 0)),
                        )
                    except Exception:
                        pass

                # Credit owner wallet
                try:
                    from apps.wallet.models import OwnerWallet
                    ow, _ = OwnerWallet.objects.get_or_create(
                        owner=owner,
                        defaults={'balance': Decimal('0'), 'total_earned': Decimal('0')},
                    )
                    ow.balance      += net_payout
                    ow.total_earned += net_payout
                    ow.save(update_fields=['balance', 'total_earned'])
                except Exception as exc:
                    logger.warning('Owner wallet credit failed for owner %s: %s', oid, exc)

                # Mark bookings settled
                Booking.objects.filter(
                    id__in=[b.id for b in bookings]
                ).update(status=Booking.STATUS_SETTLED)

                settlement.status = 'completed'
                settlement.save(update_fields=['status'])

                total_settlements += 1
                total_payout      += net_payout
                logger.info('[%s] Settlement #%d — owner %s — %d bookings — ₹%s',
                            period, settlement.id, oid, len(bookings), net_payout)

        except Exception as exc:
            logger.error('[%s] Settlement failed for owner %s: %s', period, oid, exc, exc_info=True)

    logger.info('[%s] Complete: %d settlements — ₹%s total payout',
                period, total_settlements, total_payout)
    return {
        'period':       period,
        'settlements':  total_settlements,
        'total_payout': str(total_payout),
    }


@shared_task(name='booking.generate_settlement_report')
def generate_settlement_report(period_start: str, period_end: str) -> dict:
    """Generate a summary settlement report for a date range."""
    from apps.booking.models import Settlement
    from datetime import date

    try:
        start = date.fromisoformat(period_start)
        end   = date.fromisoformat(period_end)
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD'}

    ss = Settlement.objects.filter(
        period_start__gte=start,
        period_end__lte=end,
        status='completed',
    )

    total_bk      = sum(s.total_bookings for s in ss)
    total_rev     = sum(Decimal(str(s.gross_revenue or 0))       for s in ss)
    total_comm    = sum(Decimal(str(s.commission_deducted or 0)) for s in ss)
    total_payout  = sum(Decimal(str(s.net_payout or 0))          for s in ss)

    return {
        'period':                  {'start': period_start, 'end': period_end},
        'total_settlements':       ss.count(),
        'total_bookings':          total_bk,
        'total_revenue':           str(total_rev),
        'ota_commission':          str(total_comm),
        'net_payout_to_hotels':    str(total_payout),
    }
