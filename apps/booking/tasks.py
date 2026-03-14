"""
Booking Celery Tasks — Scheduled tasks for booking lifecycle management.
"""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.booking.tasks')


@shared_task
def daily_supplier_reconciliation():
    """Run daily supplier booking reconciliation for all verticals."""
    try:
        from apps.booking.supplier_reconciliation import SupplierReconciliationEngine
        recon = SupplierReconciliationEngine.run_hotel_reconciliation()
        logger.info(
            'Supplier reconciliation completed: checked=%d matched=%d mismatched=%d',
            recon.total_checked, recon.matched, recon.mismatched,
        )
        return {
            'status': recon.status,
            'checked': recon.total_checked,
            'matched': recon.matched,
            'mismatched': recon.mismatched,
        }
    except Exception as exc:
        logger.error('daily_supplier_reconciliation failed: %s', exc)
        return {'error': str(exc)}
