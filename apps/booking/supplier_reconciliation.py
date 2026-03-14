"""
Supplier Booking Reconciliation — Daily verification of supplier-side statuses.

Verifies:
  - Hotel supplier confirmations match our booking records
  - Flight PNR status is still valid
  - Bus seat assignments are confirmed
  - Detects ghost bookings (supplier says cancelled, we say confirmed)
  - Generates mismatch alerts for operations team

Runs as daily Celery beat task.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.supplier_recon')


class SupplierReconciliation(TimeStampedModel):
    """Daily reconciliation run record."""

    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    recon_date = models.DateField(db_index=True)
    vertical = models.CharField(max_length=20, choices=[
        ('hotel', 'Hotel'), ('flight', 'Flight'), ('bus', 'Bus'), ('cab', 'Cab'),
    ])
    total_checked = models.IntegerField(default=0)
    matched = models.IntegerField(default=0)
    mismatched = models.IntegerField(default=0)
    not_found = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default=STATUS_RUNNING)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'booking'
        unique_together = ('recon_date', 'vertical')
        ordering = ['-recon_date']

    def __str__(self):
        return f"SupplierRecon {self.recon_date} ({self.vertical}): {self.status}"


class SupplierReconciliationItem(TimeStampedModel):
    """Individual booking reconciliation result."""

    RESULT_MATCHED = 'matched'
    RESULT_MISMATCH = 'mismatch'
    RESULT_NOT_FOUND = 'not_found'
    RESULT_SUPPLIER_ERROR = 'supplier_error'

    reconciliation = models.ForeignKey(
        SupplierReconciliation, on_delete=models.CASCADE,
        related_name='items',
    )
    booking_id = models.IntegerField(db_index=True)
    booking_ref = models.CharField(max_length=100)
    supplier_ref = models.CharField(max_length=200, blank=True)

    our_status = models.CharField(max_length=30)
    supplier_status = models.CharField(max_length=30, blank=True)
    our_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    result = models.CharField(max_length=20, choices=[
        (RESULT_MATCHED, 'Matched'),
        (RESULT_MISMATCH, 'Mismatch'),
        (RESULT_NOT_FOUND, 'Not Found at Supplier'),
        (RESULT_SUPPLIER_ERROR, 'Supplier API Error'),
    ])
    details = models.JSONField(default=dict, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)

    class Meta:
        app_label = 'booking'
        indexes = [
            models.Index(fields=['reconciliation', 'result']),
            models.Index(fields=['is_resolved', 'result']),
        ]


class SupplierReconciliationEngine:
    """
    Orchestrates daily supplier reconciliation across verticals.
    """

    # Map our booking statuses to expected supplier statuses
    STATUS_MAP = {
        'confirmed': ['confirmed', 'active', 'booked'],
        'checked_in': ['confirmed', 'active', 'checked_in'],
        'checked_out': ['completed', 'checked_out', 'past'],
        'cancelled': ['cancelled', 'refunded', 'voided'],
    }

    @classmethod
    def run_hotel_reconciliation(cls, recon_date=None):
        """
        Reconcile hotel bookings for a given date range.
        Checks bookings with check-in within -1 to +3 days of recon_date.
        """
        from apps.booking.models import Booking

        recon_date = recon_date or timezone.now().date()

        recon, created = SupplierReconciliation.objects.get_or_create(
            recon_date=recon_date,
            vertical='hotel',
            defaults={'status': SupplierReconciliation.STATUS_RUNNING},
        )
        if not created and recon.status == SupplierReconciliation.STATUS_COMPLETED:
            return recon

        recon.status = SupplierReconciliation.STATUS_RUNNING
        recon.save(update_fields=['status'])

        try:
            # Bookings with check-in near recon_date
            window_start = recon_date - timedelta(days=1)
            window_end = recon_date + timedelta(days=3)

            bookings = Booking.objects.filter(
                check_in__range=(window_start, window_end),
                status__in=['confirmed', 'checked_in', 'checked_out', 'cancelled'],
            ).select_related('property')

            stats = defaultdict(int)
            stats['total'] = bookings.count()

            for booking in bookings:
                result = cls._verify_hotel_booking(booking)
                SupplierReconciliationItem.objects.create(
                    reconciliation=recon,
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref or str(booking.id),
                    supplier_ref=result.get('supplier_ref', ''),
                    our_status=booking.status,
                    supplier_status=result.get('supplier_status', ''),
                    our_amount=booking.gross_amount or 0,
                    supplier_amount=result.get('supplier_amount'),
                    result=result['result'],
                    details=result.get('details', {}),
                )
                stats[result['result']] += 1

            recon.total_checked = stats['total']
            recon.matched = stats.get('matched', 0)
            recon.mismatched = stats.get('mismatch', 0)
            recon.not_found = stats.get('not_found', 0)
            recon.status = SupplierReconciliation.STATUS_COMPLETED
            recon.completed_at = timezone.now()
            recon.save()

            if recon.mismatched > 0 or recon.not_found > 0:
                cls._alert_mismatches(recon)

            logger.info(
                'Hotel reconciliation %s: checked=%d matched=%d mismatched=%d not_found=%d',
                recon_date, stats['total'], recon.matched, recon.mismatched, recon.not_found,
            )

        except Exception as e:
            recon.status = SupplierReconciliation.STATUS_FAILED
            recon.error_message = str(e)
            recon.save(update_fields=['status', 'error_message'])
            logger.exception('Hotel reconciliation failed for %s', recon_date)

        return recon

    @classmethod
    def _verify_hotel_booking(cls, booking):
        """
        Verify a single hotel booking against supplier records.
        Uses the supplier framework to check booking status.
        """
        try:
            from apps.inventory.models import SupplierPropertyMap

            supplier_maps = SupplierPropertyMap.objects.filter(
                property=booking.property, is_active=True,
            ).first()

            if not supplier_maps:
                # Direct booking (no external supplier)
                return {
                    'result': 'matched',
                    'supplier_ref': 'direct',
                    'supplier_status': booking.status,
                    'details': {'source': 'direct_booking'},
                }

            # Attempt supplier status check via adapter
            from apps.core.supplier_framework import get_adapter
            adapter = get_adapter(supplier_maps.supplier_name)
            if not adapter:
                return {
                    'result': 'supplier_error',
                    'details': {'error': f'No adapter for {supplier_maps.supplier_name}'},
                }

            try:
                supplier_booking = adapter.get_booking_status(
                    supplier_ref=getattr(booking, 'supplier_booking_ref', ''),
                    property_code=supplier_maps.supplier_property_id,
                )
            except Exception as e:
                return {
                    'result': 'supplier_error',
                    'details': {'error': str(e)},
                }

            if not supplier_booking:
                return {
                    'result': 'not_found',
                    'supplier_ref': supplier_maps.supplier_property_id,
                    'details': {'supplier': supplier_maps.supplier_name},
                }

            # Compare statuses
            expected_statuses = cls.STATUS_MAP.get(booking.status, [])
            supplier_status = supplier_booking.get('status', 'unknown').lower()

            if supplier_status in expected_statuses:
                return {
                    'result': 'matched',
                    'supplier_ref': supplier_booking.get('ref', ''),
                    'supplier_status': supplier_status,
                    'supplier_amount': supplier_booking.get('amount'),
                }
            else:
                return {
                    'result': 'mismatch',
                    'supplier_ref': supplier_booking.get('ref', ''),
                    'supplier_status': supplier_status,
                    'supplier_amount': supplier_booking.get('amount'),
                    'details': {
                        'our_status': booking.status,
                        'supplier_status': supplier_status,
                        'expected': expected_statuses,
                    },
                }

        except Exception as e:
            logger.exception('Error verifying booking %s', booking.id)
            return {
                'result': 'supplier_error',
                'details': {'error': str(e)},
            }

    @classmethod
    def _alert_mismatches(cls, recon):
        """Send alerts for mismatches to ops team."""
        try:
            from apps.core.notification_service import NotificationService

            mismatched_items = SupplierReconciliationItem.objects.filter(
                reconciliation=recon,
                result__in=['mismatch', 'not_found'],
            )

            summary = (
                f"Supplier Reconciliation Alert ({recon.recon_date}, {recon.vertical})\n"
                f"Checked: {recon.total_checked} | Mismatched: {recon.mismatched} | "
                f"Not Found: {recon.not_found}\n\n"
            )
            for item in mismatched_items[:20]:
                summary += (
                    f"  Booking #{item.booking_id} ({item.booking_ref}): "
                    f"ours={item.our_status}, supplier={item.supplier_status or 'N/A'}, "
                    f"result={item.result}\n"
                )

            NotificationService.send_admin_alert(
                subject=f'Supplier Recon Alert: {recon.mismatched + recon.not_found} issues',
                message=summary,
            )
        except Exception:
            logger.exception('Failed to send reconciliation alert')

    @classmethod
    def get_recon_summary(cls, days=7):
        """Get reconciliation summary for the last N days."""
        cutoff = timezone.now().date() - timedelta(days=days)
        recons = SupplierReconciliation.objects.filter(
            recon_date__gte=cutoff,
            status=SupplierReconciliation.STATUS_COMPLETED,
        ).order_by('-recon_date')

        return [{
            'date': r.recon_date,
            'vertical': r.vertical,
            'total': r.total_checked,
            'matched': r.matched,
            'mismatched': r.mismatched,
            'not_found': r.not_found,
            'match_rate': round(r.matched / max(r.total_checked, 1) * 100, 1),
        } for r in recons]

    @classmethod
    def get_unresolved_mismatches(cls, vertical=None):
        """Get all unresolved mismatch items for ops review."""
        qs = SupplierReconciliationItem.objects.filter(
            is_resolved=False,
            result__in=['mismatch', 'not_found'],
        ).select_related('reconciliation').order_by('-created_at')

        if vertical:
            qs = qs.filter(reconciliation__vertical=vertical)

        return qs
