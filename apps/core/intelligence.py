"""
OTA Intelligence Engine — Demand Forecasting, Quality Scoring, Price Intelligence.

Production-grade systems for:
  1. Demand forecasting (ML-lite prediction model)
  2. Hotel quality scoring (multi-factor quality assessment)
  3. Competitor price intelligence (rate monitoring + recommendations)
  4. Conversion optimization signals

All scoring/prediction functions are designed to run as Celery periodic tasks
and store results for fast retrieval at query time.
"""
import logging
import math
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.db.models import Avg, Count, F, Q, Sum, Min, Max
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.intelligence')


def _q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ============================================================================
# MODELS
# ============================================================================

class DemandForecast(TimeStampedModel):
    """
    Pre-computed demand forecast per property per date.
    Updated daily by Celery task.
    """
    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='demand_forecasts',
    )
    date = models.DateField()
    predicted_occupancy = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Predicted occupancy rate 0.00-1.00",
    )
    predicted_demand_score = models.IntegerField(
        default=50,
        help_text="0-100 demand intensity score",
    )
    confidence = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('0.50'),
        help_text="Prediction confidence 0.00-1.00",
    )
    factors = models.JSONField(
        default=dict, blank=True,
        help_text="Contributing factors: seasonality, day_of_week, events, trend",
    )

    class Meta:
        app_label = 'core'
        unique_together = ('property', 'date')
        indexes = [
            models.Index(fields=['date', 'predicted_demand_score']),
            models.Index(fields=['property', 'date']),
        ]

    def __str__(self):
        return f"Forecast: {self.property.name} {self.date} — {self.predicted_occupancy:.0%}"


class HotelQualityScore(TimeStampedModel):
    """
    Multi-factor quality score for each property.
    Updated daily — used for ranking and trust badges.
    """
    property = models.OneToOneField(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='quality_score',
    )

    # Overall composite score 0-100
    overall_score = models.IntegerField(default=50)

    # Sub-scores (each 0-100)
    guest_satisfaction_score = models.IntegerField(default=50)
    pricing_competitiveness = models.IntegerField(default=50)
    response_rate_score = models.IntegerField(default=50)
    photo_quality_score = models.IntegerField(default=50)
    listing_completeness = models.IntegerField(default=50)
    cancellation_score = models.IntegerField(default=50)
    repeat_guest_rate = models.IntegerField(default=0)

    # Trust badges
    is_top_rated = models.BooleanField(default=False)
    is_value_pick = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)

    # Detailed breakdown
    breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['-overall_score']),
            models.Index(fields=['is_top_rated', '-overall_score']),
            models.Index(fields=['is_value_pick', '-overall_score']),
        ]

    def __str__(self):
        return f"Quality: {self.property.name} — {self.overall_score}/100"


class CompetitorRateAlert(TimeStampedModel):
    """
    Alerts when competitor prices deviate significantly.
    Used by property owners and revenue managers.
    """
    ALERT_UNDERCUT = 'undercut'
    ALERT_PARITY = 'parity_violation'
    ALERT_OPPORTUNITY = 'price_opportunity'

    ALERT_CHOICES = [
        (ALERT_UNDERCUT, 'Competitor Undercut'),
        (ALERT_PARITY, 'Rate Parity Violation'),
        (ALERT_OPPORTUNITY, 'Pricing Opportunity'),
    ]

    property = models.ForeignKey(
        'hotels.Property', on_delete=models.CASCADE,
        related_name='rate_alerts',
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_CHOICES)
    competitor_name = models.CharField(max_length=50)
    date = models.DateField()
    our_price = models.DecimalField(max_digits=10, decimal_places=2)
    competitor_price = models.DecimalField(max_digits=10, decimal_places=2)
    difference_pct = models.DecimalField(max_digits=5, decimal_places=1)
    recommendation = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property', 'is_resolved', '-created_at']),
        ]


# ============================================================================
# DEMAND FORECASTING
# ============================================================================

