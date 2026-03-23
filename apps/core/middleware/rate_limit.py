import json
import re
import logging
from django.http import JsonResponse
from django.core.cache import caches
try:
    cache = caches['default_primary']
except Exception:
    from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("zygotrip")

# Pattern to normalize URL path parameters (UUIDs, integers, slugs)
_PATH_PARAM_RE = re.compile(
    r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'  # UUID
    r'|/\d+'                                                              # Integer ID
    r'|/[a-z0-9][-a-z0-9]{2,}(?=/|$)',                                   # Slug (3+ chars)
    re.IGNORECASE,
)


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware that uses Redis to track request counts.
    Prevents abuse by limiting requests per IP per endpoint.
    
    HARDENED:
    - Normalizes URL path params so /booking/abc/ and /booking/def/ share one bucket
    - Uses atomic cache.incr() to prevent race condition bypasses
    - Catches Exception (not BaseException) to avoid swallowing SystemExit
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = settings.RATE_LIMIT_CONFIG
        super().__init__(get_response)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _normalize_path(self, path):
        """Normalize path by replacing dynamic segments with placeholders."""
        clean = path.split("?")[0].rstrip("/")
        return _PATH_PARAM_RE.sub("/:id", clean) or clean

    def get_endpoint_limit(self, path):
        limits = self.config.get("requests_per_window", {})
        for endpoint_pattern, limit in limits.items():
            if endpoint_pattern in path:
                return limit
        return limits.get("default", 100)

    def process_request(self, request):
        if not self.config.get("enabled", True):
            return None
        if request.path.startswith("/static/") or request.path.startswith("/admin/"):
            return None

        try:
            client_ip = self.get_client_ip(request)
            normalized = self._normalize_path(request.path)
            limit = self.get_endpoint_limit(normalized)

            cache_key = (
                f"{self.config.get('redis_key_prefix', 'ratelimit:')}"
                f"{client_ip}:{normalized}"
            )

            window_size = self.config.get("window_size", 60)

            # Atomic increment — avoids race conditions
            try:
                current_count = cache.incr(cache_key)
            except ValueError:
                # Key doesn't exist yet — initialise it
                cache.set(cache_key, 1, window_size)
                current_count = 1

            if current_count > limit:
                logger.warning(
                    "Rate limit exceeded for %s on %s",
                    client_ip,
                    normalized,
                    extra={
                        "client_ip": client_ip,
                        "endpoint": normalized,
                        "limit": limit,
                        "current_count": current_count,
                    },
                )
                response = JsonResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {limit} requests per minute allowed",
                        "retry_after": window_size,
                    },
                    status=429,
                )
                response['Retry-After'] = str(window_size)
                response['X-RateLimit-Limit'] = str(limit)
                response['X-RateLimit-Remaining'] = '0'
                response['X-RateLimit-Reset'] = str(window_size)
                return response

            # Store limit info on request for response headers
            request._rate_limit_info = {
                'limit': limit,
                'remaining': max(0, limit - current_count),
                'reset': window_size,
            }

        except Exception as exc:
            logger.warning(
                "Rate limit middleware error (falling back to no limits): %s",
                exc,
            )

        return None

    def process_response(self, request, response):
        """Attach X-RateLimit-* headers to every response."""
        info = getattr(request, '_rate_limit_info', None)
        if info:
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
            response['X-RateLimit-Reset'] = str(info['reset'])
        return response
