"""
Tests for the core OTA business systems:
  - Loyalty (earn / redeem / bonus / tier promotion)
  - Fraud Detection (booking risk, login risk)
  - Analytics (event tracking, daily metrics)
  - Referral (signup, completion)
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User


# ═══════════════════════════════════════════════════════════════════════
# Loyalty System Tests
# ═══════════════════════════════════════════════════════════════════════

class LoyaltyTierTests(TestCase):
    """Test tier classification logic."""

    def test_bronze_default(self):
        from apps.core.loyalty import LoyaltyTier
        self.assertEqual(LoyaltyTier.for_points(0), "bronze")
        self.assertEqual(LoyaltyTier.for_points(4999), "bronze")

    def test_silver_threshold(self):
        from apps.core.loyalty import LoyaltyTier
        self.assertEqual(LoyaltyTier.for_points(5000), "silver")
        self.assertEqual(LoyaltyTier.for_points(14999), "silver")

    def test_gold_threshold(self):
        from apps.core.loyalty import LoyaltyTier
        self.assertEqual(LoyaltyTier.for_points(15000), "gold")

    def test_platinum_threshold(self):
        from apps.core.loyalty import LoyaltyTier
        self.assertEqual(LoyaltyTier.for_points(50000), "platinum")
        self.assertEqual(LoyaltyTier.for_points(999999), "platinum")


class LoyaltyEarnPointsTests(TestCase):
    """Test earning loyalty points."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="loyalty@test.com",
            password="testpass123",
            full_name="Loyalty Tester",
        )

    def test_earn_points_basic(self):
        from apps.core.loyalty import earn_points, get_or_create_loyalty_account

        points = earn_points(self.user, Decimal("5000"), reference_type="booking", reference_id="BK001")
        self.assertEqual(points, 500)  # 10 pts per 100 INR → 5000/100*10 = 500

        account = get_or_create_loyalty_account(self.user)
        self.assertEqual(account.available_points, 500)
        self.assertEqual(account.total_points_earned, 500)

    def test_earn_points_zero_amount(self):
        from apps.core.loyalty import earn_points
        points = earn_points(self.user, Decimal("0"))
        self.assertEqual(points, 0)

    def test_earn_points_creates_transaction(self):
        from apps.core.loyalty import earn_points, LoyaltyTransaction

        earn_points(self.user, Decimal("1000"))
        txns = LoyaltyTransaction.objects.filter(account__user=self.user, txn_type="earn")
        self.assertEqual(txns.count(), 1)
        self.assertEqual(txns.first().points, 100)

    def test_tier_upgrades_after_earning(self):
        from apps.core.loyalty import earn_points, get_or_create_loyalty_account

        # Earn enough for silver (5000 points = 50000 INR spend)
        earn_points(self.user, Decimal("50000"))
        account = get_or_create_loyalty_account(self.user)
        self.assertEqual(account.tier, "silver")


class LoyaltyRedeemPointsTests(TestCase):
    """Test redeeming loyalty points."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="redeem@test.com",
            password="testpass123",
            full_name="Redeem Tester",
        )

    def test_redeem_insufficient_points(self):
        from apps.core.loyalty import redeem_points, earn_points

        earn_points(self.user, Decimal("1000"))  # 100 points
        with self.assertRaises(ValueError):
            redeem_points(self.user, 500)  # Need 500 minimum

    def test_redeem_below_minimum(self):
        from apps.core.loyalty import redeem_points, earn_points

        earn_points(self.user, Decimal("100000"))  # 10000 points
        with self.assertRaises(ValueError):
            redeem_points(self.user, 100)  # Below 500 minimum

    def test_redeem_success(self):
        from apps.core.loyalty import redeem_points, earn_points, get_or_create_loyalty_account

        earn_points(self.user, Decimal("100000"))  # 10000 points
        discount = redeem_points(self.user, 500)
        self.assertEqual(discount, Decimal("50"))  # 500/100 * 10 = ₹50

        account = get_or_create_loyalty_account(self.user)
        self.assertEqual(account.available_points, 9500)


class LoyaltyBonusTests(TestCase):
    """Test bonus points awards."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="bonus@test.com",
            password="testpass123",
            full_name="Bonus Tester",
        )

    def test_award_bonus(self):
        from apps.core.loyalty import award_bonus, get_or_create_loyalty_account

        award_bonus(self.user, 250, "Welcome bonus")
        account = get_or_create_loyalty_account(self.user)
        self.assertEqual(account.available_points, 250)
        self.assertEqual(account.total_points_earned, 250)


# ═══════════════════════════════════════════════════════════════════════
# Fraud Detection Tests
# ═══════════════════════════════════════════════════════════════════════