class DemandForecaster:
    """
    ML-lite demand forecasting using historical booking data + signals.

    Features used:
      1. Day-of-week seasonality (Fri/Sat higher)
      2. Monthly seasonality (peak months)
      3. Historical occupancy for same period
      4. Event pricing calendar
      5. Booking velocity (rate of recent bookings)
      6. Look-to-book ratio from analytics
    """

    # Monthly demand factors (India-specific)
    MONTHLY_FACTORS = {
        1: 0.80,   # Jan — post-holiday slowdown
        2: 0.75,   # Feb
        3: 0.70,   # Mar — end of season
        4: 0.60,   # Apr — off-peak
        5: 0.55,   # May — summer lull
        6: 0.65,   # Jun — monsoon start
        7: 0.60,   # Jul — deep monsoon
        8: 0.60,   # Aug
        9: 0.70,   # Sep — monsoon end
        10: 0.85,  # Oct — festival season
        11: 0.90,  # Nov — peak Diwali/wedding
        12: 0.95,  # Dec — Christmas/NY
    }

    DOW_FACTORS = {
        1: 0.7,  # Mon
        2: 0.7,  # Tue
        3: 0.7,  # Wed
        4: 0.8,  # Thu
        5: 1.0,  # Fri
        6: 1.1,  # Sat
        7: 0.9,  # Sun
    }

    @staticmethod
    def forecast_property(property_obj, start_date, end_date):
        """
        Generate demand forecasts for a property over a date range.
        Returns list of DemandForecast objects (saved to DB).
        """
        from apps.booking.models import Booking
        from apps.pricing.models import EventPricing

        forecasts = []
        current = start_date

        # Historical occupancy: avg bookings per day over last 90 days
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        historical_bookings = Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'checked_in', 'checked_out', 'settled'],
            check_in__gte=ninety_days_ago,
        ).count()
        avg_daily_bookings = historical_bookings / 90 if historical_bookings > 0 else 0.1

        # Booking velocity: last 7 days vs previous 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        fourteen_days_ago = timezone.now() - timedelta(days=14)
        recent_bookings = Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'hold'],
            created_at__gte=seven_days_ago,
        ).count()
        prev_bookings = Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'hold'],
            created_at__gte=fourteen_days_ago,
            created_at__lt=seven_days_ago,
        ).count()
        velocity_factor = (recent_bookings / max(prev_bookings, 1))
        velocity_factor = min(2.0, max(0.5, velocity_factor))

        while current <= end_date:
            # Base factors
            monthly = DemandForecaster.MONTHLY_FACTORS.get(current.month, 0.7)
            dow = DemandForecaster.DOW_FACTORS.get(current.isoweekday(), 0.7)

            # Event check
            has_event = EventPricing.objects.filter(
                property=property_obj,
                date=current,
                is_active=True,
            ).exists()
            event_factor = 1.3 if has_event else 1.0

            # Days until check-in factor (closer dates have more certainty)
            days_away = (current - timezone.now().date()).days
            proximity_factor = max(0.3, min(1.0, 1.0 - (days_away / 365)))

            # Composite prediction
            raw_occupancy = (
                monthly * 0.30 +
                dow * 0.20 +
                (avg_daily_bookings * 10) * 0.15 +
                event_factor * 0.15 +
                (velocity_factor * 0.5) * 0.10 +
                proximity_factor * 0.10
            )

            predicted_occupancy = min(1.0, max(0.0, raw_occupancy))
            demand_score = int(predicted_occupancy * 100)
            confidence = Decimal(str(min(0.9, proximity_factor * 0.8 + 0.1)))

            forecast, _ = DemandForecast.objects.update_or_create(
                property=property_obj,
                date=current,
                defaults={
                    'predicted_occupancy': Decimal(str(round(predicted_occupancy, 2))),
                    'predicted_demand_score': demand_score,
                    'confidence': confidence,
                    'factors': {
                        'monthly': monthly,
                        'dow': dow,
                        'event': has_event,
                        'velocity': round(velocity_factor, 2),
                        'proximity': round(proximity_factor, 2),
                        'avg_daily': round(avg_daily_bookings, 2),
                    },
                },
            )
            forecasts.append(forecast)
            current += timedelta(days=1)

        logger.info(
            'Forecasted %d days for property %s', len(forecasts), property_obj.id,
        )
        return forecasts


