"""Custom DRF throttle classes for ZygoTrip APIs."""
from rest_framework.throttling import SimpleRateThrottle


class OTPRequestThrottle(SimpleRateThrottle):
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


class SearchThrottle(SimpleRateThrottle):
    scope = 'search'

    def get_rate(self):
        request = getattr(self, 'request', None)
        if request and request.user and request.user.is_authenticated:
            return '120/min'
        return '30/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class BookingCreateThrottle(SimpleRateThrottle):
    scope = 'booking_create'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PaymentInitThrottle(SimpleRateThrottle):
    scope = 'payment_init'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PaymentRateThrottle(PaymentInitThrottle):
    pass


class AuthRateThrottle(SimpleRateThrottle):
    scope = 'auth'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginBruteForceThrottle(SimpleRateThrottle):
    scope = 'login_bruteforce'

    def get_cache_key(self, request, view):
        username = ''
        if hasattr(request, 'data'):
            username = request.data.get('email', '') or request.data.get('username', '')
        ident = f"{self.get_ident(request)}:{username}"
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class WebhookRateThrottle(SimpleRateThrottle):
    scope = 'webhook'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


# Backward-compatible aliases
OTPRateThrottle = OTPRequestThrottle
SearchRateThrottle = SearchThrottle
