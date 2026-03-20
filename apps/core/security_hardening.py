"""
Security Hardening — OTP Abuse Protection, Login Brute-Force, Admin Guard.

Provides:
  1. OTPRateGuard — per-phone and per-IP OTP throttling with lockout
  2. LoginAttemptTracker — brute-force login detection and lockout
  3. AdminIPAllowlist — restrict admin panel to known IPs
  4. SecurityMiddleware — plugs into Django middleware stack
"""
import hashlib
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.security')


def _redis():
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception:
        return None


# ============================================================================
# OTP Abuse Protection
# ============================================================================

class OTPRateGuard:
    """
    Redis-backed OTP rate limiter.

    Limits:
      - Per phone: 5 OTP requests / 10 minutes
      - Per IP: 10 OTP requests / 10 minutes
      - Lockout: 30 minutes after exceeding limits
    """

    PHONE_LIMIT = 5
    IP_LIMIT = 10
    WINDOW_SECONDS = 600       # 10 minutes
    LOCKOUT_SECONDS = 1800     # 30 minutes
    KEY_PREFIX = 'otp_guard'

    @classmethod
    def check_allowed(cls, phone=None, ip_address=None):
        """
        Check if OTP request is allowed.
        Returns (allowed: bool, detail: str, retry_after: int)
        """
        r = _redis()
        if not r:
            return True, 'OK', 0

        now = int(time.time())

        # Check lockout
        if phone:
            lockout_key = f'{cls.KEY_PREFIX}:lockout:phone:{phone}'
            if r.exists(lockout_key):
                ttl = r.ttl(lockout_key) or cls.LOCKOUT_SECONDS
                return False, 'Too many OTP requests. Try again later.', ttl

        if ip_address:
            lockout_key = f'{cls.KEY_PREFIX}:lockout:ip:{ip_address}'
            if r.exists(lockout_key):
                ttl = r.ttl(lockout_key) or cls.LOCKOUT_SECONDS
                return False, 'Too many OTP requests from this IP. Try again later.', ttl

        # Check rate limits
        if phone:
            phone_key = f'{cls.KEY_PREFIX}:rate:phone:{phone}'
            count = r.get(phone_key)
            if count and int(count) >= cls.PHONE_LIMIT:
                # Trigger lockout
                r.setex(f'{cls.KEY_PREFIX}:lockout:phone:{phone}',
                        cls.LOCKOUT_SECONDS, 1)
                return False, 'OTP limit exceeded for this phone number.', cls.LOCKOUT_SECONDS

        if ip_address:
            ip_key = f'{cls.KEY_PREFIX}:rate:ip:{ip_address}'
            count = r.get(ip_key)
            if count and int(count) >= cls.IP_LIMIT:
                r.setex(f'{cls.KEY_PREFIX}:lockout:ip:{ip_address}',
                        cls.LOCKOUT_SECONDS, 1)
                return False, 'OTP limit exceeded for this IP.', cls.LOCKOUT_SECONDS

        return True, 'OK', 0

    @classmethod
    def record_attempt(cls, phone=None, ip_address=None):
        """Record an OTP send attempt."""
        r = _redis()
        if not r:
            return

        if phone:
            key = f'{cls.KEY_PREFIX}:rate:phone:{phone}'
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, cls.WINDOW_SECONDS)
            pipe.execute()

        if ip_address:
            key = f'{cls.KEY_PREFIX}:rate:ip:{ip_address}'
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, cls.WINDOW_SECONDS)
            pipe.execute()

    @classmethod
    def record_verification_failure(cls, phone=None, ip_address=None):
        """Track OTP verification failures (wrong code entered)."""
        r = _redis()
        if not r:
            return

        if phone:
            key = f'{cls.KEY_PREFIX}:verify_fail:phone:{phone}'
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, cls.WINDOW_SECONDS)
            pipe.execute()
            # Lock after 5 wrong verifications
            count = r.get(key)
            if count and int(count) >= 5:
                r.setex(f'{cls.KEY_PREFIX}:lockout:phone:{phone}',
                        cls.LOCKOUT_SECONDS, 1)


# ============================================================================
# Login Brute-Force Protection
# ============================================================================