# ============================================================================
# HOTEL QUALITY SCORING
# ============================================================================

class QualityScorer:
    """
    Multi-factor hotel quality assessment.

    Factors:
      1. Guest Satisfaction (35%) — avg rating, review sentiment
      2. Pricing Competitiveness (15%) — our price vs competitors
      3. Response Rate (10%) — owner reply speed to inquiries
      4. Photo Quality (10%) — number and freshness of photos
      5. Listing Completeness (10%) — all fields filled, descriptions
      6. Cancellation Rate (10%) — low cancellation = good
      7. Repeat Guest Rate (10%) — loyalty indicator
    """

    WEIGHT_SATISFACTION = 0.35
    WEIGHT_PRICING = 0.15
    WEIGHT_RESPONSE = 0.10
    WEIGHT_PHOTOS = 0.10
    WEIGHT_COMPLETENESS = 0.10
    WEIGHT_CANCELLATION = 0.10
    WEIGHT_REPEAT = 0.10

    @staticmethod
    def score_property(property_obj):
        """
        Calculate and store quality scores for a property.
        Returns HotelQualityScore instance.
        """
        scores = {}

        # 1. Guest satisfaction
        scores['guest_satisfaction'] = QualityScorer._score_satisfaction(property_obj)

        # 2. Pricing competitiveness
        scores['pricing'] = QualityScorer._score_pricing(property_obj)

        # 3. Response rate
        scores['response'] = QualityScorer._score_response(property_obj)

        # 4. Photo quality
        scores['photos'] = QualityScorer._score_photos(property_obj)

        # 5. Listing completeness
        scores['completeness'] = QualityScorer._score_completeness(property_obj)

        # 6. Cancellation rate
        scores['cancellation'] = QualityScorer._score_cancellation(property_obj)

        # 7. Repeat guests
        scores['repeat'] = QualityScorer._score_repeat_guests(property_obj)

        # Weighted total
        overall = int(
            scores['guest_satisfaction'] * QualityScorer.WEIGHT_SATISFACTION +
            scores['pricing'] * QualityScorer.WEIGHT_PRICING +
            scores['response'] * QualityScorer.WEIGHT_RESPONSE +
            scores['photos'] * QualityScorer.WEIGHT_PHOTOS +
            scores['completeness'] * QualityScorer.WEIGHT_COMPLETENESS +
            scores['cancellation'] * QualityScorer.WEIGHT_CANCELLATION +
            scores['repeat'] * QualityScorer.WEIGHT_REPEAT
        )

        # Trust badges
        is_top_rated = scores['guest_satisfaction'] >= 80 and overall >= 75
        is_value_pick = scores['pricing'] >= 80 and scores['guest_satisfaction'] >= 60

        quality, _ = HotelQualityScore.objects.update_or_create(
            property=property_obj,
            defaults={
                'overall_score': overall,
                'guest_satisfaction_score': scores['guest_satisfaction'],
                'pricing_competitiveness': scores['pricing'],
                'response_rate_score': scores['response'],
                'photo_quality_score': scores['photos'],
                'listing_completeness': scores['completeness'],
                'cancellation_score': scores['cancellation'],
                'repeat_guest_rate': scores['repeat'],
                'is_top_rated': is_top_rated,
                'is_value_pick': is_value_pick,
                'breakdown': scores,
            },
        )

        logger.info(
            'Quality score: property=%s overall=%d top_rated=%s value_pick=%s',
            property_obj.id, overall, is_top_rated, is_value_pick,
        )
        return quality

    @staticmethod
    def _score_satisfaction(property_obj):
        """Rating-based satisfaction score (0-100)."""
        rating = float(getattr(property_obj, 'rating', 0) or 0)
        review_count = getattr(property_obj, 'review_count', 0) or 0

        if review_count == 0:
            return 40  # Neutral default

        # Rating contribution (max 80 points for 5.0 rating)
        rating_score = min(80, rating * 16)

        # Volume bonus (up to 20 points for 100+ reviews)
        volume_bonus = min(20, review_count * 0.2)

        return int(min(100, rating_score + volume_bonus))

    @staticmethod
    def _score_pricing(property_obj):
        """Price competitiveness vs competitors (0-100)."""
        from apps.pricing.models import CompetitorPrice
        from apps.rooms.models import RoomType

        cheapest = RoomType.objects.filter(
            property=property_obj,
        ).order_by('base_price').first()

        if not cheapest:
            return 50

        today = timezone.now().date()
        comp_avg = CompetitorPrice.objects.filter(
            property=property_obj,
            date__gte=today,
            date__lte=today + timedelta(days=30),
            is_available=True,
        ).aggregate(avg=Avg('price_per_night'))['avg']

        if not comp_avg:
            return 50  # No competitor data

        our_price = float(cheapest.base_price)
        comp_avg = float(comp_avg)

        if comp_avg == 0:
            return 50

        ratio = our_price / comp_avg
        # Cheaper = better score. ratio < 1 means we're cheaper.
        if ratio <= 0.80:
            return 100
        elif ratio <= 0.90:
            return 85
        elif ratio <= 1.00:
            return 70
        elif ratio <= 1.10:
            return 55
        elif ratio <= 1.20:
            return 40
        else:
            return 25

    @staticmethod
    def _score_response(property_obj):
        """Owner response rate to reviews/inquiries (0-100)."""
        from apps.hotels.review_models import Review
        total_reviews = Review.objects.filter(
            property=property_obj, status=Review.STATUS_APPROVED,
        ).count()
        responded = Review.objects.filter(
            property=property_obj, status=Review.STATUS_APPROVED,
        ).exclude(owner_response='').count()

        if total_reviews == 0:
            return 50
        return int(min(100, (responded / total_reviews) * 100))

    @staticmethod
    def _score_photos(property_obj):
        """Photo count and quality proxy (0-100)."""
        try:
            count = property_obj.images.count()
        except Exception:
            count = 0
        return min(100, count * 10)  # 10+ photos = 100

    @staticmethod
    def _score_completeness(property_obj):
        """Listing completeness with geo validation and amenity check (0-100)."""
        score = 0
        if property_obj.name:
            score += 10
        if getattr(property_obj, 'description', ''):
            score += 15
        if getattr(property_obj, 'address', ''):
            score += 10

        # Geo validation: lat/lng must exist AND be within reasonable India bounds
        lat = getattr(property_obj, 'latitude', None)
        lng = getattr(property_obj, 'longitude', None)
        if lat and lng:
            try:
                lat_f, lng_f = float(lat), float(lng)
                # India bounding box: lat 6.5-37.5, lng 68-97.5
                if 6.5 <= lat_f <= 37.5 and 68.0 <= lng_f <= 97.5:
                    score += 15  # Valid Indian coordinates
                else:
                    score += 5   # Has coords but outside India — partial credit
            except (ValueError, TypeError):
                score += 0  # Invalid coordinates

        if getattr(property_obj, 'star_category', 0):
            score += 10
        try:
            if property_obj.images.exists():
                score += 10
        except Exception:
            pass
        try:
            from apps.rooms.models import RoomType
            if RoomType.objects.filter(property=property_obj).exists():
                score += 10
        except Exception:
            pass

        # Amenity completeness: at least 3 amenities populated
        try:
            amenity_count = property_obj.amenities.count()
            if amenity_count >= 5:
                score += 20
            elif amenity_count >= 3:
                score += 15
            elif amenity_count >= 1:
                score += 10
        except Exception:
            # amenities relation may not exist on all Property implementations
            pass

        return min(100, score)

    @staticmethod
    def _score_cancellation(property_obj):
        """Low cancellation rate = high score (0-100)."""
        from apps.booking.models import Booking
        ninety_days = timezone.now() - timedelta(days=90)

        total = Booking.objects.filter(
            property=property_obj,
            created_at__gte=ninety_days,
        ).count()

        if total == 0:
            return 70  # Neutral default

        cancellations = Booking.objects.filter(
            property=property_obj,
            created_at__gte=ninety_days,
            status__in=['cancelled', 'refunded'],
        ).count()

        cancel_rate = cancellations / total
        return int(max(0, 100 - (cancel_rate * 200)))  # 50% cancel → 0

    @staticmethod
    def _score_repeat_guests(property_obj):
        """Repeat guest percentage (0-100)."""
        from apps.booking.models import Booking
        year_ago = timezone.now() - timedelta(days=365)

        bookings = Booking.objects.filter(
            property=property_obj,
            created_at__gte=year_ago,
            status__in=['confirmed', 'checked_out', 'settled'],
        )
        total_users = bookings.values('user').distinct().count()
        if total_users < 2:
            return 0

        repeat_users = bookings.values('user').annotate(
            cnt=Count('id'),
        ).filter(cnt__gt=1).count()

        return int(min(100, (repeat_users / total_users) * 200))  # 50% repeat → 100


