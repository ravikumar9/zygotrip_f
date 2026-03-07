"""
System 7 — Enhanced Payment Reconciliation Engine.

Extends the basic PaymentReconciliation aggregate model with:
  - Transaction-level matching (individual PaymentTransaction vs gateway settlement line)
  - Settlement file parser stubs (Cashfree CSV, Stripe)
  - Discrepancy alerting via NotificationService
  - Daily reconciliation Celery task
"""
import csv
import io
import logging
from decimal import Decimal
from collections import defaultdict
from datetime import date, timedelta

from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.reconciliation')


# ============================================================================
# TRANSACTION-LEVEL RECONCILIATION MODEL
# ============================================================================

class ReconciliationLineItem(TimeStampedModel):
    """
    Individual transaction match result.
    One row per (gateway_settlement_txn_id, our_transaction_id) pair.
    """
    MATCH_AUTO = 'auto'
    MATCH_MANUAL = 'manual'
    MATCH_UNMATCHED = 'unmatched'

    MATCH_CHOICES = [
        (MATCH_AUTO, 'Auto-Matched'),
        (MATCH_MANUAL, 'Manual Match'),
        (MATCH_UNMATCHED, 'Unmatched'),
    ]

    reconciliation = models.ForeignKey(
        'payments.PaymentReconciliation',
        on_delete=models.CASCADE,
        related_name='line_items',
    )
    our_transaction_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text='Our PaymentTransaction.transaction_id',
    )
    gateway_settlement_id = models.CharField(
        max_length=200, blank=True, db_index=True,
        help_text='Gateway settlement/payout reference',
    )
    our_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gateway_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    match_status = models.CharField(max_length=15, choices=MATCH_CHOICES, default=MATCH_UNMATCHED)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'payments'
        indexes = [
            models.Index(fields=['reconciliation', 'match_status']),
        ]

    def __str__(self):
        return f"ReconLine {self.our_transaction_id}: {self.match_status} (diff={self.difference})"


# ============================================================================
# SETTLEMENT FILE PARSERS
# ============================================================================

class SettlementParser:
    """Base class for gateway settlement file parsers."""

    def parse(self, file_content: str) -> list:
        """
        Parse settlement data and return list of dicts:
        [
            {
                'gateway_txn_id': str,
                'settlement_id': str,
                'amount': Decimal,
                'fee': Decimal,
                'net_amount': Decimal,
                'date': date,
                'status': str,
            },
            ...
        ]
        """
        raise NotImplementedError


class CashfreeSettlementParser(SettlementParser):
    """
    Parse Cashfree settlement CSV.
    Expected columns: Order ID, Settlement ID, Order Amount, Service Charge,
                      Service Tax, Settlement Amount, Settlement Date, Status
    """

    def parse(self, file_content: str) -> list:
        reader = csv.DictReader(io.StringIO(file_content))
        results = []
        for row in reader:
            try:
                results.append({
                    'gateway_txn_id': row.get('Order ID', '').strip(),
                    'settlement_id': row.get('Settlement ID', '').strip(),
                    'amount': Decimal(row.get('Order Amount', '0').strip()),
                    'fee': Decimal(row.get('Service Charge', '0').strip()) +
                           Decimal(row.get('Service Tax', '0').strip()),
                    'net_amount': Decimal(row.get('Settlement Amount', '0').strip()),
                    'date': row.get('Settlement Date', '').strip(),
                    'status': row.get('Status', '').strip(),
                })
            except (ValueError, KeyError) as exc:
                logger.warning('Cashfree parse error row=%s: %s', row, exc)
        return results


class StripeSettlementParser(SettlementParser):
    """
    Parse Stripe payout reconciliation CSV.
    Expected columns: id, Amount, Fee, Net, Created (UTC), Status, Description
    """

    def parse(self, file_content: str) -> list:
        reader = csv.DictReader(io.StringIO(file_content))
        results = []
        for row in reader:
            try:
                results.append({
                    'gateway_txn_id': row.get('id', '').strip(),
                    'settlement_id': row.get('id', '').strip(),
                    'amount': Decimal(row.get('Amount', '0').strip()),
                    'fee': Decimal(row.get('Fee', '0').strip()),
                    'net_amount': Decimal(row.get('Net', '0').strip()),
                    'date': row.get('Created (UTC)', '').strip(),
                    'status': row.get('Status', '').strip(),
                })
            except (ValueError, KeyError) as exc:
                logger.warning('Stripe parse error row=%s: %s', row, exc)
        return results


GATEWAY_PARSERS = {
    'cashfree': CashfreeSettlementParser(),
    'stripe': StripeSettlementParser(),
}


# ============================================================================
# RECONCILIATION ENGINE
# ============================================================================

