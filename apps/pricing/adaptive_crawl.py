"""
Adaptive Competitor Crawl Dispatcher.

Replaces the fixed 3-hour competitor scan with demand-based tiers:
  HIGH demand   → every 15-30 minutes  (bookings_today >= 5 OR rooms_left <= 3)
  MEDIUM demand → every 1-2 hours       (bookings_today >= 2 OR recent searches)
  LOW demand    → every 6-12 hours       (everything else)

The dispatcher runs every 15 minutes via Celery Beat and enqueues
per-property scrape tasks only when they are "due" based on their tier.
"""
import logging
import time as _time
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('zygotrip.pricing.adaptive_crawl')

# ── Tier configuration (seconds between scrapes) ─────────────────

TIER_HIGH_INTERVAL = 30 * 60       # 30 minutes
TIER_MEDIUM_INTERVAL = 2 * 3600    # 2 hours
TIER_LOW_INTERVAL = 8 * 3600       # 8 hours

CACHE_PREFIX = 'competitor_last_scan:'


def _classify_demand(prop) -> str:
    """Classify a property into HIGH / MEDIUM / LOW demand tier."""
    # HIGH: many bookings today or very low inventory
    bookings_today = getattr(prop, 'bookings_today', 0) or 0
    if bookings_today >= 5:
        return 'HIGH'

    # Check rooms_left from search index cache
    rooms_left = cache.get(f'rooms_left:{prop.id}')
    if rooms_left is not None and rooms_left <= 3:
        return 'HIGH'

    # MEDIUM: moderate activity
    if bookings_today >= 2:
        return 'MEDIUM'

    # Check recent search impressions (from search index)
    impressions = cache.get(f'search_impressions:{prop.id}')
    if impressions is not None and impressions >= 50:
        return 'MEDIUM'

    return 'LOW'


def _interval_for_tier(tier: str) -> int:
    """Return scrape interval in seconds for a demand tier."""
    if tier == 'HIGH':
        return TIER_HIGH_INTERVAL
    if tier == 'MEDIUM':
        return TIER_MEDIUM_INTERVAL
    return TIER_LOW_INTERVAL


def _is_due(property_id: int, interval: int) -> bool:
    """Check if a property is due for a competitor scrape."""
    last_scan = cache.get(f'{CACHE_PREFIX}{property_id}')
    if last_scan is None:
        return True
    elapsed = _time.time() - last_scan
    return elapsed >= interval


def _mark_scanned(property_id: int):
    """Record the timestamp of this scan in cache."""
    cache.set(f'{CACHE_PREFIX}{property_id}', _time.time(), timeout=86400)


# ── Celery tasks ─────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def adaptive_competitor_dispatch(self):
    """
    Demand-tier dispatcher: runs every 15 minutes.
    Classifies each property and enqueues a scrape task only when due.

    This replaces the fixed 3-hour full scan with intelligent scheduling.
    """
    from apps.hotels.models import Property

    properties = Property.objects.filter(
        status='approved', agreement_signed=True, is_active=True,
    ).select_related('city').only(
        'id', 'name', 'bookings_today', 'city__name',
    )

    stats = {'high': 0, 'medium': 0, 'low': 0, 'dispatched': 0, 'skipped': 0}

    for prop in properties.iterator(chunk_size=50):
        tier = _classify_demand(prop)
        interval = _interval_for_tier(tier)

        stats[tier.lower()] += 1

        if _is_due(prop.id, interval):
            # Enqueue per-property scrape as a separate task for concurrency
            scrape_single_property.delay(prop.id, prop.name, prop.city.name if prop.city else '')
            _mark_scanned(prop.id)
            stats['dispatched'] += 1
        else:
            stats['skipped'] += 1

    logger.info(
        'Adaptive dispatch: high=%d medium=%d low=%d dispatched=%d skipped=%d',
        stats['high'], stats['medium'], stats['low'],
        stats['dispatched'], stats['skipped'],
    )
    return stats


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_single_property(self, property_id: int, property_name: str, city_name: str):
    """Scrape competitor rates for a single property and ingest them."""
    from apps.pricing.competitor_pipeline import _ota_scraper, ingest_competitor_rate

    tomorrow = date.today() + timedelta(days=1)
    day_after = tomorrow + timedelta(days=1)

    try:
        rates = _ota_scraper.scrape_rates_for_property(
            property_name=property_name,
            city_name=city_name,
            checkin=tomorrow,
            checkout=day_after,
        )

        ingested = 0
        for rate in rates:
            try:
                ingest_competitor_rate(
                    property_id=property_id,
                    competitor_name=rate['competitor_name'],
                    source=rate.get('source', 'scrape'),
                    price_per_night=rate['price_per_night'],
                    rate_date=tomorrow,
                    is_available=rate.get('is_available', True),
                    notes=rate.get('notes', ''),
                )
                ingested += 1
            except Exception:
                pass

        logger.debug('Scrape property %d: fetched=%d ingested=%d', property_id, len(rates), ingested)
        return {'property_id': property_id, 'rates': len(rates), 'ingested': ingested}

    except Exception as exc:
        logger.warning('Scrape property %d failed: %s', property_id, exc)
        raise self.retry(exc=exc)
