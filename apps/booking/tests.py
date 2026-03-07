"""
Tests for the booking app:
  - Booking service (inventory check, date range, idempotency)
  - Booking model states and transitions
  - Booking API endpoints
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User


# ═══════════════════════════════════════════════════════════════════════
# Booking Service Unit Tests
# ═══════════════════════════════════════════════════════════════════════

class BookingDateRangeTests(TestCase):
    """Test the internal _date_range helper."""

    def test_date_range_normal(self):
        from apps.booking.services import _date_range

        dates = list(_date_range(date(2025, 8, 1), date(2025, 8, 4)))
        self.assertEqual(len(dates), 3)  # 1, 2, 3 (check-out excluded)
        self.assertEqual(dates[0], date(2025, 8, 1))
        self.assertEqual(dates[-1], date(2025, 8, 3))

    def test_date_range_same_day(self):
        from apps.booking.services import _date_range

        dates = list(_date_range(date(2025, 8, 1), date(2025, 8, 1)))
        self.assertEqual(len(dates), 0)


class BookingServiceEdgeCaseTests(TestCase):
    """Test booking service edge cases."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="booker@test.com",
            password="testpass123",
            full_name="Booking Tester",
        )

    def test_booking_requires_property(self):
        """Booking without a property should raise an error."""
        from apps.booking.services import create_booking

        with self.assertRaises(Exception):
            create_booking(
                user=self.user,
                property_obj=None,
                room_type=None,
                check_in=date.today() + timedelta(days=1),
                check_out=date.today() + timedelta(days=3),
                rooms=1,
                guests=[{"name": "Test Guest"}],
            )


# ═══════════════════════════════════════════════════════════════════════
# Booking API Tests
# ═══════════════════════════════════════════════════════════════════════

class BookingAPITests(TestCase):
    """Test booking REST endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="bookapi@test.com",
            password="testpass123",
            full_name="Book API Tester",
        )

    def test_my_bookings_requires_auth(self):
        resp = self.client.get("/api/v1/booking/my/")
        self.assertIn(resp.status_code, [401, 403])

    def test_my_bookings_empty(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/booking/my/")
        self.assertEqual(resp.status_code, 200)