# ============================================================================
# COMPETITOR PRICE INTELLIGENCE
# ============================================================================

class CompetitorIntelligence:
    """
    Monitors competitor pricing and generates alerts/recommendations.
    """

    @staticmethod
    def scan_and_alert(property_obj, threshold_pct=Decimal('0.10')):
        """
        Compare our prices to competitors and generate alerts.
        Returns list of created CompetitorRateAlert objects.
        """
        from apps.pricing.models import CompetitorPrice
        from apps.rooms.models import RoomType

        cheapest_room = RoomType.objects.filter(
            property=property_obj,
        ).order_by('base_price').first()

        if not cheapest_room:
            return []

        our_base = _q(cheapest_room.base_price)
        alerts = []
        today = timezone.now().date()

        comp_prices = CompetitorPrice.objects.filter(
            property=property_obj,
            date__gte=today,
            date__lte=today + timedelta(days=30),
            is_available=True,
        )

        for cp in comp_prices:
            diff_pct = _q((our_base - cp.price_per_night) / cp.price_per_night * 100) if cp.price_per_night > 0 else Decimal('0')

            alert_type = None
            recommendation = ''

            if diff_pct > threshold_pct * 100:
                # We're more expensive
                alert_type = CompetitorRateAlert.ALERT_UNDERCUT
                recommendation = (
                    f'Consider reducing price to ₹{cp.price_per_night * Decimal("1.02"):.0f} '
                    f'(2% above {cp.competitor_name}) to remain competitive.'
                )
            elif diff_pct < -(threshold_pct * 100):
                # We're cheaper — opportunity to raise
                alert_type = CompetitorRateAlert.ALERT_OPPORTUNITY
                recommendation = (
                    f'Price opportunity: we are {abs(diff_pct):.0f}% below {cp.competitor_name}. '
                    f'Consider raising to ₹{cp.price_per_night * Decimal("0.95"):.0f} '
                    f'(5% below competitor) to increase revenue.'
                )

            if alert_type:
                alert = CompetitorRateAlert.objects.create(
                    property=property_obj,
                    alert_type=alert_type,
                    competitor_name=cp.competitor_name,
                    date=cp.date,
                    our_price=our_base,
                    competitor_price=cp.price_per_night,
                    difference_pct=diff_pct,
                    recommendation=recommendation,
                )
                alerts.append(alert)

        logger.info(
            'Competitor scan for property %s: %d alerts generated',
            property_obj.id, len(alerts),
        )
        return alerts


