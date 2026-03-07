"""
Competitor Price Ingestion Pipeline.

Sources:
  1. Supplier API feeds (Hotelbeds, STAAH, SiteMinder)
  2. Scraped OTA rates (Booking.com, Agoda, MakeMyTrip)
  3. Manual rate uploads (admin dashboard)

Stores snapshots in CompetitorPrice and generates CompetitorRateAlerts.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('zygotrip.pricing.competitor')


# ============================================================================
# INGESTION FUNCTIONS
# ============================================================================

def ingest_competitor_rate(
    property_id: int,
    competitor_name: str,
    source: str,
    price_per_night: Decimal,
    rate_date: date = None,
    is_available: bool = True,
    notes: str = '',
) -> 'CompetitorPrice':
    """
    Ingest a single competitor rate snapshot.

    Args:
        property_id: Property PK
        competitor_name: e.g. 'Booking.com', 'Agoda', 'MakeMyTrip'
        source: 'api', 'scrape', 'manual'
        price_per_night: Competitor price
        rate_date: Date the rate applies to (default: today)
        is_available: Whether competitor has availability
        notes: Optional notes

    Returns:
        CompetitorPrice instance
    """
    from apps.pricing.models import CompetitorPrice
    from apps.hotels.models import Property

    if rate_date is None:
        rate_date = timezone.now().date()

    prop = Property.objects.get(pk=property_id)
    price = Decimal(str(price_per_night))

    cp, created = CompetitorPrice.objects.update_or_create(
        property=prop,
        competitor_name=competitor_name,
        date=rate_date,
        defaults={
            'source': source,
            'price_per_night': price,
            'is_available': is_available,
            'notes': notes,
            'fetched_at': timezone.now(),
        },
    )

    if created:
        logger.info(
            "New competitor rate: %s @ ₹%s for property %d on %s",
            competitor_name, price, property_id, rate_date,
        )
    return cp


def bulk_ingest_competitor_rates(rates: list[dict]) -> dict:
    """
    Bulk ingest competitor rates.

    Args:
        rates: list of dicts with keys:
            property_id, competitor_name, source, price_per_night,
            date (optional), is_available (optional), notes (optional)

    Returns:
        dict with ingested/errors counts
    """
    stats = {'ingested': 0, 'errors': 0}

    for entry in rates:
        try:
            ingest_competitor_rate(
                property_id=entry['property_id'],
                competitor_name=entry['competitor_name'],
                source=entry.get('source', 'api'),
                price_per_night=Decimal(str(entry['price_per_night'])),
                rate_date=entry.get('date'),
                is_available=entry.get('is_available', True),
                notes=entry.get('notes', ''),
            )
            stats['ingested'] += 1
        except Exception as exc:
            logger.warning("Competitor rate ingestion error: %s", exc)
            stats['errors'] += 1

    return stats


def detect_rate_parity_violations(tolerance_pct: float = 10.0) -> list[dict]:
    """
    Compare our prices with competitor prices and flag violations.

    A violation occurs when our price differs from a competitor by more
    than `tolerance_pct` percent.

    Returns:
        list of violation dicts: {property_id, competitor, our_price, their_price, delta_pct}
    """
    from apps.pricing.models import CompetitorPrice
    from apps.hotels.models import Property
    from django.db.models import Min

    violations = []
    today = timezone.now().date()

    # Get latest competitor prices per property
    properties_with_comps = (
        CompetitorPrice.objects
        .filter(date__gte=today - timedelta(days=7), is_available=True)
        .values_list('property_id', flat=True)
        .distinct()
    )

    for prop_id in properties_with_comps:
        try:
            prop = Property.objects.prefetch_related('room_types').get(pk=prop_id)
            our_min = prop.room_types.aggregate(min_p=Min('base_price'))['min_p']
            if not our_min:
                continue

            latest_comps = (
                CompetitorPrice.objects
                .filter(property_id=prop_id, is_available=True, date__gte=today - timedelta(days=7))
                .order_by('competitor_name', '-date')
            )

            seen = set()
            for cp in latest_comps:
                if cp.competitor_name in seen:
                    continue
                seen.add(cp.competitor_name)

                delta_pct = float((our_min - cp.price_per_night) / cp.price_per_night * 100)
                if abs(delta_pct) > tolerance_pct:
                    violations.append({
                        'property_id': prop_id,
                        'property_name': prop.name,
                        'competitor': cp.competitor_name,
                        'our_price': float(our_min),
                        'their_price': float(cp.price_per_night),
                        'delta_pct': round(delta_pct, 2),
                        'direction': 'cheaper' if delta_pct < 0 else 'more_expensive',
                    })
        except Exception as exc:
            logger.warning("Rate parity check failed for property %d: %s", prop_id, exc)

    if violations:
        logger.warning("Found %d rate parity violations (>%s%% diff)", len(violations), tolerance_pct)

    return violations


# ============================================================================
# ALERT GENERATION
# ============================================================================

def generate_competitor_alerts():
    """
    Generate CompetitorRateAlerts based on current market data.
    Called by daily Celery task.
    """
    from apps.core.intelligence import CompetitorIntelligence
    from apps.hotels.models import Property

    properties = Property.objects.filter(
        status='approved', agreement_signed=True, is_active=True,
    )

    alerts_created = 0
    for prop in properties:
        try:
            alerts = CompetitorIntelligence.scan_and_alert(prop)
            alerts_created += len(alerts)
        except Exception as exc:
            logger.warning("Alert generation failed for property %d: %s", prop.id, exc)

    logger.info("Generated %d competitor alerts", alerts_created)
    return alerts_created


# ============================================================================
# CELERY TASKS
# ============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def task_competitor_price_scan(self):
    """
    Daily competitor price scan + alert generation.
    Schedule: daily at 4 AM.
    """
    try:
        violations = detect_rate_parity_violations()
        alerts = generate_competitor_alerts()
        return {
            'violations': len(violations),
            'alerts_created': alerts,
        }
    except Exception as exc:
        logger.error("Competitor price scan failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def task_bulk_ingest_rates(self, rates: list):
    """Async bulk ingestion of competitor rates."""
    try:
        return bulk_ingest_competitor_rates(rates)
    except Exception as exc:
        logger.error("Bulk rate ingestion failed: %s", exc)
        raise self.retry(exc=exc)
