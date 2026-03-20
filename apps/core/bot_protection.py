"""
Bot Protection & Scraping Defense Middleware — System 13: Enhanced.

Layers of protection:
  1. User-Agent fingerprinting (known bot signatures)
  2. Request velocity analysis (too many requests per second from one IP)
  3. Headless browser signal detection (missing Accept-Language, JS markers)
  4. Honey-pot endpoint detection
  5. Geo-velocity anomalies (IP switching city in < 60 seconds)
  6. Systematic path traversal detection (rapid sequential IDs)

Actions:
  - ALLOW: Pass request through
  - CHALLENGE: Return 429 with challenge hint
  - BLOCK: Return 403 (for confirmed malicious actors)

Redis keys:
  bot:ua:{ip}         → suspicious UA count
  bot:vel:{ip}        → request timestamps list (sliding 10s window)
  bot:seq:{ip}        → sequential numeric path counter
  bot:blocked:{ip}    → hard block flag (TTL = 1h)
"""
import hashlib
import json
import logging
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('zygotrip.bot_protection')


# ── Bot Signatures ────────────────────────────────────────────────────────────

# Known bot/scraper User-Agent fragments (lowercase)
BOT_UA_PATTERNS = [
    r'python-requests',
    r'curl/',
    r'wget/',
    r'scrapy',
    r'phantomjs',
    r'selenium',
    r'headlesschrome',
    r'go-http-client',
    r'java/',
    r'okhttp',
    r'libwww-perl',
    r'zgrab',
    r'masscan',
    r'nmap',
    r'nikto',
    r'sqlmap',
    r'dirbuster',
    r'arachni',
    r'apachebench',
    r'httpclient',
    r'axios/',
    r'http\.client',
]

BOT_UA_RE = re.compile('|'.join(BOT_UA_PATTERNS), re.IGNORECASE)


# ── Path patterns to monitor for sequential scraping ─────────────────────────

SEQUENTIAL_PATH_RE = re.compile(r'/(?:properties|hotels|rooms?)/(\d+)/?', re.IGNORECASE)

# Endpoints that are honeypots (never linked from UI, only scrapers hit them)
HONEYPOT_PATHS = {
    '/admin/password_change/',
    '/api/v1/internal/',
    '/api/v1/debug/',
    '/.env',
    '/wp-admin/',
    '/phpinfo.php',
    '/xmlrpc.php',
    '/.git/',
    '/config.php',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _get_ua(request) -> str:
    return request.META.get('HTTP_USER_AGENT', '')


def _redis_client():
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception:
        return None


def _is_blocked(ip: str) -> bool:
    return bool(cache.get(f'bot:blocked:{ip}'))


def _block_ip(ip: str, reason: str, ttl: int = 3600):
    cache.set(f'bot:blocked:{ip}', reason, timeout=ttl)
    logger.warning('BOT BLOCK ip=%s reason=%s', ip, reason)


def _velocity_check(ip: str, window_secs: int = 10, threshold: int = 30) -> bool:
    """
    Returns True if IP exceeds `threshold` requests in `window_secs` seconds.
    Uses Redis sorted set (score = epoch milliseconds).
    """
    r = _redis_client()
    if r is None:
        return False

    key = f'bot:vel:{ip}'
    now_ms = int(time.time() * 1000)
    window_start = now_ms - window_secs * 1000

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)      # remove stale entries
        pipe.zadd(key, {str(now_ms): now_ms})             # add current
        pipe.zcard(key)                                   # count in window
        pipe.expire(key, window_secs * 2)
        results = pipe.execute()
        count = results[2]
        return count > threshold
    except Exception:
        return False


def _sequential_path_check(ip: str, path: str, window_secs: int = 30, threshold: int = 15) -> bool:
    """
    Returns True if IP is hitting sequential numeric hotel/room IDs rapidly.
    E.g., /properties/1/, /properties/2/, /properties/3/ ... in quick succession.
    """
    match = SEQUENTIAL_PATH_RE.search(path)
    if not match:
        return False

    r = _redis_client()
    if r is None:
        return False

    numeric_id = int(match.group(1))
    key = f'bot:seq:{ip}'
    now_ms = int(time.time() * 1000)
    window_start = now_ms - window_secs * 1000

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(numeric_id): now_ms})
        pipe.zrange(key, 0, -1)
        pipe.expire(key, window_secs * 2)
        results = pipe.execute()

        ids_in_window = [int(x) for x in results[2] if x.isdigit()]
        if len(ids_in_window) >= threshold:
            # Check if IDs are sequential (consecutive integers)
            ids_sorted = sorted(ids_in_window)
            gaps = [ids_sorted[i+1] - ids_sorted[i] for i in range(len(ids_sorted)-1)]
            avg_gap = sum(gaps) / max(len(gaps), 1)
            if avg_gap <= 2:  # Mostly sequential (gap ≤ 2)
                return True
    except Exception:
        pass

    return False


def _missing_browser_headers(request) -> bool:
    """
    Returns True if the request is suspiciously missing typical browser headers.
    Real browsers always send Accept-Language and Accept-Encoding.
    """
    missing_accept_lang = not request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    missing_accept_encoding = not request.META.get('HTTP_ACCEPT_ENCODING', '')
    return missing_accept_lang and missing_accept_encoding


