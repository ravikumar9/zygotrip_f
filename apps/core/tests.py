"""
Tests for the core OTA business systems:
  - Loyalty (earn / redeem / bonus / tier promotion)
  - Fraud Detection (booking risk, login risk)
  - Analytics (event tracking, daily metrics)
  - Referral (signup, completion)
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import City, Country, State
from apps.hotels.models import Property


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


class OTAVisiblePropertySignalsTests(TestCase):
    def test_selector_reads_live_search_index_signals(self):
        from apps.hotels.ota_selectors import ota_visible_properties
        from apps.search.models import PropertySearchIndex

        country = Country.objects.create(code='IN', name='India', display_name='India')
        state = State.objects.create(
            country=country,
            code='GA',
            name='Goa',
            display_name='Goa',
        )
        city = City.objects.create(
            state=state,
            code='GOI',
            name='Goa',
            display_name='Goa',
            slug='goa',
            latitude=Decimal('15.299326'),
            longitude=Decimal('74.123996'),
        )
        owner = User.objects.create_user(email='signals@test.com', password='test123')
        hotel = Property.objects.create(
            owner=owner,
            name='Signal Suites',
            slug='signal-suites',
            city=city,
            latitude=Decimal('15.299326'),
            longitude=Decimal('74.123996'),
            address='Candolim, Goa',
            description='Signal-rich property',
            status='approved',
            agreement_signed=True,
            bookings_today=1,
        )
        PropertySearchIndex.objects.update_or_create(
            property=hotel,
            defaults={
                'property_name': hotel.name,
                'slug': hotel.slug,
                'property_type': hotel.property_type,
                'city_id': city.id,
                'city_name': city.name,
                'latitude': hotel.latitude,
                'longitude': hotel.longitude,
                'recent_bookings': 7,
                'rooms_left': 3,
                'available_rooms': 9,
                'cashback_amount': Decimal('400.00'),
                'has_breakfast': True,
                'distance_km': Decimal('1.40'),
            },
        )

        selected = ota_visible_properties().get(pk=hotel.pk)

        self.assertEqual(selected.recent_bookings, 7)
        self.assertEqual(selected._available_rooms, 3)
        self.assertEqual(selected._cashback_amount, Decimal('400.00'))
        self.assertTrue(selected._has_breakfast)
        self.assertEqual(selected._distance_km, Decimal('1.40'))


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

    def test_payment_failure_ip_concentration_increases_risk(self):
        from apps.core.fraud_detection import assess_booking_risk, record_payment_failure

        baseline = assess_booking_risk(self.user, "5.6.7.8", Decimal("5000"))
        for _ in range(4):
            record_payment_failure(self.user, ip_address="9.9.9.9")

        elevated = assess_booking_risk(self.user, "9.9.9.9", Decimal("5000"))
        self.assertGreater(elevated["risk_score"], baseline["risk_score"])


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

    def test_track_event_normalizes_booking_attempt_alias(self):
        from apps.core.analytics import track_event, AnalyticsEvent

        track_event(
            event_type="booking_created",
            user=self.user,
            metadata={"amount": "9500.00"},
        )

        event = AnalyticsEvent.objects.get(user=self.user)
        self.assertEqual(event.event_type, AnalyticsEvent.EVENT_BOOKING_ATTEMPT)
        self.assertEqual(event.properties["amount"], "9500.00")

    def test_warehouse_export_task_publishes_stream_event(self):
        from unittest.mock import patch

        from apps.core.analytics import AnalyticsEvent
        from apps.core.analytics_tasks import _export_analytics_events_to_warehouse_impl

        event = AnalyticsEvent.objects.create(
            event_type=AnalyticsEvent.EVENT_HOTEL_CLICK,
            user=self.user,
            session_id="wh_123",
            property_id=42,
            city="Goa",
            properties={"source": "search_results"},
        )

        with patch('apps.core.event_bus.event_bus.publish') as publish_mock:
            result = _export_analytics_events_to_warehouse_impl(
                last_event_id=event.id - 1,
                batch_size=10,
            )

        self.assertEqual(result['exported'], 1)
        self.assertEqual(publish_mock.call_count, 1)
        published = publish_mock.call_args.args[0]
        self.assertEqual(published.event_type, 'analytics.warehouse_exported')
        self.assertEqual(published.payload['event_type'], AnalyticsEvent.EVENT_HOTEL_CLICK)


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


class GatewayRegistryTests(TestCase):
    """Test API gateway service discovery and tracing metadata."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_route_resolution_uses_service_boundaries(self):
        from apps.core.gateway_registry import resolve_api_version, resolve_service_name

        self.assertEqual(resolve_service_name('/api/v1/flights/search/'), 'flights')
        self.assertEqual(resolve_service_name('/api/v1/payment/webhook/'), 'payments')
        self.assertEqual(resolve_api_version('/api/v1/flights/search/'), 'v1')
        self.assertEqual(resolve_api_version('/api/search/'), 'legacy')

    def test_middleware_adds_gateway_headers(self):
        from apps.core.gateway_middleware import APIGatewayMiddleware

        request = self.factory.get('/api/v1/flights/search/')
        request.request_id = 'req-123'
        middleware = APIGatewayMiddleware(lambda req: HttpResponse('ok'))

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-API-Version'], 'v1')
        self.assertEqual(response['X-Service-Name'], 'flights')
        self.assertEqual(response['X-Request-ID'], 'req-123')
        self.assertIn('Server-Timing', response)

    def test_gateway_services_endpoint_returns_registry(self):
        response = self.client.get('/api/v1/gateway/services/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['gateway']['default_api_version'], 'v1')
        self.assertEqual(payload['request']['service'], 'gateway')

        services = {item['service'] for item in payload['services']}
        self.assertIn('booking', services)
        self.assertIn('payments', services)
        self.assertIn('flights', services)

    def test_canonical_ota_event_publishes_internal_topic(self):
        from unittest.mock import patch

        from apps.core.ota_events import BOOKING_CREATED, publish_ota_event

        with patch('apps.core.ota_events.event_bus.publish') as publish_mock:
            publish_ota_event(
                BOOKING_CREATED,
                payload={'booking_id': 99},
                user_id=7,
                source='test',
            )

        self.assertEqual(publish_mock.call_count, 1)
        event = publish_mock.call_args.args[0]
        self.assertEqual(event.event_type, 'booking.created')
        self.assertEqual(event.payload['ota_event'], BOOKING_CREATED)
        self.assertEqual(event.payload['booking_id'], 99)
        self.assertEqual(event.user_id, 7)

    def test_funnel_tracking_endpoint_records_event(self):
        from apps.core.analytics import AnalyticsEvent

        response = self.client.post(
            '/api/v1/analytics/funnel/track/',
            data={
                'session_id': 'fs_test_123',
                'stage': 'hotel_page_viewed',
                'stage_index': 1,
                'time_since_last': 4,
                'properties': {
                    'hotelId': 42,
                    'destination': 'Goa',
                },
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 202)
        event = AnalyticsEvent.objects.get(session_id='fs_test_123')
        self.assertEqual(event.event_type, AnalyticsEvent.EVENT_PROPERTY_VIEW)
        self.assertEqual(event.property_id, 42)
        self.assertEqual(event.city, 'Goa')
        self.assertEqual(event.properties['funnel_stage'], 'hotel_page_viewed')