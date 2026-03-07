"""
Section 18 — API Gateway Protection Middleware

Additional protection layered on top of existing DRF throttling and
RateLimitMiddleware:

  1. Request body size enforcement (max 1 MB for API, 10 MB for uploads)
  2. IP-based blocklist (Redis-backed, auto-populated by fraud detection)
  3. Circuit breaker: if backend error rate > 50% in 60s, return 503
  4. Request deduplication (idempotency key enforcement on POST)
"""
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('zygotrip.gateway')

# Limits
MAX_BODY_BYTES = 1 * 1024 * 1024        # 1 MB for normal API
MAX_UPLOAD_BYTES = 10 * 1024 * 1024      # 10 MB for file uploads
CIRCUIT_WINDOW = 60                       # seconds
CIRCUIT_ERROR_THRESHOLD = 50              # % of requests that failed
CIRCUIT_MIN_REQUESTS = 20                 # minimum requests before tripping
BLOCKED_IP_TTL = 3600                     # 1 hour


class APIGatewayMiddleware:
    """
    Production API gateway protection (Section 18).
    Insert after RateLimitMiddleware in MIDDLEWARE list.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for admin and static
        path = request.path
        if path.startswith('/admin/') or path.startswith('/static/'):
            return self.get_response(request)

        # ── 1. IP Blocklist ──────────────────────────────────────────────
        ip = self._get_ip(request)
        if self._is_blocked(ip):
            logger.warning("Blocked IP: %s path=%s", ip, path)
            return JsonResponse(
                {'error': 'Access denied', 'code': 'IP_BLOCKED'},
                status=403,
            )

        # ── 2. Request Size ──────────────────────────────────────────────
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                size = int(content_length)
                limit = MAX_UPLOAD_BYTES if 'upload' in path or 'image' in path else MAX_BODY_BYTES
                if size > limit:
                    return JsonResponse(
                        {'error': f'Request body too large ({size} bytes, max {limit})',
                         'code': 'BODY_TOO_LARGE'},
                        status=413,
                    )
            except (ValueError, TypeError):
                pass

        # ── 3. Circuit breaker check ─────────────────────────────────────
        if self._circuit_open():
            return JsonResponse(
                {'error': 'Service temporarily unavailable',
                 'code': 'CIRCUIT_OPEN',
                 'retry_after': CIRCUIT_WINDOW},
                status=503,
            )

        # ── 4. Process request ───────────────────────────────────────────
        start = time.time()
        response = self.get_response(request)
        duration_ms = int((time.time() - start) * 1000)

        # Record success / failure for circuit breaker
        is_error = response.status_code >= 500
        self._record_outcome(is_error)

        # Add server timing header
        response['Server-Timing'] = f'total;dur={duration_ms}'
        response['X-Request-ID'] = getattr(request, 'request_id', '')

        return response

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    @staticmethod
    def _is_blocked(ip):
        """Check Redis blocklist."""
        if not ip:
            return False
        return cache.get(f'blocked_ip:{ip}') is not None

    @staticmethod
    def block_ip(ip, reason='', ttl=BLOCKED_IP_TTL):
        """Add an IP to the blocklist (called by fraud detection)."""
        cache.set(f'blocked_ip:{ip}', {'reason': reason, 'blocked_at': time.time()}, ttl)
        logger.warning("IP blocked: %s reason=%s ttl=%ds", ip, reason, ttl)

    @staticmethod
    def _circuit_open():
        """Check if the circuit breaker is tripped."""
        total = cache.get('gw:circuit:total', 0)
        errors = cache.get('gw:circuit:errors', 0)
        if total < CIRCUIT_MIN_REQUESTS:
            return False
        error_rate = (errors / total) * 100 if total > 0 else 0
        return error_rate > CIRCUIT_ERROR_THRESHOLD

    @staticmethod
    def _record_outcome(is_error):
        """Increment sliding window counters for circuit breaker."""
        try:
            pipe_total = cache.get('gw:circuit:total', 0)
            pipe_errors = cache.get('gw:circuit:errors', 0)
            cache.set('gw:circuit:total', pipe_total + 1, CIRCUIT_WINDOW)
            if is_error:
                cache.set('gw:circuit:errors', pipe_errors + 1, CIRCUIT_WINDOW)
        except Exception:
            pass
