"""
Tests for new OTA intelligence systems:
  - PricingEngine (unified pricing with demand/loyalty/competitor)
  - Inventory Normalization
  - Demand Forecasting
  - Quality Scoring
  - Review Fraud Detection
  - Enhanced Ranking
  - Production Hardening (circuit breaker, health check)
"""
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.accounts.models import User


# ═══════════════════════════════════════════════════════════════════════
# Pricing Engine Tests
# ═══════════════════════════════════════════════════════════════════════

class PricingServiceTests(TestCase):
    """Test the canonical pricing_service calculations."""

    def test_gst_5_percent_slab(self):
        from apps.pricing.pricing_service import get_gst_rate
        rate = get_gst_rate(Decimal('5000'))
        self.assertEqual(rate, Decimal('0.05'))

    def test_gst_18_percent_slab(self):
        from apps.pricing.pricing_service import get_gst_rate
        rate = get_gst_rate(Decimal('8000'))
        self.assertEqual(rate, Decimal('0.18'))

    def test_gst_boundary_7500(self):
        from apps.pricing.pricing_service import get_gst_rate
        rate = get_gst_rate(Decimal('7500'))
        self.assertEqual(rate, Decimal('0.05'))

    def test_gst_just_above_boundary(self):
        from apps.pricing.pricing_service import get_gst_rate
        rate = get_gst_rate(Decimal('7501'))
        self.assertEqual(rate, Decimal('0.18'))

    def test_service_fee_capped_at_500(self):
        from apps.pricing.pricing_service import _q, _SERVICE_FEE_RATE, _SERVICE_FEE_CAP
        subtotal = Decimal('20000')
        fee = _q(subtotal * _SERVICE_FEE_RATE)
        if fee > _SERVICE_FEE_CAP:
            fee = _SERVICE_FEE_CAP
        self.assertEqual(fee, Decimal('500.00'))

    def test_service_fee_under_cap(self):
        from apps.pricing.pricing_service import _q, _SERVICE_FEE_RATE, _SERVICE_FEE_CAP
        subtotal = Decimal('5000')
        fee = _q(subtotal * _SERVICE_FEE_RATE)
        self.assertEqual(fee, Decimal('250.00'))

    def test_calculate_from_amounts_basic(self):
        from apps.pricing.pricing_service import calculate_from_amounts
        result = calculate_from_amounts(
            base_amount=Decimal('5000'),
            meal_amount=Decimal('0'),
            promo_discount=Decimal('0'),
            tariff_per_night=Decimal('5000'),
        )
        self.assertIn('total_amount', result)
        self.assertTrue(result['total_amount'] > Decimal('5000'))

    def test_calculate_from_amounts_with_promo(self):
        from apps.pricing.pricing_service import calculate_from_amounts
        result_no_promo = calculate_from_amounts(
            base_amount=Decimal('5000'),
            tariff_per_night=Decimal('5000'),
        )
        result_promo = calculate_from_amounts(
            base_amount=Decimal('5000'),
            promo_discount=Decimal('500'),
            tariff_per_night=Decimal('5000'),
        )
        self.assertTrue(result_promo['total_amount'] < result_no_promo['total_amount'])

    def test_calculate_from_amounts_negative_promo_clamped(self):
        """Promo discount cannot exceed base amount."""
        from apps.pricing.pricing_service import calculate_from_amounts
        result = calculate_from_amounts(
            base_amount=Decimal('5000'),
            promo_discount=Decimal('10000'),  # more than base
            tariff_per_night=Decimal('5000'),
        )
        # Subtotal should never be negative
        self.assertGreaterEqual(result['total_amount'], Decimal('0'))


# ═══════════════════════════════════════════════════════════════════════
# Pricing Engine (Unified) Tests
# ═══════════════════════════════════════════════════════════════════════

class PricingEngineAdvanceModifierTests(TestCase):
    """Test early-bird / last-minute pricing modifiers."""

    def test_early_bird_discount(self):
        from apps.pricing.engine import PricingEngine
        future = timezone.now().date() + timedelta(days=90)
        modifier = PricingEngine._get_advance_booking_modifier(future)
        self.assertEqual(modifier, Decimal('0.05'))

    def test_last_minute_surcharge(self):
        from apps.pricing.engine import PricingEngine
        tomorrow = timezone.now().date() + timedelta(days=1)
        modifier = PricingEngine._get_advance_booking_modifier(tomorrow)
        self.assertEqual(modifier, Decimal('-0.05'))

    def test_normal_advance_no_modifier(self):
        from apps.pricing.engine import PricingEngine
        two_weeks = timezone.now().date() + timedelta(days=14)
        modifier = PricingEngine._get_advance_booking_modifier(two_weeks)
        self.assertEqual(modifier, Decimal('0.00'))


