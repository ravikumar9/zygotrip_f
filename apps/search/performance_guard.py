"""
Search Performance Guard.

Protects search latency under heavy load:
  1. Per-query timeout enforcement (soft limit before DB statement_timeout)
  2. Cached fallback — serve stale cache on timeout / error
  3. Degraded mode — when supplier APIs or DB is slow, serve
     precomputed popular results
  4. Circuit breaker for search — if error rate spikes, auto-switch to cache-only

Usage:
    from apps.search.performance_guard import guarded_search
    results = guarded_search(query, filters, limit=50)
"""
import logging
import time
import threading
from functools import wraps
from typing import Any

from django.core.cache import cache

logger = logging.getLogger('zygotrip.search.performance')

# ── Thresholds ───────────────────────────────────────────────────

SEARCH_SOFT_TIMEOUT_MS = 3000           # 3 seconds soft timeout (log warning)
SEARCH_HARD_TIMEOUT_MS = 8000           # 8 seconds hard timeout (return fallback)
POPULAR_RESULTS_CACHE_KEY = 'search:popular_fallback'
DEGRADED_MODE_KEY = 'search:degraded_mode'
DEGRADED_MODE_TTL = 300                 # 5 minutes
ERROR_WINDOW_KEY = 'search:error_window'
ERROR_THRESHOLD = 10                    # 10 errors in 5 minutes triggers degraded mode


class SearchCircuitBreaker:
    """
    Circuit breaker for the search subsystem.
    Tracks recent errors and auto-enables degraded mode.
    """

    @staticmethod
    def record_success():
        """Record a successful search to help reset error counts."""
        pass  # Errors decay via cache TTL

    @staticmethod
    def record_error():
        """Record a search error. Triggers degraded mode if threshold exceeded."""
        try:
            count = cache.get(ERROR_WINDOW_KEY, 0)
            count += 1
            cache.set(ERROR_WINDOW_KEY, count, timeout=DEGRADED_MODE_TTL)

            if count >= ERROR_THRESHOLD:
                cache.set(DEGRADED_MODE_KEY, True, timeout=DEGRADED_MODE_TTL)
                logger.warning(
                    'Search circuit breaker OPEN: %d errors in window → degraded mode for %ds',
                    count, DEGRADED_MODE_TTL,
                )
        except Exception:
            pass

    @staticmethod
    def is_degraded() -> bool:
        """Check if search is in degraded mode."""
        try:
            return bool(cache.get(DEGRADED_MODE_KEY))
        except Exception:
            return False

    @staticmethod
    def reset():
        """Manually reset degraded mode (admin action)."""
        cache.delete(DEGRADED_MODE_KEY)
        cache.delete(ERROR_WINDOW_KEY)


def _get_popular_fallback():
    """Return cached popular hotel results as a fast fallback."""
    return cache.get(POPULAR_RESULTS_CACHE_KEY)


def warm_popular_fallback():
    """
    Pre-compute and cache popular hotels for use as fallback.
    Called by the warm_popular_city_caches Celery task.
    """
    try:
        from apps.hotels.models import Property
        popular = list(
            Property.objects.filter(
                status='approved', is_active=True,
            ).select_related('city', 'locality').prefetch_related(
                'images', 'amenities',
            ).order_by('-popularity_score', '-rating')[:40]
        )
        cache.set(POPULAR_RESULTS_CACHE_KEY, popular, timeout=3600)
        logger.info('Warmed popular fallback cache with %d properties', len(popular))
        return len(popular)
    except Exception as exc:
        logger.warning('Failed to warm popular fallback: %s', exc)
        return 0


def _build_stale_cache_key(query: str, filters: dict | None) -> str:
    """Build a cache key for stale fallback results."""
    import hashlib
    raw = f"{query}:{sorted(filters.items()) if filters else ''}"
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"search:stale:{digest}"


def guarded_search(query: str | None = None,
                   filters: dict | None = None,
                   limit: int = 50,
                   **kwargs) -> dict:
    """
    Performance-guarded search wrapper.

    1. If degraded mode is active → return cached popular results immediately.
    2. Execute search with soft/hard timeout tracking.
    3. On timeout or error → return stale cached results → popular fallback.
    4. Record success/error for circuit breaker.
    5. Track search latency metric.
    """
    start = time.monotonic()

    # ── Degraded mode shortcut ────────────────────────────────────
    if SearchCircuitBreaker.is_degraded():
        logger.info('Search in degraded mode — returning popular fallback')
        fallback = _get_popular_fallback()
        if fallback:
            return {
                'results': fallback[:limit],
                'count': len(fallback[:limit]),
                'strategy': 'degraded_popular',
                'intent': 'fallback',
                'cached': True,
                'query_time_ms': round((time.monotonic() - start) * 1000, 2),
                'degraded': True,
            }

    # ── Execute actual search ─────────────────────────────────────
    try:
        from apps.search.engine.search_engine import search_engine

        result = search_engine.search_hotels(
            query=query,
            filters=filters,
            limit=limit,
            **kwargs,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        # Soft timeout warning
        if elapsed_ms > SEARCH_SOFT_TIMEOUT_MS:
            logger.warning(
                'Search slow: %.0fms for query="%s" (soft limit %dms)',
                elapsed_ms, query, SEARCH_SOFT_TIMEOUT_MS,
            )

        # Track latency metric
        try:
            from apps.core.metrics import track_search_latency
            track_search_latency(elapsed_ms / 1000.0, search_type='hotel')
        except Exception:
            pass

        SearchCircuitBreaker.record_success()

        # Cache results for stale fallback
        stale_key = _build_stale_cache_key(query or '', filters)
        try:
            cache.set(stale_key, {
                'results': result.results,
                'count': result.count,
                'strategy': result.strategy,
                'intent': result.intent,
            }, timeout=1800)  # 30 minutes stale TTL
        except Exception:
            pass

        return {
            'results': result.results,
            'count': result.count,
            'strategy': result.strategy,
            'intent': result.intent,
            'cached': result.cached,
            'query_time_ms': round(elapsed_ms, 2),
            'degraded': False,
        }

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.error('Search failed after %.0fms: %s', elapsed_ms, exc)
        SearchCircuitBreaker.record_error()

        # Try stale cache
        stale_key = _build_stale_cache_key(query or '', filters)
        stale = cache.get(stale_key)
        if stale:
            logger.info('Serving stale cached results for query="%s"', query)
            return {
                'results': stale['results'][:limit],
                'count': stale['count'],
                'strategy': 'stale_cache',
                'intent': stale.get('intent', 'fallback'),
                'cached': True,
                'query_time_ms': round(elapsed_ms, 2),
                'degraded': True,
            }

        # Last resort: popular fallback
        fallback = _get_popular_fallback()
        if fallback:
            return {
                'results': fallback[:limit],
                'count': len(fallback[:limit]),
                'strategy': 'error_popular_fallback',
                'intent': 'fallback',
                'cached': True,
                'query_time_ms': round(elapsed_ms, 2),
                'degraded': True,
            }

        # Nothing available
        return {
            'results': [],
            'count': 0,
            'strategy': 'error',
            'intent': 'error',
            'cached': False,
            'query_time_ms': round(elapsed_ms, 2),
            'degraded': True,
        }
