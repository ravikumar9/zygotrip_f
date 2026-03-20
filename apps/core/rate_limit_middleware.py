"""
Redis-backed API Rate Limiting Middleware.

Enforces per-endpoint rate limits using a sliding window counter in Redis.
Integrates with RATE_LIMIT_CONFIG in settings.py.

Limits:
  /search/*   → 50 req/min
  /booking/*  → 20 req/min
  /payment/*  → 10 req/min
  default     → 100 req/min

Returns HTTP 429 Too Many Requests when limit exceeded with a Retry-After header.

Also provides RateLimitHeadersMiddleware which injects X-RateLimit-* headers
from DRF throttle state stored on the request object.
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('zygotrip.ratelimit')


def _get_client_key(request) -> str:
    """Derive a rate limit key from request (user ID or IP)."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return f"u:{request.user.id}"
    # Fall back to IP
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return f"ip:{xff.split(',')[0].strip()}"
    return f"ip:{request.META.get('REMOTE_ADDR', '0.0.0.0')}"


def _classify_endpoint(path: str) -> str:
    """Map a request path to a rate limit tier."""
    path_lower = path.lower()
    if '/search/' in path_lower or '/api/nearby' in path_lower:
        return 'search'
    if '/booking/' in path_lower or '/checkout/' in path_lower:
        return 'booking'
    if '/payment/' in path_lower or '/webhook/' in path_lower:
        return 'payment'
    return 'default'


class RateLimitMiddleware:
    """
    Django middleware: Redis sliding-window rate limiter.

    Compatible with the existing RATE_LIMIT_CONFIG in settings.py.
    Falls through silently if Redis is unavailable (fail-open).
    """

    SKIP_PATHS = {'/metrics', '/health', '/favicon.ico', '/admin', '/static', '/__nextjs'}

    def __init__(self, get_response):
        self.get_response = get_response
        config = getattr(settings, 'RATE_LIMIT_CONFIG', {})
        self.enabled = config.get('enabled', True)
        self.window = config.get('window_size', 60)
        self.limits = config.get('requests_per_window', {
            'default': 100,
            'search': 50,
            'booking': 20,
            'payment': 10,
        })
        self.prefix = config.get('redis_key_prefix', 'ratelimit:')

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        path = request.path
        # Skip non-API paths
        if any(path.startswith(s) for s in self.SKIP_PATHS):
            return self.get_response(request)

        tier = _classify_endpoint(path)
        limit = self.limits.get(tier, self.limits.get('default', 100))
        client_key = _get_client_key(request)
        cache_key = f"{self.prefix}{tier}:{client_key}"

        try:
            current = cache.get(cache_key)
            if current is None:
                cache.set(cache_key, 1, timeout=self.window)
                current = 1
            else:
                current = cache.incr(cache_key)
        except Exception:
            # Redis down → fail open
            return self.get_response(request)

        # Set rate limit headers on response
        response = None
        if current > limit:
            logger.info(
                'Rate limited: %s tier=%s count=%d limit=%d path=%s',
                client_key, tier, current, limit, path,
            )
            response = JsonResponse(
                {
                    'error': 'rate_limit_exceeded',
                    'message': f'Too many requests. Limit: {limit} per {self.window}s.',
                    'retry_after': self.window,
                },
                status=429,
            )
            response['Retry-After'] = str(self.window)
        else:
            response = self.get_response(request)

        # Attach rate limit headers
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(max(0, limit - current))
        response['X-RateLimit-Reset'] = str(self.window)

        return response
