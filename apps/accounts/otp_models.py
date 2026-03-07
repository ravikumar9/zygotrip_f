"""
OTP (One-Time Password) Model — Phone-based authentication.

Supports:
  - Login/register via phone number + OTP
  - Phone verification for existing accounts
  - Rate-limited: max 5 OTPs per phone per hour
  - Auto-expiry: 5 minutes
"""
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class OTP(TimeStampedModel):
    """
    One-time password record for phone-based auth.
    Each OTP is valid for 5 minutes and can be verified once.
    """
    phone = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20,
        choices=[
            ('login', 'Login / Register'),
            ('verify', 'Phone Verification'),
        ],
        default='login',
    )
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(
        default=0,
        help_text='Number of failed verification attempts',
    )
    max_attempts = models.IntegerField(default=5)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'purpose', '-created_at'], name='otp_phone_purpose_idx'),
        ]

    def __str__(self):
        return f"OTP {self.phone} ({self.purpose}) — {'verified' if self.is_verified else 'pending'}"

    @classmethod
    def generate(cls, phone: str, purpose: str = 'login') -> 'OTP':
        """
        Generate a new OTP. Invalidates previous unverified OTPs for same phone+purpose.
        Rate-limits to MAX_OTP_PER_HOUR per phone per hour.
        """
        max_per_hour = getattr(settings, 'MAX_OTP_PER_HOUR', 5)
        one_hour_ago = timezone.now() - timedelta(hours=1)

        recent_count = cls.objects.filter(
            phone=phone,
            purpose=purpose,
            created_at__gte=one_hour_ago,
        ).count()

        if recent_count >= max_per_hour:
            raise ValueError(f'Too many OTP requests. Please wait before trying again.')

        # Invalidate previous unverified OTPs — delete rather than marking
        # verified (is_verified=True means "successfully used", not "expired")
        cls.objects.filter(
            phone=phone, purpose=purpose, is_verified=False,
        ).delete()

        # Generate 6-digit code (use fixed code ONLY in DEBUG mode for testing)
        debug_code = getattr(settings, 'OTP_DEBUG_CODE', None)
        if debug_code and getattr(settings, 'DEBUG', False):
            import logging
            logging.getLogger('zygotrip').warning(
                'OTP_DEBUG_CODE active — this MUST NOT run in production'
            )
            code = str(debug_code)
        else:
            code = ''.join(secrets.choice(string.digits) for _ in range(6))

        otp = cls.objects.create(
            phone=phone,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(
                minutes=getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
            ),
        )
        return otp

    @classmethod
    def verify(cls, phone: str, code: str, purpose: str = 'login') -> bool:
        """
        Verify OTP code. Returns True if valid, False otherwise.
        Locks out after max_attempts failed tries.
        """
        try:
            otp = cls.objects.filter(
                phone=phone,
                purpose=purpose,
                is_verified=False,
                expires_at__gt=timezone.now(),
            ).latest('created_at')
        except cls.DoesNotExist:
            return False

        if otp.attempts >= otp.max_attempts:
            return False

        if otp.code != code:
            otp.attempts += 1
            otp.save(update_fields=['attempts', 'updated_at'])
            return False

        # Success
        otp.is_verified = True
        otp.save(update_fields=['is_verified', 'updated_at'])
        return True
