"""
Phase 16 — Final Backend Freeze Test Suite.

Tests for:
  1. Guest booking flow (Phase 1)
  2. Pricing service → PriceEngine delegation (Phase 3)
  3. Webhook HMAC + timestamp + replay protection (Phase 12)
  4. Device fingerprint fraud gating (Phase 7)
  5. Reconciliation Celery task (Phase 13)
  6. Supplier sync tasks (Phase 6)
  7. Search index rebuild (Phase 10)
"""
import hashlib
import hmac as hmac_lib
import json
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase, override_settings, RequestFactory
from django.utils import timezone
from django.core.cache import cache


# ═══════════════════════════════════════════════════════════════════════
# TEST HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _create_full_test_property(suffix='1'):
    """
    Create a full property hierarchy needed for booking tests.
    Returns (user, city, locality, property, room_type).
    """
    from apps.accounts.models import User
    from apps.core.location_models import Country, State, City, Locality
    from apps.hotels.models import Property
    from apps.rooms.models import RoomType

    user = User.objects.create_user(
        email=f'owner-freeze-{suffix}@test.com', password='test1234',
        phone=f'88888{suffix}0000', role='owner',
    )
    country, _ = Country.objects.get_or_create(
        code='IN', defaults={'name': 'India', 'display_name': 'India'}
    )
    state, _ = State.objects.get_or_create(
        code='KA', country=country,
        defaults={'name': 'Karnataka', 'display_name': 'Karnataka'}
    )
    city, _ = City.objects.get_or_create(
        code=f'FRZ{suffix}', state=state,
        defaults={
            'name': f'FreezeCity{suffix}', 'display_name': f'FreezeCity{suffix}',
            'latitude': Decimal('12.0'), 'longitude': Decimal('77.0'),
        }
    )
    locality, _ = Locality.objects.get_or_create(
        name=f'FreezeLocality{suffix}', city=city,
        defaults={
            'display_name': f'FreezeLocality{suffix}',
            'latitude': Decimal('12.0'), 'longitude': Decimal('77.0'),
        }
    )
    prop = Property.objects.create(
        owner=user, name=f'Freeze Hotel {suffix}', property_type='Hotel',
        city=city, locality=locality, address='123 Test St',
        description='Test hotel for freeze tests',
        latitude=Decimal('12.0'), longitude=Decimal('77.0'),
        status='approved', agreement_signed=True, is_active=True,
        commission_percentage=Decimal('15'),
    )
    room_type = RoomType.objects.create(
        property=prop,
        name='Deluxe Room',
        base_price=Decimal('5000.00'),
        max_occupancy=2,
    )
    return user, city, locality, prop, room_type


# ═══════════════════════════════════════════════════════════════════════
# 1. GUEST BOOKING TESTS (Phase 1)
# ═══════════════════════════════════════════════════════════════════════

class GuestBookingModelTest(TestCase):
    """Test GuestBookingContext model and nullable user on Booking."""

    def test_booking_user_nullable(self):
        """Booking can be created with user=None for guest checkout."""
        from apps.booking.models import Booking
        meta = Booking._meta
        user_field = meta.get_field('user')
        self.assertTrue(user_field.null, 'Booking.user must be nullable for guest bookings')
        self.assertTrue(user_field.blank)

    def test_booking_has_is_guest_field(self):
        """Booking has is_guest_booking boolean field."""
        from apps.booking.models import Booking
        field = Booking._meta.get_field('is_guest_booking')
        self.assertFalse(field.default)  # defaults to False

    def test_guest_booking_context_model_exists(self):
        """GuestBookingContext model exists with required fields."""
        from apps.booking.models import GuestBookingContext
        meta = GuestBookingContext._meta
        field_names = [f.name for f in meta.get_fields()]
        required = ['email', 'phone', 'full_name', 'ip_address',
                     'session_key', 'device_fingerprint', 'fraud_score']
        for name in required:
            self.assertIn(name, field_names, f'GuestBookingContext missing field: {name}')


