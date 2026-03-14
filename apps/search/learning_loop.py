"""
Search Learning Loop.

Closes the feedback loop: search shown → hotel clicked → hotel booked.
Tracks per-property behavioral signals and feeds them into ranking.

Signals tracked:
  - Impressions: how often a property appears in search results
  - Clicks: how often users click through to a property page
  - Bookings: how often a clicked property converts to a booking
  - CTR: clicks / impressions
  - Booking conversion: bookings / clicks

These signals update PropertySearchIndex periodically (via Celery task)
and SearchRankingV2 uses them in real-time scoring.
"""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('zygotrip.search.learning')

# ── Cache key patterns ───────────────────────────────────────────
# Counters accumulate in Redis and are flushed to DB periodically.

IMPRESSION_KEY = 'sll:imp:{property_id}'
CLICK_KEY = 'sll:click:{property_id}'
COUNTER_TTL = 86400  # 24 hours


def record_impression(property_id: int):
    """Record that a property was shown in search results."""
    key = IMPRESSION_KEY.format(property_id=property_id)
    try:
        if cache.get(key) is None:
            cache.set(key, 1, timeout=COUNTER_TTL)
        else:
            cache.incr(key)
    except Exception:
        pass


def record_impressions_batch(property_ids: list[int]):
    """Record impressions for a batch of properties (after search results rendered)."""
    for pid in property_ids:
        record_impression(pid)


def record_click(property_id: int):
    """Record that a user clicked through to a property page."""
    key = CLICK_KEY.format(property_id=property_id)
    try:
        if cache.get(key) is None:
            cache.set(key, 1, timeout=COUNTER_TTL)
        else:
            cache.incr(key)
    except Exception:
        pass


def get_realtime_ctr(property_id: int) -> float:
    """Get real-time CTR for a property from cache counters."""
    try:
        impressions = cache.get(IMPRESSION_KEY.format(property_id=property_id)) or 0
        clicks = cache.get(CLICK_KEY.format(property_id=property_id)) or 0
        if impressions > 0:
            return round(clicks / impressions, 4)
    except Exception:
        pass
    return 0.0


# ── Flush to DB (called by aggregate_ctr_scores task) ────────────

def flush_learning_signals_to_db():
    """
    Flush accumulated Redis counters into PropertySearchIndex.

    Called by the existing aggregate_ctr_scores Celery task
    (apps/search/tasks.py) which already runs every 30 minutes.
    """
    from apps.search.models import PropertySearchIndex

    index_entries = PropertySearchIndex.objects.all().only(
        'id', 'property_id', 'total_impressions', 'total_clicks',
        'click_through_rate',
    )

    flushed = 0
    for entry in index_entries.iterator(chunk_size=100):
        pid = entry.property_id
        imp_key = IMPRESSION_KEY.format(property_id=pid)
        click_key = CLICK_KEY.format(property_id=pid)

        try:
            new_impressions = cache.get(imp_key) or 0
            new_clicks = cache.get(click_key) or 0

            if new_impressions == 0 and new_clicks == 0:
                continue

            # Accumulate into DB totals
            total_imp = (entry.total_impressions or 0) + new_impressions
            total_clicks = (entry.total_clicks or 0) + new_clicks
            ctr = round(total_clicks / total_imp, 4) if total_imp > 0 else 0

            PropertySearchIndex.objects.filter(pk=entry.pk).update(
                total_impressions=total_imp,
                total_clicks=total_clicks,
                click_through_rate=ctr,
            )

            # Reset counters after flush
            cache.delete(imp_key)
            cache.delete(click_key)
            flushed += 1

        except Exception as exc:
            logger.debug('Flush failed for property %d: %s', pid, exc)

    logger.info('Learning loop: flushed %d property signal updates to DB', flushed)
    return flushed
