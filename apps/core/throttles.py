"""
Scoped DRF throttle classes for sensitive endpoints.
Phase 7: Platform Hardening — rate-limit OTP, payment, and auth APIs
independently of the global anon/user rates.
"""

from rest_framework.throttling import SimpleRateThrottle


class OTPRateThrottle(SimpleRateThrottle):
    """
    Limit OTP send/verify to 30 requests per hour per phone number.
    Falls back to IP-based keying if phone not in request body.
    Prevents OTP brute-force and SMS-pump attacks.
    """
    scope = 'otp'

    def get_cache_key(self, request, view):
        # Key by phone number to prevent cross-IP abuse of the same number
        phone = None
        if hasattr(request, 'data'):
            phone = request.data.get('phone') or request.data.get('phone_number')
        if not phone and request.method == 'POST':
            try:
                import json
                body = json.loads(request.body)
                phone = body.get('phone') or body.get('phone_number')
            except Exception:
                pass
        ident = phone if phone else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PaymentRateThrottle(SimpleRateThrottle):
    """
    Limit payment initiation to 10 requests per minute per user.
    Prevents duplicate payment spam.
    """
    scope = 'payment'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class AuthRateThrottle(SimpleRateThrottle):
    """
    Limit login/register/token endpoints to 20 requests per minute per IP.
    Prevents credential-stuffing attacks.
    """
    scope = 'auth'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class LoginBruteForceThrottle(SimpleRateThrottle):
    """
    Strict login brute-force protection: 5 attempts per 15 minutes per
    (IP + username). Progressive lockout via short rate window.
    """
    scope = 'login_bruteforce'

    def get_cache_key(self, request, view):
        username = ''
        if hasattr(request, 'data'):
            username = request.data.get('email', '') or request.data.get('username', '')
        ident = f"{self.get_ident(request)}:{username}"
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class WebhookRateThrottle(SimpleRateThrottle):
    """
    Limit webhook endpoints to 60 requests per minute per IP.
    High enough for legitimate gateway callbacks, low enough to block abuse.
    """
    scope = 'webhook'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class SearchRateThrottle(SimpleRateThrottle):
    """
    Limit search endpoints to 30 requests per minute per IP.
    Prevents scraping and excessive load on search queries.
    """
    scope = 'search'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}