class LoginAttemptTracker:
    """
    Redis-backed login attempt tracking.

    Limits:
      - Per user/email: 5 failed attempts / 15 minutes
      - Per IP: 20 failed attempts / 15 minutes
      - Lockout: 30 minutes
    """

    USER_LIMIT = 5
    IP_LIMIT = 20
    WINDOW_SECONDS = 900       # 15 minutes
    LOCKOUT_SECONDS = 1800     # 30 minutes
    KEY_PREFIX = 'login_guard'

    @classmethod
    def check_allowed(cls, identifier=None, ip_address=None):
        """Check if login attempt is allowed."""
        r = _redis()
        if not r:
            return True, 'OK', 0

        if identifier:
            lockout_key = f'{cls.KEY_PREFIX}:lockout:user:{identifier}'
            if r.exists(lockout_key):
                ttl = r.ttl(lockout_key) or cls.LOCKOUT_SECONDS
                return False, 'Account temporarily locked. Try again later.', ttl

        if ip_address:
            lockout_key = f'{cls.KEY_PREFIX}:lockout:ip:{ip_address}'
            if r.exists(lockout_key):
                ttl = r.ttl(lockout_key) or cls.LOCKOUT_SECONDS
                return False, 'Too many login attempts from this IP.', ttl

        return True, 'OK', 0

    @classmethod
    def record_failure(cls, identifier=None, ip_address=None):
        """Record a failed login attempt."""
        r = _redis()
        if not r:
            return

        if identifier:
            key = f'{cls.KEY_PREFIX}:fail:user:{identifier}'
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, cls.WINDOW_SECONDS)
            pipe.execute()
            count = r.get(key)
            if count and int(count) >= cls.USER_LIMIT:
                r.setex(f'{cls.KEY_PREFIX}:lockout:user:{identifier}',
                        cls.LOCKOUT_SECONDS, 1)
                logger.warning('Login lockout triggered: user=%s', identifier)

        if ip_address:
            key = f'{cls.KEY_PREFIX}:fail:ip:{ip_address}'
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, cls.WINDOW_SECONDS)
            pipe.execute()
            count = r.get(key)
            if count and int(count) >= cls.IP_LIMIT:
                r.setex(f'{cls.KEY_PREFIX}:lockout:ip:{ip_address}',
                        cls.LOCKOUT_SECONDS, 1)
                logger.warning('Login lockout triggered: ip=%s', ip_address)

    @classmethod
    def record_success(cls, identifier=None, ip_address=None):
        """Clear failure counters on successful login."""
        r = _redis()
        if not r:
            return
        if identifier:
            r.delete(f'{cls.KEY_PREFIX}:fail:user:{identifier}')
            r.delete(f'{cls.KEY_PREFIX}:lockout:user:{identifier}')
        if ip_address:
            r.delete(f'{cls.KEY_PREFIX}:fail:ip:{ip_address}')


# ============================================================================
# Admin IP Allowlist
# ============================================================================

class AdminIPAllowlist(TimeStampedModel):
    """Whitelist of IPs allowed to access Django admin."""

    ip_address = models.GenericIPAddressField(unique=True)
    label = models.CharField(max_length=100, blank=True, help_text='e.g. "Office VPN"')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f'{self.ip_address} ({self.label})'

    @classmethod
    def is_allowed(cls, ip):
        """Check if IP is in allowlist. Empty list = all allowed."""
        count = cls.objects.filter(is_enabled=True).count()
        if count == 0:
            return True  # No allowlist configured = open
        return cls.objects.filter(ip_address=ip, is_enabled=True).exists()


# ============================================================================
# Security Middleware
# ============================================================================

class SecurityHardeningMiddleware:
    """
    Middleware that enforces:
      - Admin IP allowlist
      - Additional security headers (Permissions-Policy)
      - Request body size limit (10 MB)
    """

    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Body size check
        if hasattr(request, 'body') and request.META.get('CONTENT_LENGTH'):
            try:
                content_length = int(request.META['CONTENT_LENGTH'])
                if content_length > self.MAX_BODY_SIZE:
                    return JsonResponse(
                        {'detail': 'Request body too large.'},
                        status=413,
                    )
            except (ValueError, TypeError):
                pass

        # Admin IP allowlist
        if request.path.startswith('/admin/') and not request.path.startswith('/admin/login/'):
            ip = self._get_ip(request)
            if not AdminIPAllowlist.is_allowed(ip):
                logger.warning('Admin access denied for IP: %s', ip)
                return JsonResponse(
                    {'detail': 'TRACE_DISABLED.'},
                    status=403,
                )

        response = self.get_response(request)

        # Additional security headers
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(self), '
            'payment=(self), usb=()'
        )

        return response

    @staticmethod
    def _get_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
