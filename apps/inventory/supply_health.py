"""
Supply Health Monitor.

Monitors supplier and property reliability and automatically downgrades
unreliable properties in search ranking.

Tracks:
  - Booking failure rate per property (last 7 days)
  - Inventory sync failures per supplier
  - Supplier response latency (from SupplierHealth model)

Properties with high failure rates get their reliability score reduced
in PropertySearchIndex.availability_reliability.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Count, Q, Avg
from django.utils import timezone

logger = logging.getLogger('zygotrip.supply_health')


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def monitor_supply_health(self):
    """
    Periodic supply health check (every 30 minutes).

    1. Compute per-property booking failure rate (7-day window).
    2. Downgrade search ranking for properties with >20% failure rate.
    3. Flag unhealthy suppliers and email alerts.
    4. Update PropertySearchIndex.availability_reliability.
    """
    from apps.booking.models import Booking
    from apps.inventory.models import SupplierHealth
    from apps.search.models import PropertySearchIndex

    now = timezone.now()
    window_start = now - timedelta(days=7)

    stats = {'properties_checked': 0, 'downgraded': 0, 'suppliers_unhealthy': 0}

    # ── 1. Per-property booking failure rate ──────────────────────
    try:
        from apps.hotels.models import Property

        properties = Property.objects.filter(
            status='approved', is_active=True,
        ).values_list('id', flat=True)

        for prop_id in properties:
            stats['properties_checked'] += 1
            total = Booking.objects.filter(
                property_id=prop_id,
                created_at__gte=window_start,
            ).count()

            if total < 5:
                continue  # Not enough data

            failed = Booking.objects.filter(
                property_id=prop_id,
                created_at__gte=window_start,
                status__in=['failed', 'payment_failed', 'supplier_error'],
            ).count()

            failure_rate = failed / total if total > 0 else 0

            # Compute reliability score: 1.0 - failure_rate (floor at 0.1)
            reliability = max(Decimal('0.10'), Decimal('1.00') - Decimal(str(round(failure_rate, 4))))

            # Update search index
            PropertySearchIndex.objects.filter(
                property_id=prop_id,
            ).update(availability_reliability=reliability)

            if failure_rate > 0.20:
                stats['downgraded'] += 1
                logger.warning(
                    'Property %d downgraded: failure_rate=%.2f%% (%d/%d bookings)',
                    prop_id, failure_rate * 100, failed, total,
                )

    except Exception as exc:
        logger.error('Property health check failed: %s', exc)

    # ── 2. Supplier health summary ────────────────────────────────
    try:
        unhealthy_suppliers = SupplierHealth.objects.filter(is_healthy=False)
        stats['suppliers_unhealthy'] = unhealthy_suppliers.count()

        for supplier in unhealthy_suppliers:
            logger.warning(
                'Unhealthy supplier: %s (error_rate=%.1f%%, avg_latency=%dms, disabled=%s)',
                supplier.supplier_name,
                (supplier.error_rate or 0) * 100,
                supplier.avg_latency_ms or 0,
                supplier.disabled_at is not None,
            )

    except Exception as exc:
        logger.error('Supplier health check failed: %s', exc)

    # ── 3. Track metrics ──────────────────────────────────────────
    try:
        from apps.core.metrics import registry
        registry.gauge(
            'zygotrip_supply_health_downgraded',
            stats['downgraded'],
            help_text='Properties downgraded due to high failure rate',
        )
        registry.gauge(
            'zygotrip_supply_health_unhealthy_suppliers',
            stats['suppliers_unhealthy'],
            help_text='Number of unhealthy suppliers',
        )
    except Exception:
        pass

    logger.info(
        'Supply health check: checked=%d downgraded=%d unhealthy_suppliers=%d',
        stats['properties_checked'], stats['downgraded'], stats['suppliers_unhealthy'],
    )
    return stats
