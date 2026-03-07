"""
Production-grade distributed lock system for ZygoTrip booking engine.

Priority:
  1. Redis distributed lock (multi-process safe, horizontally scalable)
  2. Threading local lock fallback (single-process, dev/test only)

Usage:
    with acquire_booking_lock(property_id, room_type_id, check_in, check_out):
        # critical section — only one process can be here at a time
        ...

    # Or context-manager style:
    lock = BookingLock(key="booking:prop:42:rt:7:2026-03-01")
    with lock:
        ...
"""

import hashlib
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("zygotrip.locks")

# ─── Try to import Redis (optional dependency) ────────────────────────────────
try:
    import redis as _redis_module
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis-py not installed. Falling back to threading lock.")


# ─── Redis helper ─────────────────────────────────────────────────────────────

def _get_redis_client() -> Optional[object]:
    """Return a Redis client if Redis is reachable; None otherwise."""
    if not _REDIS_AVAILABLE:
        return None

    from django.conf import settings
    host = getattr(settings, "REDIS_HOST", "localhost")
    port = int(getattr(settings, "REDIS_PORT", 6379))

    try:
        client = _redis_module.Redis(
            host=host, port=port, db=3,
            socket_connect_timeout=0.3,
            socket_timeout=0.5,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unreachable for locks (%s). Using thread lock.", exc)
        return None


# ─── Thread-local fallback lock registry ─────────────────────────────────────

_thread_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _get_thread_lock(key: str) -> threading.Lock:
    with _registry_lock:
        if key not in _thread_locks:
            _thread_locks[key] = threading.Lock()
        return _thread_locks[key]


# ─── Redis distributed lock (SET NX PX pattern) ──────────────────────────────

class RedisDistributedLock:
    """
    Simple, safe Redis distributed lock using SET NX PX.
    Releases only if value matches (owner token) to prevent stealing.
    """

    RELEASE_SCRIPT = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
    """

    def __init__(self, client, key: str, ttl_ms: int = 30_000, retry_interval: float = 0.05):
        self._client = client
        self._key = key
        self._ttl_ms = ttl_ms
        self._retry_interval = retry_interval
        self._token: Optional[str] = None

    def acquire(self, timeout: float = 10.0) -> bool:
        token = str(uuid.uuid4())
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            acquired = self._client.set(
                self._key, token,
                px=self._ttl_ms,
                nx=True,
            )
            if acquired:
                self._token = token
                return True
            time.sleep(self._retry_interval)
        return False

    def release(self) -> None:
        if self._token is None:
            return
        try:
            self._client.eval(self.RELEASE_SCRIPT, 1, self._key, self._token)
        except Exception as exc:
            logger.warning("Redis lock release failed for %s: %s", self._key, exc)
        finally:
            self._token = None

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire distributed lock: {self._key}")
        return self

    def __exit__(self, *_):
        self.release()


# ─── Thread-local lock (fallback) ────────────────────────────────────────────

class ThreadLocalLock:
    def __init__(self, key: str, timeout: float = 10.0):
        self._lock = _get_thread_lock(key)
        self._timeout = timeout

    def __enter__(self):
        acquired = self._lock.acquire(timeout=self._timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire thread lock within {self._timeout}s")
        return self

    def __exit__(self, *_):
        self._lock.release()


# ─── Public API ───────────────────────────────────────────────────────────────

def make_inventory_lock_key(hotel_id: int, room_type_id: int, date) -> str:
    """
    Lock key for a single inventory date slot.
    Pattern: inventory_lock:{hotel_id}:{room_type}:{date}
    Used for per-date inventory mutations.
    """
    return f"inventory_lock:{hotel_id}:{room_type_id}:{date}"


def make_booking_lock_key(property_id: int, room_type_id: int, check_in, check_out) -> str:
    """
    Deterministic lock key for a specific room/date range combo.
    Uses readable pattern: inventory_lock:{property_id}:{room_type_id}:{check_in}_{check_out}
    Also stores a short hash suffix for collision safety.
    """
    raw = f"booking:{property_id}:{room_type_id}:{check_in}:{check_out}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"inventory_lock:{property_id}:{room_type_id}:{check_in}_{check_out}:{digest}"


@contextmanager
def acquire_booking_lock(
    property_id: int,
    room_type_id: int,
    check_in,
    check_out,
    ttl_ms: int = 30_000,
    timeout: float = 10.0,
):
    """
    Context manager that acquires a distributed lock for a booking slot.

    Uses Redis if available, falls back to threading.Lock for local dev.

    Args:
        property_id: The property being booked.
        room_type_id: The room type being reserved.
        check_in / check_out: Date objects for the booking window.
        ttl_ms: Lock TTL in milliseconds (safety expiry — default 30s).
        timeout: How long to wait for the lock (seconds).

    Raises:
        TimeoutError: If the lock cannot be acquired within `timeout`.
    """
    key = make_booking_lock_key(property_id, room_type_id, check_in, check_out)
    client = _get_redis_client()

    if client is not None:
        lock = RedisDistributedLock(client, key, ttl_ms=ttl_ms, retry_interval=0.05)
        logger.debug("Acquiring Redis lock: %s", key)
        with lock:
            yield
    else:
        logger.debug("Acquiring thread lock (Redis unavailable): %s", key)
        with ThreadLocalLock(key, timeout=timeout):
            yield


# ─── Booking Retry Queue (kept for compatibility) ────────────────────────────

class BookingRetryQueue:
    """
    In-memory retry queue for booking operations that fail due to lock contention.
    Production: replace with a Celery task queue.
    """

    _lock = threading.Lock()
    _queue: list[dict] = []

    @classmethod
    def enqueue(cls, booking_id: int) -> None:
        with cls._lock:
            cls._queue.append({
                "booking_id": booking_id,
                "timestamp": time.time(),
            })

    @classmethod
    def dequeue(cls) -> Optional[dict]:
        with cls._lock:
            return cls._queue.pop(0) if cls._queue else None

    @classmethod
    def size(cls) -> int:
        with cls._lock:
            return len(cls._queue)