class ReconciliationEngine:
    """
    Transaction-level reconciliation engine.

    1. Loads our PaymentTransactions for the date range
    2. Matches against gateway settlement lines
    3. Creates ReconciliationLineItem for each match/mismatch
    4. Updates PaymentReconciliation aggregate record
    5. Alerts on discrepancies exceeding threshold
    """

    TOLERANCE = Decimal('1.00')  # Allow ₹1 rounding difference
    ALERT_THRESHOLD = Decimal('500.00')  # Alert if total discrepancy > ₹500

    @classmethod
    @transaction.atomic
    def reconcile_gateway(cls, gateway, recon_date, settlement_lines=None):
        """
        Run full reconciliation for a single gateway on a single date.

        Args:
            gateway: str ('cashfree', 'stripe', 'wallet', 'paytm_upi')
            recon_date: date
            settlement_lines: list of dicts from SettlementParser.parse()
                             If None, reconciles from DB only.

        Returns:
            PaymentReconciliation instance
        """
        from apps.payments.models import PaymentReconciliation, PaymentTransaction

        # Get or create the aggregate record
        recon, _ = PaymentReconciliation.objects.get_or_create(
            date=recon_date,
            gateway=gateway,
            defaults={'status': 'pending'},
        )

        # Load our transactions for this date + gateway
        our_txns = PaymentTransaction.objects.filter(
            gateway=gateway,
            status=PaymentTransaction.STATUS_SUCCESS,
            created_at__date=recon_date,
        )
        our_map = {txn.gateway_transaction_id: txn for txn in our_txns if txn.gateway_transaction_id}
        our_by_internal_id = {txn.transaction_id: txn for txn in our_txns}

        # Clear previous line items for re-run idempotency
        recon.line_items.all().delete()

        settlement_map = {}
        if settlement_lines:
            for line in settlement_lines:
                gw_id = line.get('gateway_txn_id', '')
                if gw_id:
                    settlement_map[gw_id] = line

        matched_count = 0
        unmatched_count = 0
        total_our = Decimal('0')
        total_gateway = Decimal('0')
        line_items = []

        # Match: iterate our transactions, find in settlement
        for gw_id, our_txn in our_map.items():
            total_our += our_txn.amount
            settlement = settlement_map.pop(gw_id, None)

            if settlement:
                gw_amount = settlement['net_amount']
                total_gateway += gw_amount
                diff = our_txn.amount - gw_amount
                status = ReconciliationLineItem.MATCH_AUTO if abs(diff) <= cls.TOLERANCE else ReconciliationLineItem.MATCH_UNMATCHED

                if status == ReconciliationLineItem.MATCH_AUTO:
                    matched_count += 1
                else:
                    unmatched_count += 1

                line_items.append(ReconciliationLineItem(
                    reconciliation=recon,
                    our_transaction_id=our_txn.transaction_id,
                    gateway_settlement_id=gw_id,
                    our_amount=our_txn.amount,
                    gateway_amount=gw_amount,
                    difference=diff,
                    match_status=status,
                    notes=f'Fee: ₹{settlement.get("fee", 0)}' if settlement.get('fee') else '',
                ))
            else:
                # We have the txn, settlement file doesn't — might be delayed
                unmatched_count += 1
                line_items.append(ReconciliationLineItem(
                    reconciliation=recon,
                    our_transaction_id=our_txn.transaction_id,
                    gateway_settlement_id='',
                    our_amount=our_txn.amount,
                    gateway_amount=Decimal('0'),
                    difference=our_txn.amount,
                    match_status=ReconciliationLineItem.MATCH_UNMATCHED,
                    notes='Missing from gateway settlement',
                ))

        # Remaining settlement lines not matched to our transactions
        for gw_id, line in settlement_map.items():
            gw_amount = line['net_amount']
            total_gateway += gw_amount
            unmatched_count += 1
            line_items.append(ReconciliationLineItem(
                reconciliation=recon,
                our_transaction_id='',
                gateway_settlement_id=gw_id,
                our_amount=Decimal('0'),
                gateway_amount=gw_amount,
                difference=-gw_amount,
                match_status=ReconciliationLineItem.MATCH_UNMATCHED,
                notes='Not found in our records',
            ))

        ReconciliationLineItem.objects.bulk_create(line_items)

        # Update aggregate
        discrepancy = total_our - total_gateway
        recon.expected_amount = total_our
        recon.settled_amount = total_gateway
        recon.discrepancy = discrepancy
        recon.transactions_matched = matched_count
        recon.transactions_unmatched = unmatched_count

        if unmatched_count == 0 and abs(discrepancy) <= cls.TOLERANCE:
            recon.status = 'matched'
        else:
            recon.status = 'discrepancy'

        recon.details = {
            'our_txn_count': our_txns.count(),
            'settlement_line_count': len(settlement_lines) if settlement_lines else 0,
            'auto_matched': matched_count,
            'unmatched': unmatched_count,
            'tolerance': str(cls.TOLERANCE),
        }
        recon.save()

        # Alert on large discrepancies
        if abs(discrepancy) > cls.ALERT_THRESHOLD:
            cls._send_discrepancy_alert(recon)

        logger.info(
            'Reconciliation %s %s: matched=%d unmatched=%d discrepancy=₹%s',
            gateway, recon_date, matched_count, unmatched_count, discrepancy,
        )
        return recon

    @staticmethod
    def _send_discrepancy_alert(recon):
        """Send alert about reconciliation discrepancy."""
        try:
            from apps.core.notification_service import notification_service
            notification_service.send_notification(
                channel='email',
                recipient='finance@zygotrip.com',
                subject=f'[ALERT] Payment Reconciliation Discrepancy — {recon.gateway} {recon.date}',
                body=(
                    f'Gateway: {recon.gateway}\n'
                    f'Date: {recon.date}\n'
                    f'Expected: ₹{recon.expected_amount}\n'
                    f'Settled: ₹{recon.settled_amount}\n'
                    f'Discrepancy: ₹{recon.discrepancy}\n'
                    f'Unmatched TXNs: {recon.transactions_unmatched}\n'
                ),
                metadata={'type': 'reconciliation_alert', 'gateway': recon.gateway},
            )
        except Exception as exc:
            logger.error('Failed to send reconciliation alert: %s', exc)
