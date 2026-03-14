"""
DistributedInventoryLock — Per-date-slot Redis distributed lock for inventory.

Problem this solves:
  A single booking-range lock (e.g. "Mar 1→Mar 5") allows two OVERLAPPING
  ranges (e.g. "Mar 3→Mar 7") to acquire locks simultaneously because the
  lock keys differ.  Per-date slot locking prevents any date from being
  double-booked regardless of the booking range shape.

Strategy:
  1. Acquire one Redis lock per night in [check_in, check_out)
  2. Dates sorted before acquisition → consistent lock ordering, no deadlock
  3. SELECT FOR UPDATE inside the lock adds DB-level safety
  4. Falls back to threading.Lock when Redis unavailable (dev/test)

Usage (preferred):
    from apps.inventory.lock_manager import acquire_hold_locked

    holds = acquire_hold_locked(
        room_type_id=room_type.id,
        check_in=date(2026, 3, 10),
        check_out=date(2026, 3, 13),
        rooms=2,
    )

Or as a context manager:
    with DistributedInventoryLock(room_type_id, check_in, check_out):
        holds = acquire_hold(room_type_id, check_in, check_out, rooms=2)
"""
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger('zygotrip.inventory.locks')


# ── Lock key helpers ──────────────────────────────────────────────────────────

def _slot_key(room_type_id: int, slot_date: date) -> str:
    """
    Redis key for one (room_type, date) inventory slot.
    Pattern: inv_slot:{room_type_id}:{YYYY-MM-DD}
    """
    return f"inv_slot:{room_type_id}:{slot_date.isoformat()}"


def _date_range(check_in: date, check_out: date) -> List[date]:
    """Return sorted list of dates [check_in, check_out)."""
    dates = []
    current = check_in
    while current < check_out:
        dates.append(current)
        current += timedelta(days=1)
    return dates


# ── Core context manager ──────────────────────────────────────────────────────

@contextmanager
def acquire_inventory_slot_locks(
    room_type_id: int,
    check_in: date,
    check_out: date,
    ttl_ms: int = 30_000,
    timeout: float = 10.0,
) -> Iterator[List[str]]:
    """
    Acquire per-date Redis locks for every night in [check_in, check_out).

    Yields:
        List of locked key strings.

    Releases all locks on exit (even on exception).

    Raises:
        TimeoutError: If any slot lock cannot be acquired within `timeout`.
    """
    from apps.booking.distributed_locks import (
        RedisDistributedLock,
        ThreadLocalLock,
        _get_redis_client,
    )

    slot_dates = _date_range(check_in, check_out)
    if not slot_dates:
        yield []
        return

    # Sort ascending — consistent ordering prevents deadlocks
    slot_dates.sort()
    keys = [_slot_key(room_type_id, d) for d in slot_dates]

    client = _get_redis_client()
    # Track acquired locks as (lock_type, lock_obj) tuples
    acquired: List[Tuple[str, object]] = []

    try:
        if client is not None:
            # ── Redis path ────────────────────────────────────────────────
            for key in keys:
                lock = RedisDistributedLock(
                    client, key,
                    ttl_ms=ttl_ms,
                    retry_interval=0.02,    # 20ms spin — tight loop for inventory
                )
                if not lock.acquire(timeout=timeout):
                    raise TimeoutError(
                        f"Inventory slot lock timeout: key={key} "
                        f"(room_type={room_type_id}, {check_in}→{check_out})"
                    )
                acquired.append(('redis', lock))
                logger.debug("Acquired Redis slot lock: %s", key)
        else:
            # ── Thread-local fallback (dev / no Redis) ────────────────────
            for key in keys:
                tl = ThreadLocalLock(key, timeout=timeout)
                tl.__enter__()
                acquired.append(('thread', tl))
                logger.debug("Acquired thread slot lock (Redis unavailable): %s", key)

        logger.info(
            "Inventory slot locks acquired: room_type=%s nights=%d (%s→%s)",
            room_type_id, len(acquired), check_in, check_out,
        )
        yield keys

    finally:
        # Release in REVERSE acquisition order — symmetric unlock
        for lock_type, lock in reversed(acquired):
            try:
                if lock_type == 'redis':
                    lock.release()
                else:
                    lock.__exit__(None, None, None)
            except Exception as exc:
                logger.warning("Failed to release inventory slot lock: %s", exc)

        if acquired:
            logger.debug(
                "Inventory slot locks released: room_type=%s (%s→%s)",
                room_type_id, check_in, check_out,
            )


# ── Class-based wrapper ───────────────────────────────────────────────────────

class DistributedInventoryLock:
    """
    Class-based distributed lock for inventory date slots.

    Wraps ``acquire_inventory_slot_locks`` in a reusable object.

    Example::

        lock = DistributedInventoryLock(room_type.id, check_in, check_out)
        with lock:
            holds = acquire_hold(room_type.id, check_in, check_out, rooms=2)
    """

    def __init__(
        self,
        room_type_id: int,
        check_in: date,
        check_out: date,
        ttl_ms: int = 30_000,
        timeout: float = 10.0,
    ):
        self.room_type_id = room_type_id
        self.check_in = check_in
        self.check_out = check_out
        self.ttl_ms = ttl_ms
        self.timeout = timeout
        self._ctx: Optional[object] = None

    def __enter__(self):
        self._ctx = acquire_inventory_slot_locks(
            self.room_type_id, self.check_in, self.check_out,
            ttl_ms=self.ttl_ms, timeout=self.timeout,
        )
        return self._ctx.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ctx is not None:
            return self._ctx.__exit__(exc_type, exc_val, exc_tb)
        return False


# ── Public convenience API ────────────────────────────────────────────────────

def acquire_hold_locked(
    room_type_id: int,
    check_in: date,
    check_out: date,
    rooms: int = 1,
    booking_context=None,
    hold_minutes: int = 15,
):
    """
    Preferred entry point for creating inventory holds in production.

    Combines:
      1. Per-date Redis distributed locks (prevents overlapping-range race)
      2. DB-level SELECT FOR UPDATE inside acquire_hold (prevents race within same DB tx)

    Args:
        room_type_id:      RoomType PK
        check_in:          First night
        check_out:         Checkout date (exclusive)
        rooms:             Number of rooms to hold
        booking_context:   BookingContext instance (optional)
        hold_minutes:      Hold TTL in minutes

    Returns:
        List of InventoryHold objects created

    Raises:
        TimeoutError:               Lock contention — retry at higher level
        InsufficientInventoryError: Not enough rooms available
        RestrictionError:           CTA/CTD/min-stay/closure violations
    """
    from apps.inventory.atomic_ops import acquire_hold

    with DistributedInventoryLock(room_type_id, check_in, check_out):
        return acquire_hold(
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            rooms=rooms,
            booking_context=booking_context,
            hold_minutes=hold_minutes,
        )