# ============================================================================
# CONVERSION OPTIMIZATION SIGNALS
# ============================================================================

class ConversionSignals:
    """
    Compute real-time conversion signals for property display.
    These urgency/social-proof signals boost conversion rates.
    """

    @staticmethod
    def get_signals(property_obj, check_in=None, check_out=None):
        """Get conversion signals through the production-safe signal service."""
        from apps.core.conversion_signals import ConversionSignals as ConversionSignalService

        raw = ConversionSignalService.for_property(property_obj, check_in, check_out)
        rooms_left = raw.get('rooms_left')
        booked_today = raw.get('booked_today', 0)
        viewing_now = raw.get('viewing_now', 0)

        signals = {}
        if rooms_left is not None and rooms_left <= 8:
            signals['scarcity'] = {
                'show': True,
                'text': f'Only {rooms_left} room{"s" if rooms_left != 1 else ""} left!' if rooms_left <= 3 else f'{rooms_left} rooms left',
                'urgency': 'high' if rooms_left <= 3 else 'medium',
            }
        else:
            signals['scarcity'] = {'show': False}

        if booked_today > 0:
            signals['popularity'] = {
                'show': True,
                'text': f'Booked {booked_today} time{"s" if booked_today != 1 else ""} today',
                'urgency': 'high' if booked_today >= 5 else 'low',
            }
        else:
            signals['popularity'] = {'show': False}

        price_trend = raw.get('price_trend', 'stable')
        signals['price_trend'] = {
            'show': price_trend in {'rising', 'falling'},
            'text': 'Price rising - book now' if price_trend == 'rising' else ('Price dropped recently' if price_trend == 'falling' else ''),
            'direction': 'up' if price_trend == 'rising' else ('down' if price_trend == 'falling' else 'stable'),
        }

        review_count = getattr(property_obj, 'review_count', 0) or 0
        rating = float(getattr(property_obj, 'rating', 0) or 0)
        if viewing_now >= 2:
            signals['social_proof'] = {
                'show': True,
                'text': f'{viewing_now} people viewing this now',
            }
        elif review_count >= 50 and rating >= 4.0:
            signals['social_proof'] = {
                'show': True,
                'text': f'Loved by guests - {rating}★ ({review_count} reviews)',
            }
        elif review_count >= 10:
            signals['social_proof'] = {
                'show': True,
                'text': f'{review_count} verified reviews',
            }
        else:
            signals['social_proof'] = {'show': False}

        badges = []
        try:
            quality = HotelQualityScore.objects.get(property=property_obj)
            if quality.is_top_rated:
                badges.append({'type': 'top_rated', 'text': 'Top Rated'})
            if quality.is_value_pick:
                badges.append({'type': 'value_pick', 'text': 'Value Pick'})
            if quality.is_trending:
                badges.append({'type': 'trending', 'text': 'Trending'})
        except HotelQualityScore.DoesNotExist:
            pass
        great_deal = raw.get('great_deal') or {}
        if great_deal.get('is_great_deal') and great_deal.get('badge_text'):
            badges.append({'type': 'great_deal', 'text': great_deal['badge_text']})
        signals['trust_badges'] = badges

        last_booked_ago = raw.get('last_booked_ago')
        if last_booked_ago is not None:
            if last_booked_ago < 60:
                text = f'Last booked {last_booked_ago} minute{"s" if last_booked_ago != 1 else ""} ago'
            else:
                hours = max(1, int(last_booked_ago / 60))
                text = f'Last booked {hours} hour{"s" if hours != 1 else ""} ago'
            signals['last_booked'] = {
                'show': True,
                'text': text,
                'urgency': 'high' if last_booked_ago < 60 else 'medium',
            }
        else:
            signals['last_booked'] = {'show': False}

        if viewing_now >= 2:
            signals['viewers_now'] = {
                'show': True,
                'text': f'{viewing_now} people viewing this now',
                'count': viewing_now,
                'urgency': 'high' if viewing_now >= 5 else 'medium',
            }
        else:
            signals['viewers_now'] = {'show': False}

        signals['summary'] = raw
        return signals

    @staticmethod
    def _scarcity_signal(property_obj, check_in, check_out):
        """Rooms remaining for the date range."""
        from apps.rooms.models import RoomInventory, RoomType

        room_types = RoomType.objects.filter(property=property_obj)
        min_available = None

        for rt in room_types:
            avail = RoomInventory.objects.filter(
                room_type=rt,
                date__gte=check_in,
                date__lt=check_out,
            ).order_by('available_rooms').first()

            if avail:
                if min_available is None or avail.available_rooms < min_available:
                    min_available = avail.available_rooms

        if min_available is not None and min_available <= 3:
            return {
                'show': True,
                'text': f'Only {min_available} room{"s" if min_available != 1 else ""} left!',
                'urgency': 'high' if min_available <= 1 else 'medium',
            }
        return {'show': False}

    @staticmethod
    def _popularity_signal(property_obj):
        """Recent booking count."""
        from apps.booking.models import Booking

        recent = Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'hold'],
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).count()

        if recent >= 3:
            return {
                'show': True,
                'text': f'Booked {recent} times in last 24 hours',
                'urgency': 'high',
            }
        elif recent >= 1:
            return {
                'show': True,
                'text': f'Booked {recent} time{"s" if recent > 1 else ""} today',
                'urgency': 'low',
            }
        return {'show': False}

    @staticmethod
    def _price_trend_signal(property_obj):
        """Price trend over last 30 days."""
        from apps.inventory.models import PriceHistory

        thirty_days = timezone.now() - timedelta(days=30)
        recent = PriceHistory.objects.filter(
            property=property_obj,
            created_at__gte=thirty_days,
        ).order_by('-created_at')[:2]

        if len(recent) >= 2:
            latest = recent[0].price
            previous = recent[1].price
            if latest < previous:
                return {
                    'show': True,
                    'text': 'Price dropped recently',
                    'direction': 'down',
                }
            elif latest > previous:
                return {
                    'show': True,
                    'text': 'Price rising — book now',
                    'direction': 'up',
                }
        return {'show': False}

    @staticmethod
    def _social_proof_signal(property_obj):
        """Review-based social proof."""
        review_count = getattr(property_obj, 'review_count', 0) or 0
        rating = float(getattr(property_obj, 'rating', 0) or 0)

        if review_count >= 50 and rating >= 4.0:
            return {
                'show': True,
                'text': f'Loved by guests — {rating}★ ({review_count} reviews)',
            }
        elif review_count >= 10:
            return {
                'show': True,
                'text': f'{review_count} verified reviews',
            }
        return {'show': False}

    @staticmethod
    def _last_booked_signal(property_obj):
        """Show 'Last booked X hours/minutes ago' for recent bookings."""
        from apps.booking.models import Booking

        last = Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'hold'],
        ).order_by('-created_at').values_list('created_at', flat=True).first()

        if not last:
            return {'show': False}

        now = timezone.now()
        delta = now - last
        hours = delta.total_seconds() / 3600

        if hours < 1:
            minutes = max(1, int(delta.total_seconds() / 60))
            return {
                'show': True,
                'text': f'Last booked {minutes} minute{"s" if minutes != 1 else ""} ago',
                'urgency': 'high',
            }
        elif hours < 24:
            h = int(hours)
            return {
                'show': True,
                'text': f'Last booked {h} hour{"s" if h != 1 else ""} ago',
                'urgency': 'medium' if h <= 3 else 'low',
            }
        elif hours < 72:
            days = int(hours / 24)
            return {
                'show': True,
                'text': f'Last booked {days} day{"s" if days != 1 else ""} ago',
                'urgency': 'low',
            }
        return {'show': False}

    @staticmethod
    def _viewers_now_signal(property_obj):
        """
        Estimate current viewers from recent analytics pageviews.
        Shows 'X people viewing this now' when there's active interest.
        """
        try:
            from apps.core.analytics import AnalyticsEvent
            # Count unique sessions viewing this property in last 15 minutes
            cutoff = timezone.now() - timedelta(minutes=15)
            viewer_count = AnalyticsEvent.objects.filter(
                property_id=property_obj.pk,
                event_type=AnalyticsEvent.EVENT_PROPERTY_VIEW,
                created_at__gte=cutoff,
            ).values('session_id').distinct().count()

            if viewer_count >= 2:
                return {
                    'show': True,
                    'text': f'{viewer_count} people viewing this now',
                    'count': viewer_count,
                    'urgency': 'high' if viewer_count >= 5 else 'medium',
                }
        except Exception:
            pass
        return {'show': False}
