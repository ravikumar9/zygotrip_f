"""
Inventory Ingestion Pipeline — Connects InventoryNormalizationEngine to the platform.

Flow:
  Supplier feeds → InventoryNormalizationEngine → InventoryCalendar → SearchIndex

This module provides Celery tasks and service functions that wire up the
normalization engine to the actual inventory storage layer.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.inventory.pipeline')


# ============================================================================
# SUPPLIER INGESTION
# ============================================================================

def ingest_supplier_feed(supplier_name: str, feed_data: list[dict]) -> dict:
    """
    Ingest a supplier feed through the normalization engine.

    Args:
        supplier_name: e.g. 'booking_com', 'expedia', 'staah'
        feed_data: list of dicts with keys:
            property_id, room_type_id, date, price, available_rooms,
            is_available (optional), meal_plan (optional)

    Returns:
        dict with ingested/skipped/error counts
    """
    from apps.inventory.normalization import InventoryNormalizationEngine

    engine = InventoryNormalizationEngine()
    stats = {'ingested': 0, 'skipped': 0, 'errors': 0}

    for entry in feed_data:
        try:
            engine.ingest_supplier_data(
                supplier_name=supplier_name,
                property_id=entry['property_id'],
                room_type_id=entry.get('room_type_id'),
                date=entry['date'] if isinstance(entry['date'], date) else date.fromisoformat(entry['date']),
                price=Decimal(str(entry['price'])),
                available_rooms=entry.get('available_rooms', 1),
                is_available=entry.get('is_available', True),
            )
            stats['ingested'] += 1
        except Exception as exc:
            logger.warning("Ingestion error for %s entry: %s", supplier_name, exc)
            stats['errors'] += 1

    logger.info(
        "Supplier %s feed: %d ingested, %d skipped, %d errors",
        supplier_name, stats['ingested'], stats['skipped'], stats['errors'],
    )
    return stats


def reconcile_all_properties(days_ahead: int = 30) -> dict:
    """
    Reconcile all active properties through the normalization engine.
    Updates InventoryCalendar with normalized rates from supplier data.

    Returns:
        dict with reconciled count
    """
    from apps.hotels.models import Property
    from apps.inventory.normalization import InventoryNormalizationEngine

    engine = InventoryNormalizationEngine()
    today = timezone.now().date()
    end_date = today + timedelta(days=days_ahead)

    properties = Property.objects.filter(
        status='approved', agreement_signed=True, is_active=True,
    ).values_list('id', flat=True)

    reconciled = 0
    for prop_id in properties:
        try:
            engine.reconcile_property(prop_id, today, end_date)
            reconciled += 1
        except Exception as exc:
            logger.warning("Reconciliation failed for property %d: %s", prop_id, exc)

    logger.info("Reconciled %d/%d properties", reconciled, len(properties))
    return {'reconciled': reconciled, 'total': len(properties)}


def detect_rate_parity_violations() -> list:
    """
    Scan for rate parity violations across all properties.
    Returns list of violation dicts.
    """
    from apps.hotels.models import Property
    from apps.inventory.normalization import InventoryNormalizationEngine

    engine = InventoryNormalizationEngine()
    today = timezone.now().date()
    end_date = today + timedelta(days=30)

    violations = []
    properties = Property.objects.filter(
        status='approved', agreement_signed=True,
    ).values_list('id', flat=True)

    for prop_id in properties:
        try:
            prop_violations = engine.detect_rate_parity_violations(prop_id, today, end_date)
            violations.extend(prop_violations)
        except Exception as exc:
            logger.warning("Rate parity check failed for property %d: %s", prop_id, exc)

    return violations


# ============================================================================
# CELERY TASKS
# ============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def task_ingest_supplier_feed(self, supplier_name: str, feed_data: list):
    """Async ingestion of a supplier feed."""
    try:
        return ingest_supplier_feed(supplier_name, feed_data)
    except Exception as exc:
        logger.error("Supplier feed ingestion failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def task_reconcile_all_properties(self):
    """
    Daily reconciliation of all properties.
    Schedule: daily at 6 AM.
    """
    try:
        return reconcile_all_properties(days_ahead=30)
    except Exception as exc:
        logger.error("Property reconciliation failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def task_detect_rate_parity(self):
    """
    Daily rate parity violation scan.
    Schedule: daily at 7 AM.
    """
    try:
        violations = detect_rate_parity_violations()
        if violations:
            logger.warning("Found %d rate parity violations", len(violations))
        return {'violations_count': len(violations)}
    except Exception as exc:
        logger.error("Rate parity scan failed: %s", exc)
        raise self.retry(exc=exc)