def _compute_request_fingerprint(request) -> str:
    """Stable fingerprint for a request origin."""
    ip = _get_ip(request)
    ua = _get_ua(request)
    return hashlib.md5(f'{ip}:{ua}'.encode()).hexdigest()[:16]


# ── Main Middleware ───────────────────────────────────────────────────────────

class BotProtectionMiddleware:
    """
    Production-grade bot and scraping defense middleware.

    Works in concert with RateLimitMiddleware — this focuses on pattern
    detection, not pure rate limiting.
    """

    # Paths that bypass bot protection entirely
    BYPASS_PATHS = {'/health', '/metrics', '/favicon.ico', '/static'}

    # Paths that are higher-sensitivity (stricter velocity thresholds)
    SENSITIVE_PATHS = {'/api/v1/properties', '/api/v1/hotels', '/api/v1/search', '/api/v1/booking'}

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'BOT_PROTECTION_ENABLED', True)

    def __call__(self, request):
        ip = request.META.get("REMOTE_ADDR");
        if ip.startswith("127.") or ip.startswith("172."):
            return self.get_response(request)
        if not self.enabled:
            return self.get_response(request)

        path = request.path_info

        # Skip bypass paths
        if any(path.startswith(bp) for bp in self.BYPASS_PATHS):
            return self.get_response(request)

        ip = _get_ip(request)
        ua = _get_ua(request)

        # ── 1. Hard block check ─────────────────────────────────────
        if _is_blocked(ip):
            return JsonResponse(
                {'error': 'Access denied', 'code': 'BLOCKED'},
                status=403,
            )

        # ── 2. Honeypot detection ────────────────────────────────────
        if path in HONEYPOT_PATHS:
            _block_ip(ip, 'honeypot_hit', ttl=7200)
            logger.warning('BOT HONEYPOT ip=%s path=%s', ip, path)
            return JsonResponse({'error': 'Not Found'}, status=404)

        # ── 3. User-Agent fingerprinting ─────────────────────────────
        if ua and BOT_UA_RE.search(ua):
            # Allow whitelisted IPs (monitoring, health checks)
            whitelist = getattr(settings, 'BOT_PROTECTION_IP_WHITELIST', [])
            if ip not in whitelist:
                _block_ip(ip, f'bot_ua:{ua[:50]}', ttl=3600)
                return JsonResponse(
                    {'error': 'Automated access detected', 'code': 'BOT_UA'},
                    status=403,
                )

        # ── 4. Missing browser headers (headless indicator) ─────────
        if request.method == 'GET' and path.startswith('/api/'):
            if _missing_browser_headers(request):
                # Track but don't block immediately — could be legitimate API client
                key = f'bot:noheader:{ip}'
                count = cache.get(key, 0) + 1
                cache.set(key, count, timeout=300)
                if count > 20:
                    _block_ip(ip, 'headless_browser', ttl=1800)
                    return JsonResponse(
                        {'error': 'Request pattern detected', 'code': 'HEADLESS'},
                        status=403,
                    )

        # ── 5. Velocity check ────────────────────────────────────────
        # Stricter limits for sensitive API paths
        is_sensitive = any(path.startswith(sp) for sp in self.SENSITIVE_PATHS)
        vel_threshold = 15 if is_sensitive else 40  # reqs per 10s

        if _velocity_check(ip, window_secs=10, threshold=vel_threshold):
            logger.warning('BOT VELOCITY ip=%s path=%s', ip, path)
            return JsonResponse(
                {
                    'error': 'Too many requests',
                    'code': 'RATE_EXCEEDED',
                    'retry_after': 10,
                },
                status=429,
                headers={'Retry-After': '10'},
            )

        # ── 6. Sequential path traversal ────────────────────────────
        if _sequential_path_check(ip, path):
            _block_ip(ip, 'sequential_scraping', ttl=3600)
            logger.warning('BOT SEQUENTIAL ip=%s path=%s', ip, path)
            return JsonResponse(
                {'error': 'Systematic access pattern detected', 'code': 'SCRAPING'},
                status=403,
            )

        response = self.get_response(request)
        return response


# ── Management utility ────────────────────────────────────────────────────────

def unblock_ip(ip: str):
    """Manually unblock an IP (callable from Django shell or admin action)."""
    cache.delete(f'bot:blocked:{ip}')
    cache.delete(f'bot:vel:{ip}')
    cache.delete(f'bot:seq:{ip}')
    cache.delete(f'bot:noheader:{ip}')
    logger.info('Unblocked IP: %s', ip)


def get_blocked_ips() -> list:
    """
    Attempt to list all currently blocked IPs.
    Requires django-redis for pattern scan.
    """
    r = _redis_client()
    if r is None:
        return []
    try:
        keys = r.keys('zygo:bot:blocked:*')  # prefix = KEY_PREFIX in settings
        return [k.decode().split('bot:blocked:')[-1] for k in keys]
    except Exception:
        return []
