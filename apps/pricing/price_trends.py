"""
Price History & Trend Detection.

Analyses CompetitorPrice history to:
  - Detect "Great Deal" signals (current price significantly below average)
  - Flag abnormal price spikes
  - Compute rolling trend direction (rising / falling / stable)

Feeds into the search index (`deal_score`) and HotelCard badges.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Min, Max, StdDev, Count
from django.utils import timezone

from celery import shared_task

logger = logging.getLogger('zygotrip.pricing.trends')


# ── Threshold configuration ──────────────────────────────────────

GREAT_DEAL_THRESHOLD = Decimal('0.75')   # Current price <= 75% of 30-day avg → great deal
SPIKE_THRESHOLD = Decimal('1.40')        # Current price >= 140% of 30-day avg → price spike
TREND_LOOKBACK_DAYS = 30
MIN_DATA_POINTS = 3                       # Minimum competitor entries for trend detection


class PriceTrend:
    """Price trend analysis result for a property on a date."""

    def __init__(self, property_id: int, check_date: date):
        self.property_id = property_id
        self.check_date = check_date
        self.avg_30d: Decimal | None = None
        self.min_30d: Decimal | None = None
        self.max_30d: Decimal | None = None
        self.stddev: Decimal | None = None
        self.current_min: Decimal | None = None
        self.data_points: int = 0
        self.is_great_deal: bool = False
        self.is_price_spike: bool = False
        self.deal_score: int = 0          # 0-100
        self.trend_direction: str = 'stable'  # rising / falling / stable

    def to_dict(self) -> dict:
        return {
            'property_id': self.property_id,
            'check_date': str(self.check_date),
            'avg_30d': float(self.avg_30d) if self.avg_30d else None,
            'min_30d': float(self.min_30d) if self.min_30d else None,
            'max_30d': float(self.max_30d) if self.max_30d else None,
            'current_min': float(self.current_min) if self.current_min else None,
            'data_points': self.data_points,
            'is_great_deal': self.is_great_deal,
            'is_price_spike': self.is_price_spike,
            'deal_score': self.deal_score,
            'trend_direction': self.trend_direction,
        }


def analyse_price_trend(property_id: int, check_date: date | None = None) -> PriceTrend:
    """
    Analyse competitor price history for a property and detect trends.

    Returns a PriceTrend with deal/spike flags, deal_score, and trend direction.
    """
    from apps.pricing.models import CompetitorPrice

    if check_date is None:
        check_date = date.today() + timedelta(days=1)

    trend = PriceTrend(property_id, check_date)
    lookback_start = check_date - timedelta(days=TREND_LOOKBACK_DAYS)

    # ── Gather 30-day history ────────────────────────────────────
    history = CompetitorPrice.objects.filter(
        property_id=property_id,
        date__gte=lookback_start,
        date__lte=check_date,
        is_available=True,
    )

    agg = history.aggregate(
        avg_price=Avg('price_per_night'),
        min_price=Min('price_per_night'),
        max_price=Max('price_per_night'),
        std_price=StdDev('price_per_night'),
        cnt=Count('id'),
    )

    trend.data_points = agg['cnt'] or 0
    if trend.data_points < MIN_DATA_POINTS:
        return trend  # Not enough data

    trend.avg_30d = Decimal(str(agg['avg_price'])) if agg['avg_price'] else None
    trend.min_30d = Decimal(str(agg['min_price'])) if agg['min_price'] else None
    trend.max_30d = Decimal(str(agg['max_price'])) if agg['max_price'] else None
    trend.stddev = Decimal(str(agg['std_price'])) if agg['std_price'] else None

    # ── Current competitor minimum (latest date) ──────────────────
    latest_prices = CompetitorPrice.objects.filter(
        property_id=property_id,
        date=check_date,
        is_available=True,
    )
    current_agg = latest_prices.aggregate(min_now=Min('price_per_night'))
    trend.current_min = Decimal(str(current_agg['min_now'])) if current_agg['min_now'] else None

    if not trend.current_min or not trend.avg_30d or trend.avg_30d == 0:
        return trend

    # ── Deal / Spike detection ────────────────────────────────────
    ratio = trend.current_min / trend.avg_30d

    if ratio <= GREAT_DEAL_THRESHOLD:
        trend.is_great_deal = True
    if ratio >= SPIKE_THRESHOLD:
        trend.is_price_spike = True

    # Deal score: 0 (bad deal) to 100 (incredible deal)
    # Mapped from ratio: 0.5 → 100, 0.75 → 60, 1.0 → 30, 1.4+ → 0
    if ratio <= Decimal('0.50'):
        trend.deal_score = 100
    elif ratio >= Decimal('1.40'):
        trend.deal_score = 0
    else:
        # Linear interpolation: 0.50→100, 1.40→0
        score = float((Decimal('1.40') - ratio) / Decimal('0.90') * 100)
        trend.deal_score = max(0, min(100, int(score)))

    # ── Trend direction (first-half avg vs second-half avg) ───────
    midpoint = lookback_start + timedelta(days=TREND_LOOKBACK_DAYS // 2)

    first_half = history.filter(date__lt=midpoint).aggregate(avg=Avg('price_per_night'))
    second_half = history.filter(date__gte=midpoint).aggregate(avg=Avg('price_per_night'))

    if first_half['avg'] and second_half['avg']:
        first_avg = Decimal(str(first_half['avg']))
        second_avg = Decimal(str(second_half['avg']))
        if first_avg > 0:
            change_pct = (second_avg - first_avg) / first_avg
            if change_pct > Decimal('0.05'):
                trend.trend_direction = 'rising'
            elif change_pct < Decimal('-0.05'):
                trend.trend_direction = 'falling'
            else:
                trend.trend_direction = 'stable'

    return trend


def batch_analyse_trends(property_ids: list[int] | None = None,
                         check_date: date | None = None) -> list[PriceTrend]:
    """Analyse trends for multiple properties. Used by Celery task."""
    from apps.hotels.models import Property

    if check_date is None:
        check_date = date.today() + timedelta(days=1)

    if property_ids is None:
        property_ids = list(
            Property.objects.filter(
                status='approved', is_active=True,
            ).values_list('id', flat=True)
        )

    trends = []
    for pid in property_ids:
        try:
            trend = analyse_price_trend(pid, check_date)
            trends.append(trend)
        except Exception as exc:
            logger.debug('Trend analysis failed for property %d: %s', pid, exc)

    return trends


# ── Celery task ──────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def update_deal_scores(self):
    """
    Batch-update deal scores in the PropertySearchIndex.
    Runs after competitor scans to keep deal badges fresh.
    """
    from apps.search.models import PropertySearchIndex

    trends = batch_analyse_trends()
    updated = 0

    for trend in trends:
        if trend.data_points < MIN_DATA_POINTS:
            continue
        try:
            rows = PropertySearchIndex.objects.filter(
                property_id=trend.property_id,
            ).update(deal_score=trend.deal_score)
            if rows:
                updated += 1
        except Exception:
            pass

    logger.info('Deal scores updated for %d properties (analysed %d)', updated, len(trends))
    return {'analysed': len(trends), 'updated': updated}
