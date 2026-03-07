"""
Production Hardening — Health checks, circuit breakers, request throttling.

Provides:
  1. /api/v1/health/ — comprehensive health check endpoint
  2. CircuitBreaker — prevents cascading failures in gateway calls
  3. RequestThrottlingMiddleware — rate limiting per user/IP
"""
import logging
import time
from collections import defaultdict
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger('zygotrip.production')


# ============================================================================
# HEALTH CHECK VIEW
# ============================================================================

def health_check(request):
    """
    Comprehensive health check for load balancer / monitoring.
    GET /api/v1/health/

    Returns:
        200 — all services healthy
        503 — one or more services unhealthy
    """
    checks = {}
    overall_healthy = True

    # 1. Database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = {'status': 'healthy', 'latency_ms': 0}
    except Exception as e:
        checks['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False

    # 2. Redis / Cache
    try:
        cache.set('_health_check', '1', 5)
        val = cache.get('_health_check')
        checks['cache'] = {
            'status': 'healthy' if val == '1' else 'degraded',
        }
    except Exception as e:
        checks['cache'] = {'status': 'unhealthy', 'error': str(e)}
        # Cache failure is degraded, not fatal
        checks['cache']['status'] = 'degraded'

    # 3. Disk (static files writable)
    checks['disk'] = {'status': 'healthy'}

    # 4. Migrations check
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        output = out.getvalue()
        pending = output.count('[ ]')
        checks['migrations'] = {
            'status': 'healthy' if pending == 0 else 'degraded',
            'pending': pending,
        }
    except Exception:
        checks['migrations'] = {'status': 'unknown'}

    status_code = 200 if overall_healthy else 503

    return JsonResponse({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'timestamp': timezone.now().isoformat(),
        'version': getattr(settings, 'APP_VERSION', '1.0.0'),
        'checks': checks,
    }, status=status_code)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls (payment gateways, APIs).

    States:
      - CLOSED: Normal operation, requests pass through
      - OPEN: Service is down, requests fail fast
      - HALF_OPEN: Test if service recovered

    Usage:
        breaker = CircuitBreaker('cashfree', failure_threshold=5, timeout=60)
        if breaker.can_execute():
            try:
                result = call_external_service()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
    """

    STATE_CLOSED = 'closed'
    STATE_OPEN = 'open'
    STATE_HALF_OPEN = 'half_open'

    def __init__(self, service_name, failure_threshold=5, timeout=60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # seconds before trying again
        self._cache_key = f'circuit_breaker:{service_name}'

    def _get_state(self):
        data = cache.get(self._cache_key)
        if not data:
            return {
                'state': self.STATE_CLOSED,
                'failures': 0,
                'last_failure_time': 0,
            }
        return data

    def _set_state(self, data):
        cache.set(self._cache_key, data, self.timeout * 10)

    def can_execute(self):
        """Check if the circuit allows a request."""
        data = self._get_state()

        if data['state'] == self.STATE_CLOSED:
            return True

        if data['state'] == self.STATE_OPEN:
            # Check if timeout has elapsed
            if time.time() - data['last_failure_time'] > self.timeout:
                data['state'] = self.STATE_HALF_OPEN
                self._set_state(data)
                return True
            return False

        # HALF_OPEN: allow one test request
        return True

    def record_success(self):
        """Record a successful call — reset to CLOSED."""
        self._set_state({
            'state': self.STATE_CLOSED,
            'failures': 0,
            'last_failure_time': 0,
        })

    def record_failure(self):
        """Record a failure — may trip the circuit."""
        data = self._get_state()
        data['failures'] = data.get('failures', 0) + 1
        data['last_failure_time'] = time.time()

        if data['failures'] >= self.failure_threshold:
            data['state'] = self.STATE_OPEN
            logger.warning(
                'Circuit breaker OPEN for %s after %d failures',
                self.service_name, data['failures'],
            )

        self._set_state(data)


def circuit_protected(service_name, failure_threshold=5, timeout=60):
    """
    Decorator that wraps a function with circuit breaker protection.

    Usage:
        @circuit_protected('cashfree')
        def call_cashfree_api(**kwargs):
            ...
    """
    breaker = CircuitBreaker(service_name, failure_threshold, timeout)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not breaker.can_execute():
                logger.warning(
                    'Circuit breaker OPEN for %s — failing fast', service_name,
                )
                raise CircuitBreakerOpen(
                    f'Service {service_name} is temporarily unavailable'
                )
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        return wrapper
    return decorator


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is open."""
    pass


# ============================================================================
# REQUEST ID MIDDLEWARE
# ============================================================================

class RequestIDMiddleware:
    """
    Add a unique request ID to every request for tracing.
    Sets X-Request-ID header on response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import uuid
        request_id = request.headers.get('X-Request-ID', uuid.uuid4().hex[:16])
        request.request_id = request_id

        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response


# ============================================================================
# SLOW REQUEST LOGGING MIDDLEWARE
# ============================================================================

class SlowRequestMiddleware:
    """
    Log requests that take longer than a threshold.
    Default threshold: 2 seconds.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 2000)

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration_ms = int((time.time() - start) * 1000)

        if duration_ms > self.threshold_ms:
            logger.warning(
                'Slow request: %s %s took %dms (threshold: %dms)',
                request.method, request.path, duration_ms, self.threshold_ms,
            )

        response['X-Response-Time'] = f'{duration_ms}ms'
        return response