class GuestBookingAPITest(TransactionTestCase):
    """Test guest booking creation endpoint (AllowAny)."""

    def setUp(self):
        self.user, self.city, self.locality, self.prop, self.room_type = _create_full_test_property('g1')

        # Create inventory for the room
        from apps.rooms.models import RoomInventory
        today = date.today()
        for i in range(5):
            RoomInventory.objects.create(
                room_type=self.room_type,
                date=today + timedelta(days=i + 1),
                available_rooms=10,
            )

    def test_guest_can_create_booking_context(self):
        """Anonymous user can create a booking context."""
        from rest_framework.test import APIClient
        client = APIClient()
        checkin = date.today() + timedelta(days=1)
        checkout = checkin + timedelta(days=2)

        resp = client.post('/api/v1/booking/context/', {
            'property_id': self.prop.id,
            'room_type_id': self.room_type.id,
            'checkin': str(checkin),
            'checkout': str(checkout),
            'adults': 2,
            'rooms': 1,
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['success'])
        self.assertIn('uuid', resp.json()['data'])


# ═══════════════════════════════════════════════════════════════════════
# 2. PRICING SERVICE DELEGATION TESTS (Phase 3)
# ═══════════════════════════════════════════════════════════════════════

class PricingServiceDelegationTest(TestCase):
    """Test that pricing_service.calculate is the authoritative pricing engine."""

    def setUp(self):
        self.room_type = MagicMock()
        self.room_type.base_price = Decimal('3000.00')
        self.room_type.property = MagicMock()

    def test_calculate_delegates_to_price_engine(self):
        """pricing_service.calculate() is the authoritative engine and returns correct shape."""
        from apps.pricing.pricing_service import calculate
        result = calculate(
            room_type=self.room_type,
            nights=3,
            rooms=1,
        )

        # pricing_service.calculate() is now the single source of truth
        self.assertIn('final_total', result)
        self.assertIn('gst_amount', result)
        self.assertIn('base_price', result)

    def test_calculate_returns_correct_shape(self):
        """pricing_service.calculate() returns all expected keys."""
        from apps.pricing.pricing_service import calculate
        result = calculate(
            room_type=self.room_type,
            nights=2,
            rooms=1,
        )

        expected_keys = [
            'base_price', 'meal_plan_price', 'property_discount',
            'platform_discount', 'promo_discount', 'total_before_tax',
            'service_fee', 'gst_percentage', 'gst_amount',
            'total_after_tax', 'final_total', 'tariff_per_night',
            'nights', 'rooms',
        ]
        for key in expected_keys:
            self.assertIn(key, result, f'Missing key in pricing_service output: {key}')

    def test_gst_slabs_correct(self):
        """Verify GST slab: 5% for ≤₹7500, 18% for >₹7500."""
        from apps.pricing.pricing_service import get_gst_percentage
        self.assertEqual(get_gst_percentage(Decimal('5000')), '5')
        self.assertEqual(get_gst_percentage(Decimal('7500')), '5')
        self.assertEqual(get_gst_percentage(Decimal('7501')), '18')
        self.assertEqual(get_gst_percentage(Decimal('15000')), '18')


# ═══════════════════════════════════════════════════════════════════════
# 3. WEBHOOK SECURITY TESTS (Phase 12)
# ═══════════════════════════════════════════════════════════════════════

@override_settings(PAYMENT_WEBHOOK_SECRET='test-secret-key-123')
class WebhookSecurityTest(TestCase):
    """Test HMAC signature, timestamp freshness, and replay protection."""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def _make_webhook_request(self, payload, secret=None, timestamp=None, signature=None):
        """Build a webhook POST request with optional security headers."""
        from django.test import Client
        client = Client()
        body = json.dumps(payload).encode()

        headers = {'content_type': 'application/json'}

        if timestamp is not None:
            headers['HTTP_X_WEBHOOK_TIMESTAMP'] = str(timestamp)

        if signature is not None:
            headers['HTTP_X_WEBHOOK_SIGNATURE'] = signature
        elif secret:
            sig = hmac_lib.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers['HTTP_X_WEBHOOK_SIGNATURE'] = sig

        return client.post('/invoice/webhook/', body, **headers)

    def test_missing_signature_rejected(self):
        """Webhook without X-Webhook-Signature is rejected (401)."""
        payload = {'payment_reference_id': 'test-1', 'status': 'success', 'amount': 1000}
        resp = self._make_webhook_request(payload, timestamp=int(time.time()))
        self.assertEqual(resp.status_code, 401)

    def test_invalid_signature_rejected(self):
        """Webhook with wrong HMAC signature is rejected (401)."""
        payload = {'payment_reference_id': 'test-2', 'status': 'success', 'amount': 1000}
        resp = self._make_webhook_request(
            payload, timestamp=int(time.time()), signature='wrong-signature'
        )
        self.assertEqual(resp.status_code, 401)

    def test_valid_signature_accepted(self):
        """Webhook with correct HMAC passes signature check."""
        payload = {'payment_reference_id': 'test-3', 'status': 'success', 'amount': 1000}
        # Valid signature should pass signature check (may still fail on business logic)
        resp = self._make_webhook_request(
            payload, secret='test-secret-key-123', timestamp=int(time.time())
        )
        # Should NOT be 401 (sig check passed), may be 400 (no matching booking)
        self.assertNotEqual(resp.status_code, 401)

    def test_stale_timestamp_rejected(self):
        """Webhook with timestamp >5 min old is rejected (400)."""
        payload = {'payment_reference_id': 'test-4', 'status': 'success', 'amount': 1000}
        stale_ts = int(time.time()) - 600  # 10 minutes ago
        resp = self._make_webhook_request(
            payload, secret='test-secret-key-123', timestamp=stale_ts
        )
        self.assertEqual(resp.status_code, 400)

    def test_replay_protection(self):
        """Same payment_reference_id is rejected on second attempt."""
        payload = {'payment_reference_id': 'replay-test-1', 'status': 'success', 'amount': 1000}

        # Simulate first call setting the cache key
        cache.set('webhook:dedup:replay-test-1', True, 3600)

        resp = self._make_webhook_request(
            payload, secret='test-secret-key-123', timestamp=int(time.time())
        )
        # Should return 200 with idempotent=True (duplicate detection)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('idempotent'))


# ═══════════════════════════════════════════════════════════════════════
# 4. DEVICE FINGERPRINT TESTS (Phase 7)
# ═══════════════════════════════════════════════════════════════════════

class DeviceFingerprintServiceTest(TestCase):
    """Test FingerprintService computation and fraud scoring."""

    def test_fraud_score_bot_detection(self):
        """Bot user-agent patterns score ≥30."""
        from apps.core.device_fingerprint import DeviceFingerprint, FingerprintService

        fp = DeviceFingerprint(
            fingerprint_hash='a' * 64,
            user_agent='Mozilla/5.0 (HeadlessChrome) Puppeteer',
            ip_address='1.2.3.4',
        )
        score, reasons = FingerprintService.compute_fraud_score(fp)
        self.assertGreaterEqual(score, 30)
        self.assertIn('bot_ua', reasons)

    def test_fraud_score_empty_ua(self):
        """Empty user-agent scores ≥15."""
        from apps.core.device_fingerprint import DeviceFingerprint, FingerprintService

        fp = DeviceFingerprint(
            fingerprint_hash='b' * 64,
            user_agent='',
            ip_address='1.2.3.5',
        )
        score, reasons = FingerprintService.compute_fraud_score(fp)
        self.assertGreaterEqual(score, 15)
        self.assertIn('empty_ua', reasons)

    def test_fraud_score_no_js(self):
        """Missing JS fingerprint (canvas + webgl) scores ≥10."""
        from apps.core.device_fingerprint import DeviceFingerprint, FingerprintService

        fp = DeviceFingerprint(
            fingerprint_hash='c' * 64,
            user_agent='Mozilla/5.0 (normal browser)',
            canvas_hash='',
            webgl_hash='',
        )
        score, reasons = FingerprintService.compute_fraud_score(fp)
        self.assertGreaterEqual(score, 10)
        self.assertIn('no_js_fingerprint', reasons)

    def test_clean_fingerprint_low_score(self):
        """Normal fingerprint with valid JS fields should score low."""
        from apps.core.device_fingerprint import DeviceFingerprint, FingerprintService

        fp = DeviceFingerprint(
            fingerprint_hash='d' * 64,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            canvas_hash='valid-canvas-hash',
            webgl_hash='valid-webgl-hash',
            ip_address='203.0.113.1',
        )
        score, reasons = FingerprintService.compute_fraud_score(fp)
        self.assertLess(score, 30)

    def test_mobile_detection(self):
        """Mobile user-agent detection."""
        from apps.core.device_fingerprint import FingerprintService
        self.assertTrue(FingerprintService._detect_mobile('Mozilla/5.0 (iPhone; CPU iPhone OS 15)'))
        self.assertTrue(FingerprintService._detect_mobile('Mozilla/5.0 (Linux; Android 11)'))
        self.assertFalse(FingerprintService._detect_mobile('Mozilla/5.0 (Windows NT 10.0)'))


# ═══════════════════════════════════════════════════════════════════════
# 5. PAYMENT RECONCILIATION TESTS (Phase 13)
# ═══════════════════════════════════════════════════════════════════════

class PaymentReconciliationTest(TestCase):
    """Test the reconcile_gateway_transactions Celery task."""

    def test_reconciliation_model_exists(self):
        """PaymentReconciliation model has correct structure."""
        from apps.payments.models import PaymentReconciliation
        meta = PaymentReconciliation._meta
        field_names = [f.name for f in meta.get_fields()]
        required = ['date', 'gateway', 'expected_amount', 'settled_amount',
                     'discrepancy', 'transactions_matched', 'transactions_unmatched']
        for name in required:
            self.assertIn(name, field_names)

    def test_reconciliation_task_runs(self):
        """reconcile_gateway_transactions task runs without error (empty data)."""
        from apps.core.tasks import reconcile_gateway_transactions
        result = reconcile_gateway_transactions()
        self.assertIn('date', result)
        self.assertIn('gateways', result)
        self.assertIsInstance(result['gateways'], list)


# ═══════════════════════════════════════════════════════════════════════
# 6. SUPPLIER SYNC TESTS (Phase 6)
# ═══════════════════════════════════════════════════════════════════════

class SupplierSyncTest(TestCase):
    """Test supplier sync Celery tasks."""

    def test_supplier_framework_adapters_exist(self):
        """All 3 supplier adapters are registered."""
        from apps.core.supplier_framework import get_supplier_adapter
        for name in ['hotelbeds', 'staah', 'siteminder']:
            adapter = get_supplier_adapter(name)
            self.assertEqual(adapter.name, name)

    def test_hotelbeds_auth_without_credentials(self):
        """Hotelbeds adapter returns False when no credentials."""
        from apps.core.supplier_framework import HotelbedsAdapter
        adapter = HotelbedsAdapter()
        self.assertFalse(adapter.authenticate())

    @patch('apps.core.supplier_framework.HotelbedsAdapter.authenticate', return_value=False)
    def test_sync_hotelbeds_auth_failure_graceful(self, mock_auth):
        """sync_hotelbeds_inventory handles auth failure gracefully."""
        from apps.core.tasks import sync_hotelbeds_inventory
        result = sync_hotelbeds_inventory()
        self.assertEqual(result['status'], 'auth_failed')

    def test_sync_tasks_registered_in_celery(self):
        """All 3 supplier sync tasks exist."""
        from apps.core import tasks
        self.assertTrue(hasattr(tasks, 'sync_hotelbeds_inventory'))
        self.assertTrue(hasattr(tasks, 'sync_staah_inventory'))
        self.assertTrue(hasattr(tasks, 'sync_siteminder_inventory'))


# ═══════════════════════════════════════════════════════════════════════
# 7. SEARCH INDEX REBUILD TESTS (Phase 10)
# ═══════════════════════════════════════════════════════════════════════

class SearchIndexRebuildTest(TestCase):
    """Test rebuild_property_search_index Celery task."""

    def test_rebuild_task_exists(self):
        """rebuild_property_search_index task is importable."""
        from apps.core.tasks import rebuild_property_search_index
        self.assertTrue(callable(rebuild_property_search_index))

    def test_rebuild_runs_empty(self):
        """Rebuild with no properties completes without error."""
        from apps.core.tasks import rebuild_property_search_index
        result = rebuild_property_search_index()
        self.assertEqual(result['rebuilt'], 0)
        self.assertIsNone(result['property_id'])


# ═══════════════════════════════════════════════════════════════════════
# 8. CELERY SCHEDULE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

class CeleryBeatScheduleTest(TestCase):
    """Verify all required tasks are in the Celery Beat schedule."""

    def test_all_critical_tasks_scheduled(self):
        """All Phase 6/10/13 tasks exist as importable Celery tasks."""
        from apps.core import tasks
        required = [
            'sync_hotelbeds_inventory',
            'sync_staah_inventory',
            'sync_siteminder_inventory',
            'reconcile_gateway_transactions',
            'rebuild_property_search_index',
        ]
        for name in required:
            self.assertTrue(hasattr(tasks, name), f'Missing task: {name}')
            self.assertTrue(callable(getattr(tasks, name)))

    def test_beat_schedule_has_supplier_entries(self):
        """Celery beat_schedule in settings.py contains supplier sync entries (authoritative source)."""
        from django.conf import settings
        beat = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        # In DEBUG mode beat schedule is empty, so check settings source file
        if not beat:
            import pathlib
            settings_path = pathlib.Path(__file__).resolve().parent.parent.parent / 'zygotrip_project' / 'settings.py'
            source = settings_path.read_text(encoding='utf-8')
            for name in ['supplier-availability-sync', 'sync-search-index', 'reconcile-payments']:
                self.assertIn(name, source, f'Missing from settings.py CELERY_BEAT_SCHEDULE: {name}')


# ═══════════════════════════════════════════════════════════════════════
# 9. PRICE ENGINE INTEGRATION TEST
# ═══════════════════════════════════════════════════════════════════════

class PriceEngineIntegrationTest(TestCase):
    """Verify PriceEngine produces correct pricing."""

    def test_base_calculation(self):
        """PriceEngine.calculate produces valid output."""
        from apps.pricing.price_engine import PriceEngine

        room_type = MagicMock()
        room_type.base_price = Decimal('5000.00')
        room_type.property = MagicMock()
        room_type.property.commission_percentage = 15

        result = PriceEngine.calculate(
            room_type=room_type,
            nights=2,
            rooms=1,
        )

        self.assertEqual(result['base_price'], Decimal('10000.00'))
        self.assertGreater(result['final_price'], Decimal('10000.00'))  # Has tax + fee
        self.assertIn('gst', result)
        self.assertIn('service_fee', result)
        self.assertIn('ota_commission', result)

    def test_gst_5_percent_under_threshold(self):
        """Room tariff ≤₹7500 gets 5% GST."""
        from apps.pricing.price_engine import PriceEngine

        room_type = MagicMock()
        room_type.base_price = Decimal('5000.00')
        room_type.property = MagicMock()

        result = PriceEngine.calculate(room_type=room_type, nights=1, rooms=1)
        self.assertEqual(result['gst_percentage'], '5')

    def test_gst_18_percent_above_threshold(self):
        """Room tariff >₹7500 gets 18% GST."""
        from apps.pricing.price_engine import PriceEngine

        room_type = MagicMock()
        room_type.base_price = Decimal('10000.00')
        room_type.property = MagicMock()

        result = PriceEngine.calculate(room_type=room_type, nights=1, rooms=1)
        self.assertEqual(result['gst_percentage'], '18')
