"""
Hotel Ranking Algorithm — OTA-grade property sorting.

Factors (weighted):
  1. Guest Rating (25%) — Higher avg_rating = higher rank
  2. Conversion Rate (15%) — Properties that convert searches to bookings
  3. Review Volume (10%) — More reviews = more trustworthy
  4. Price Competitiveness (15%) — Price vs. similar properties in same city
  5. Photo Quality (5%) — Properties with more/better photos
  6. Recency (10%) — Recently booked properties rank higher (popularity signal)
  7. Quality Score (10%) — Multi-factor hotel quality assessment
  8. Demand Score (5%) — Predicted demand from forecasting engine
  9. Freshness Bonus (5%) — Newly listed properties get a boost

Produces a 0-100 ranking_score stored on PropertySearchIndex for fast sort.
"""
import logging
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

logger = logging.getLogger('zygotrip.ranking')


WEIGHT_RATING = Decimal('0.25')
WEIGHT_CONVERSION = Decimal('0.15')
WEIGHT_REVIEWS = Decimal('0.10')
WEIGHT_PRICE = Decimal('0.15')
WEIGHT_PHOTOS = Decimal('0.05')
WEIGHT_RECENCY = Decimal('0.10')
WEIGHT_QUALITY = Decimal('0.10')
WEIGHT_DEMAND = Decimal('0.05')
WEIGHT_FRESHNESS = Decimal('0.05')


def compute_ranking_score(property_obj) -> int:
    """
    Compute a 0-100 ranking score for a property.
    Returns integer score.
    """
    scores = {}

    # 1. Rating score (0-100)
    rating = float(getattr(property_obj, 'avg_rating', 0) or 0)
    scores['rating'] = min(100, rating * 20)  # 5.0 → 100

    # 2. Review volume score (0-100)
    review_count = getattr(property_obj, 'review_count', 0) or 0
    scores['reviews'] = min(100, review_count * 2)  # 50+ reviews → 100

    # 3. Photo quality score (0-100)
    try:
        photo_count = property_obj.images.count() if hasattr(property_obj, 'images') else 0
    except Exception:
        photo_count = 0
    scores['photos'] = min(100, photo_count * 10)  # 10+ photos → 100

    # 4. Price competitiveness (0-100)
    # Compare to city average
    try:
        from apps.rooms.models import RoomType
        city_avg = RoomType.objects.filter(
            property__city=property_obj.city,
            property__is_active=True,
        ).aggregate(avg=Avg('base_price'))['avg']

        if city_avg and city_avg > 0:
            min_price = getattr(property_obj, 'min_price', 0) or 0
            if min_price > 0:
                ratio = float(city_avg) / float(min_price)
                scores['price'] = min(100, max(0, ratio * 50))
            else:
                scores['price'] = 50
        else:
            scores['price'] = 50
    except Exception:
        scores['price'] = 50

    # 5. Recency — bookings in last 30 days
    try:
        from apps.booking.models import Booking
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_bookings = Booking.objects.filter(
            property=property_obj,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED],
            created_at__gte=thirty_days_ago,
        ).count()
        scores['recency'] = min(100, recent_bookings * 5)  # 20+ bookings → 100
    except Exception:
        scores['recency'] = 0

    # 6. Conversion rate — approximate from booking contexts vs confirmed
    scores['conversion'] = 50  # Default; requires analytics data

    try:
        from apps.core.analytics import AnalyticsEvent
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        views = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
            property_id=property_obj.id,
            created_at__gte=thirty_days_ago,
        ).count()
        confirms = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
            property_id=property_obj.id,
            created_at__gte=thirty_days_ago,
        ).count()
        if views > 0:
            conv_rate = confirms / views
            scores['conversion'] = min(100, conv_rate * 500)  # 20% conversion → 100
    except Exception:
        pass

    # 7. Quality score from intelligence engine
    scores['quality'] = 50  # Default
    try:
        from apps.core.intelligence import HotelQualityScore
        quality = HotelQualityScore.objects.filter(property=property_obj).first()
        if quality:
            scores['quality'] = quality.overall_score
    except Exception:
        pass

    # 8. Demand score from forecasting engine
    scores['demand'] = 50  # Default
    try:
        from apps.core.intelligence import DemandForecast
        today = timezone.now().date()
        forecast = DemandForecast.objects.filter(
            property=property_obj, date=today,
        ).first()
        if forecast:
            scores['demand'] = forecast.predicted_demand_score
    except Exception:
        pass

    # 9. Freshness bonus — new listings get a 90-day boost
    scores['freshness'] = 0
    try:
        created = getattr(property_obj, 'created_at', None)
        if created:
            age_days = (timezone.now() - created).days
            if age_days <= 90:
                scores['freshness'] = max(0, 100 - int(age_days * 1.1))
    except Exception:
        pass

    # Weighted total
    total = (
        Decimal(str(scores.get('rating', 0))) * WEIGHT_RATING +
        Decimal(str(scores.get('conversion', 0))) * WEIGHT_CONVERSION +
        Decimal(str(scores.get('reviews', 0))) * WEIGHT_REVIEWS +
        Decimal(str(scores.get('price', 0))) * WEIGHT_PRICE +
        Decimal(str(scores.get('photos', 0))) * WEIGHT_PHOTOS +
        Decimal(str(scores.get('recency', 0))) * WEIGHT_RECENCY +
        Decimal(str(scores.get('quality', 0))) * WEIGHT_QUALITY +
        Decimal(str(scores.get('demand', 0))) * WEIGHT_DEMAND +
        Decimal(str(scores.get('freshness', 0))) * WEIGHT_FRESHNESS
    )

    return min(100, max(0, int(total)))


def update_property_ranking(property_obj):
    """Update ranking score on PropertySearchIndex (uses popularity_score field)."""
    try:
        from apps.search.models import PropertySearchIndex
        score = compute_ranking_score(property_obj)
        PropertySearchIndex.objects.filter(
            property=property_obj,
        ).update(popularity_score=score)
        logger.info('Updated ranking: property=%s score=%d', property_obj.id, score)
        return score
    except Exception as e:
        logger.error('Failed to update ranking for property %s: %s', property_obj.id, e)
        return 0


def bulk_update_rankings():
    """Recompute rankings for all active properties. Run daily via Celery."""
    from apps.hotels.models import Property

    properties = Property.objects.filter(is_active=True).select_related('city')
    updated = 0
    for prop in properties.iterator(chunk_size=100):
        try:
            update_property_ranking(prop)
            updated += 1
        except Exception as e:
            logger.error('Ranking update failed for property %s: %s', prop.id, e)

    logger.info('Bulk ranking update complete: %d properties updated', updated)
    return updated