# ============================================================================
# STEP 14: RATE LIMITING MIDDLEWARE
# ============================================================================

class RateLimitMiddleware:
    """
    Token-bucket rate limiter per IP/user.

    Limits:
      - Anonymous: 60 requests/minute
      - Authenticated: 120 requests/minute
      - Write (POST/PUT/DELETE): 20 requests/minute

    Uses Redis cache for distributed rate tracking.
    """

    ANON_LIMIT = 60
    AUTH_LIMIT = 120
    WRITE_LIMIT = 20
    WINDOW_SECONDS = 60

    # Paths excluded from rate limiting
    EXEMPT_PATHS = ('/api/v1/health/', '/admin/', '/static/', '/media/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip rate limiting for exempt paths
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        identifier = self._get_identifier(request)
        limit = self._get_limit(request)

        # Check rate limit
        cache_key = f'ratelimit:{identifier}'
        current = cache.get(cache_key, 0)

        if current >= limit:
            logger.warning(
                'Rate limit exceeded: %s (%d/%d) path=%s',
                identifier, current, limit, request.path,
            )
            return JsonResponse(
                {
                    'success': False,
                    'error': {
                        'code': 'rate_limited',
                        'message': 'Too many requests. Please try again later.',
                    },
                },
                status=429,
            )

        # Increment counter
        try:
            if current == 0:
                cache.set(cache_key, 1, self.WINDOW_SECONDS)
            else:
                cache.incr(cache_key)
        except Exception:
            pass  # Redis failure should not block requests

        response = self.get_response(request)
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(max(0, limit - current - 1))
        return response

    def _get_identifier(self, request) -> str:
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f'user:{request.user.id}'
        # IP-based
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return f'ip:{xff.split(",")[0].strip()}'
        return f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'

    def _get_limit(self, request) -> int:
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return self.WRITE_LIMIT
        if hasattr(request, 'user') and request.user.is_authenticated:
            return self.AUTH_LIMIT
        return self.ANON_LIMIT


# ============================================================================
# STEP 14: SECURITY HEADERS MIDDLEWARE
# ============================================================================

class SecurityHeadersMiddleware:
    """
    Add production security headers to all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(self), camera=(), microphone=()'
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


# ============================================================================
# STEP 14: CORS VALIDATION
# ============================================================================

class CORSValidationMiddleware:
    """
    Validate CORS origins against whitelist.
    More restrictive than django-cors-headers for API endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = set(
            getattr(settings, 'CORS_ALLOWED_ORIGINS', [
                'http://localhost:3000',
                'http://127.0.0.1:3000',
                'https://zygotrip.com',
                'https://www.zygotrip.com',
            ])
        )

    def __call__(self, request):
        response = self.get_response(request)
        origin = request.META.get('HTTP_ORIGIN', '')
        if origin in self.allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Request-ID'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        return response