class FraudBookingRiskTests(TestCase):
    """Test booking fraud risk assessment."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="fraud@test.com",
            password="testpass123",
            full_name="Fraud Tester",
        )

    def test_low_risk_normal_booking(self):
        from apps.core.fraud_detection import assess_booking_risk

        result = assess_booking_risk(
            user=self.user,
            ip_address="192.168.1.10",
            amount=Decimal("5000"),
        )
        self.assertIn("risk_score", result)
        self.assertIn("action", result)
        self.assertIn(result["action"], ["allow", "flag", "require_verification", "block"])

    def test_high_amount_increases_risk(self):
        from apps.core.fraud_detection import assess_booking_risk

        low = assess_booking_risk(self.user, "1.2.3.4", Decimal("1000"))
        high = assess_booking_risk(self.user, "1.2.3.4", Decimal("500000"))
        # Very high amount should produce a higher risk score
        self.assertGreaterEqual(high["risk_score"], low["risk_score"])

    def test_creates_fraud_flag_on_high_risk(self):
        from apps.core.fraud_detection import assess_booking_risk, FraudFlag

        # Record multiple payment failures to spike velocity scoring
        from apps.core.fraud_detection import record_payment_failure
        for _ in range(6):
            record_payment_failure(self.user)

        result = assess_booking_risk(self.user, "1.2.3.4", Decimal("200000"))
        # Should have created a FraudFlag record
        flags = FraudFlag.objects.filter(user=self.user)
        self.assertTrue(flags.exists())


class FraudLoginRiskTests(TestCase):
    """Test login fraud risk assessment."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="loginrisk@test.com",
            password="testpass123",
            full_name="Login Tester",
        )

    def test_normal_login_low_risk(self):
        from apps.core.fraud_detection import assess_login_risk

        result = assess_login_risk("10.0.0.1", self.user.email)
        self.assertIn("risk_score", result)
        self.assertEqual(result["action"], "allow")


# ═══════════════════════════════════════════════════════════════════════
# Analytics Tests
# ═══════════════════════════════════════════════════════════════════════

class AnalyticsTrackEventTests(TestCase):
    """Test event tracking."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="analytics@test.com",
            password="testpass123",
            full_name="Analytics Tester",
        )

    def test_track_search_event(self):
        from apps.core.analytics import track_event, AnalyticsEvent

        track_event(
            event_type="search",
            user=self.user,
            properties={"destination": "Goa", "checkin": "2025-08-01"},
        )
        events = AnalyticsEvent.objects.filter(user=self.user, event_type="search")
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().properties["destination"], "Goa")

    def test_track_event_multiple(self):
        from apps.core.analytics import track_event, AnalyticsEvent

        track_event(
            event_type="property_view",
            user=self.user,
            properties={"property_id": 42},
        )
        events = AnalyticsEvent.objects.filter(user=self.user, event_type="property_view")
        self.assertEqual(events.count(), 1)


class AnalyticsDailyMetricsTests(TestCase):
    """Test daily metrics computation."""

    def test_compute_daily_metrics_no_data(self):
        from apps.core.analytics import compute_daily_metrics, DailyMetrics

        # Explicitly pass today's date (default is yesterday)
        today = timezone.now().date()
        compute_daily_metrics(date=today)
        self.assertTrue(DailyMetrics.objects.filter(date=today).exists())


# ═══════════════════════════════════════════════════════════════════════
# Referral Tests
# ═══════════════════════════════════════════════════════════════════════

class ReferralTests(TestCase):
    """Test referral system."""

    def setUp(self):
        self.referrer = User.objects.create_user(
            email="referrer@test.com",
            password="testpass123",
            full_name="Referrer",
        )
        self.referee = User.objects.create_user(
            email="referee@test.com",
            password="testpass123",
            full_name="Referee",
        )

    def test_referral_profile_creation(self):
        from apps.core.referral import ReferralProfile

        profile, created = ReferralProfile.objects.get_or_create(user=self.referrer)
        self.assertTrue(created)
        self.assertIsNotNone(profile.referral_code)
        self.assertTrue(len(profile.referral_code) > 0)

    def test_process_referral_signup(self):
        from apps.core.referral import ReferralProfile, process_referral_signup, Referral

        profile = ReferralProfile.objects.create(user=self.referrer)
        result = process_referral_signup(self.referee, profile.referral_code)
        self.assertTrue(result)

        referrals = Referral.objects.filter(referrer=self.referrer, referee=self.referee)
        self.assertEqual(referrals.count(), 1)

    def test_duplicate_referral_rejected(self):
        from apps.core.referral import ReferralProfile, process_referral_signup

        profile = ReferralProfile.objects.create(user=self.referrer)
        process_referral_signup(self.referee, profile.referral_code)
        # Second attempt should fail
        result = process_referral_signup(self.referee, profile.referral_code)
        self.assertFalse(result)

    def test_self_referral_rejected(self):
        from apps.core.referral import ReferralProfile, process_referral_signup

        profile = ReferralProfile.objects.create(user=self.referrer)
        result = process_referral_signup(self.referrer, profile.referral_code)
        self.assertFalse(result)