class DemandSurgeTierTests(TestCase):
    """Test demand surge multiplier tiers."""

    def test_tiers_are_descending(self):
        from apps.pricing.engine import DEMAND_SURGE_TIERS
        thresholds = [t[0] for t in DEMAND_SURGE_TIERS]
        self.assertEqual(thresholds, sorted(thresholds, reverse=True))

    def test_high_occupancy_surge(self):
        from apps.pricing.engine import DEMAND_SURGE_TIERS
        # 96% occupancy → 15% surge
        for threshold, multiplier in DEMAND_SURGE_TIERS:
            if Decimal('0.96') >= threshold:
                self.assertEqual(multiplier, Decimal('1.15'))
                break


# ═══════════════════════════════════════════════════════════════════════
# Review Fraud Detection Tests
# ═══════════════════════════════════════════════════════════════════════

class ReviewFraudContentTests(TestCase):
    """Test review content analysis."""

    def test_short_content_flagged(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_review = MagicMock()
        mock_review.comment = 'Good'
        mock_review.user = None
        risk, details = ReviewFraudDetector._check_content(mock_review)
        self.assertGreater(risk, 0)
        self.assertIn('too_short', details)

    def test_normal_content_passes(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_review = MagicMock()
        mock_review.comment = 'The hotel was really nice. I enjoyed the pool and the breakfast was excellent. Would recommend!'
        mock_review.user = None
        risk, details = ReviewFraudDetector._check_content(mock_review)
        self.assertEqual(risk, 0)

    def test_all_caps_flagged(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_review = MagicMock()
        mock_review.comment = 'THIS HOTEL WAS ABSOLUTELY TERRIBLE AND I WILL NEVER COME BACK AGAIN EVER'
        mock_review.user = None
        risk, details = ReviewFraudDetector._check_content(mock_review)
        self.assertIn('all_caps', details)

    def test_repetitive_content_flagged(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_review = MagicMock()
        mock_review.comment = 'good good good good good good good good good good good good good good good good good good good good'
        mock_review.user = None
        risk, details = ReviewFraudDetector._check_content(mock_review)
        self.assertIn('low_unique_ratio', details)


class ReviewFraudAccountAgeTests(TestCase):
    """Test new account detection."""

    def test_new_account_flagged(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_user = MagicMock()
        mock_user.created_at = timezone.now() - timedelta(days=1)
        mock_review = MagicMock()
        mock_review.user = mock_user
        risk, details = ReviewFraudDetector._check_account_age(mock_review)
        self.assertGreater(risk, 0)

    def test_old_account_passes(self):
        from apps.hotels.review_fraud import ReviewFraudDetector
        mock_user = MagicMock()
        mock_user.created_at = timezone.now() - timedelta(days=365)
        mock_review = MagicMock()
        mock_review.user = mock_user
        risk, details = ReviewFraudDetector._check_account_age(mock_review)
        self.assertEqual(risk, 0)


# ═══════════════════════════════════════════════════════════════════════
# Quality Scoring Tests
# ═══════════════════════════════════════════════════════════════════════

class QualityScorerSatisfactionTests(TestCase):
    """Test guest satisfaction scoring."""

    def test_no_reviews_returns_neutral(self):
        from apps.core.intelligence import QualityScorer
        mock_prop = MagicMock()
        mock_prop.rating = 0
        mock_prop.review_count = 0
        score = QualityScorer._score_satisfaction(mock_prop)
        self.assertEqual(score, 40)

    def test_high_rating_high_score(self):
        from apps.core.intelligence import QualityScorer
        mock_prop = MagicMock()
        mock_prop.rating = 4.8
        mock_prop.review_count = 100
        score = QualityScorer._score_satisfaction(mock_prop)
        self.assertGreaterEqual(score, 80)

    def test_low_rating_low_score(self):
        from apps.core.intelligence import QualityScorer
        mock_prop = MagicMock()
        mock_prop.rating = 2.0
        mock_prop.review_count = 5
        score = QualityScorer._score_satisfaction(mock_prop)
        self.assertLess(score, 50)


# ═══════════════════════════════════════════════════════════════════════
# Circuit Breaker Tests
# ═══════════════════════════════════════════════════════════════════════

class CircuitBreakerTests(TestCase):
    """Test circuit breaker pattern."""

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_initial_state_closed(self):
        from apps.core.production import CircuitBreaker
        cb = CircuitBreaker('test_service', failure_threshold=3, timeout=10)
        self.assertTrue(cb.can_execute())

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_opens_after_threshold(self):
        from apps.core.production import CircuitBreaker
        cb = CircuitBreaker('test_service_2', failure_threshold=3, timeout=10)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        self.assertFalse(cb.can_execute())

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_success_resets(self):
        from apps.core.production import CircuitBreaker
        cb = CircuitBreaker('test_service_3', failure_threshold=3, timeout=10)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        self.assertTrue(cb.can_execute())


# ═══════════════════════════════════════════════════════════════════════
# Ranking Engine Tests
# ═══════════════════════════════════════════════════════════════════════

class RankingWeightTests(TestCase):
    """Test ranking weight configuration."""

    def test_weights_sum_to_one(self):
        from apps.core.ranking import (
            WEIGHT_RATING, WEIGHT_CONVERSION, WEIGHT_REVIEWS,
            WEIGHT_PRICE, WEIGHT_PHOTOS, WEIGHT_RECENCY,
            WEIGHT_QUALITY, WEIGHT_DEMAND, WEIGHT_FRESHNESS,
        )
        total = (
            WEIGHT_RATING + WEIGHT_CONVERSION + WEIGHT_REVIEWS +
            WEIGHT_PRICE + WEIGHT_PHOTOS + WEIGHT_RECENCY +
            WEIGHT_QUALITY + WEIGHT_DEMAND + WEIGHT_FRESHNESS
        )
        self.assertEqual(total, Decimal('1.00'))


# ═══════════════════════════════════════════════════════════════════════
# Analytics Tests
# ═══════════════════════════════════════════════════════════════════════

class AnalyticsFunnelTests(TestCase):
    """Test funnel metrics computation."""

    def test_funnel_returns_required_keys(self):
        from apps.core.analytics import get_funnel_metrics
        today = timezone.now().date()
        result = get_funnel_metrics(today - timedelta(days=7), today)
        self.assertIn('funnel', result)
        self.assertIn('conversion_rates', result)
        self.assertIn('searches', result['funnel'])
        self.assertIn('bookings_confirmed', result['funnel'])

    def test_property_analytics_returns_dict(self):
        from apps.core.analytics import get_property_analytics
        result = get_property_analytics(property_id=99999, days=30)
        self.assertIn('views', result)
        self.assertIn('conversion_rate', result)


# ═══════════════════════════════════════════════════════════════════════
# Health Check Tests
# ═══════════════════════════════════════════════════════════════════════

class HealthCheckTests(TestCase):
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        from apps.core.production import health_check
        factory = RequestFactory()
        request = factory.get('/api/v1/health/')
        response = health_check(request)
        self.assertEqual(response.status_code, 200)

    def test_health_check_json_structure(self):
        import json
        from apps.core.production import health_check
        factory = RequestFactory()
        request = factory.get('/api/v1/health/')
        response = health_check(request)
        data = json.loads(response.content)
        self.assertIn('status', data)
        self.assertIn('checks', data)
        self.assertIn('database', data['checks'])


# ═══════════════════════════════════════════════════════════════════════
# User Phone Uniqueness Tests
# ═══════════════════════════════════════════════════════════════════════

class UserPhoneUniquenessTests(TestCase):
    """Test that phone uniqueness constraint works."""

    def test_blank_phone_stored_as_null(self):
        user = User.objects.create_user(
            email='test_blank@example.com',
            password='testpass123',
            full_name='Test User',
            phone='',
        )
        user.refresh_from_db()
        self.assertIsNone(user.phone)

    def test_duplicate_phone_rejected(self):
        from django.db import IntegrityError
        User.objects.create_user(
            email='user1@example.com',
            password='testpass123',
            full_name='User 1',
            phone='9876543210',
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email='user2@example.com',
                password='testpass123',
                full_name='User 2',
                phone='9876543210',
            )

    def test_multiple_null_phones_allowed(self):
        User.objects.create_user(
            email='null1@example.com',
            password='testpass123',
            full_name='Null 1',
            phone='',
        )
        User.objects.create_user(
            email='null2@example.com',
            password='testpass123',
            full_name='Null 2',
            phone='',
        )
        # Both should exist with NULL phone
        self.assertEqual(
            User.objects.filter(phone__isnull=True, email__startswith='null').count(),
            2,
        )


# ═══════════════════════════════════════════════════════════════════════
# Conversion Signals Tests
# ═══════════════════════════════════════════════════════════════════════

class ConversionSignalTests(TestCase):
    """Test conversion optimization signals."""

    def test_social_proof_high_rated(self):
        from apps.core.intelligence import ConversionSignals
        mock_prop = MagicMock()
        mock_prop.review_count = 75
        mock_prop.rating = 4.5
        signal = ConversionSignals._social_proof_signal(mock_prop)
        self.assertTrue(signal['show'])
        self.assertIn('Loved by guests', signal['text'])

    def test_social_proof_no_reviews(self):
        from apps.core.intelligence import ConversionSignals
        mock_prop = MagicMock()
        mock_prop.review_count = 0
        mock_prop.rating = 0
        signal = ConversionSignals._social_proof_signal(mock_prop)
        self.assertFalse(signal['show'])
