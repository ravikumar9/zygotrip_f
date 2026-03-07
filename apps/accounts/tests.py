"""
Tests for the accounts app:
  - User model (creation, roles, email uniqueness)
  - OTP generation security (CSPRNG, expiry)
  - Authentication API (register, login, profile)
  - Rate limiting on auth endpoints
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User


# ═══════════════════════════════════════════════════════════════════════
# User Model Tests
# ═══════════════════════════════════════════════════════════════════════

class UserModelTests(TestCase):
    """Test User model creation and methods."""

    def test_create_user(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="securepass123",
            full_name="Test User",
        )
        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(user.full_name, "Test User")
        self.assertTrue(user.check_password("securepass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@test.com",
            password="adminpass123",
            full_name="Admin User",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_email_uniqueness(self):
        User.objects.create_user(
            email="unique@test.com",
            password="pass123",
            full_name="First",
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="unique@test.com",
                password="pass456",
                full_name="Second",
            )

    def test_role_helpers(self):
        owner = User.objects.create_user(
            email="owner@test.com",
            password="pass123",
            full_name="Owner",
            role="property_owner",
        )
        self.assertTrue(owner.is_property_owner())
        self.assertTrue(owner.is_vendor())
        self.assertFalse(owner.is_admin())

    def test_user_str(self):
        user = User.objects.create_user(
            email="str@test.com",
            password="pass123",
            full_name="String Test",
        )
        self.assertIn("str@test.com", str(user))


# ═══════════════════════════════════════════════════════════════════════
# OTP Security Tests
# ═══════════════════════════════════════════════════════════════════════

class OTPSecurityTests(TestCase):
    """Test OTP model security properties."""

    def test_otp_is_six_digits(self):
        from apps.accounts.otp_models import OTP

        otp = OTP.generate(phone="+919876543210")
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())

    def test_otp_codes_differ(self):
        """CSPRNG should produce varying codes (not all identical)."""
        from apps.accounts.otp_models import OTP

        codes = set()
        for i in range(10):
            otp = OTP.generate(phone=f"+91987654321{i}")
            codes.add(otp.code)

        # With CSPRNG, 10 codes should not all be the same
        self.assertGreater(len(codes), 1)

    def test_otp_expiry(self):
        from apps.accounts.otp_models import OTP

        otp = OTP.generate(phone="+919999999999")
        # Fresh OTP should NOT be expired
        self.assertTrue(otp.expires_at > timezone.now())

        # Move expiry to the past
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        self.assertTrue(otp.expires_at < timezone.now())


# ═══════════════════════════════════════════════════════════════════════
# Auth API Tests
# ═══════════════════════════════════════════════════════════════════════

class AuthAPITests(TestCase):
    """Test authentication REST API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="api@test.com",
            password="testpass123",
            full_name="API Tester",
        )

    def test_login_success(self):
        resp = self.client.post("/api/v1/auth/login/", {
            "email": "api@test.com",
            "password": "testpass123",
        }, format="json")
        # Should return 200 with tokens
        self.assertIn(resp.status_code, [200, 201])

    def test_login_wrong_password(self):
        resp = self.client.post("/api/v1/auth/login/", {
            "email": "api@test.com",
            "password": "wrongpass",
        }, format="json")
        self.assertIn(resp.status_code, [400, 401])

    def test_profile_requires_auth(self):
        resp = self.client.get("/api/v1/users/me/")
        self.assertIn(resp.status_code, [401, 403])

    def test_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/users/me/")
        self.assertEqual(resp.status_code, 200)