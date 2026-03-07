"""
Section 7 + 17 — Event Streaming Bus

In-process event bus that decouples producers (views, services) from
consumers (analytics, cache invalidation, notifications, audit log).

In production replace the in-memory dispatcher with Redis Streams or
Kafka — the publish() / subscribe() API stays the same.

Usage:
    from apps.core.event_bus import event_bus, DomainEvent

    # -- Publish (from any service) --
    event_bus.publish(DomainEvent(
        event_type='booking.confirmed',
        payload={'booking_id': 123, 'amount': '4500.00'},
        user_id=request.user.id,
    ))

    # -- Subscribe (at module load in AppConfig.ready()) --
    event_bus.subscribe('booking.confirmed', on_booking_confirmed)
    event_bus.subscribe('booking.*', audit_all_bookings)
"""
import fnmatch
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from django.utils import timezone

logger = logging.getLogger('zygotrip.events')


# ============================================================================
# Domain Event DTO
# ============================================================================

@dataclass(frozen=True)
class DomainEvent:
    event_type: str                           # e.g. 'booking.confirmed'
    payload: dict[str, Any] = field(default_factory=dict)
    user_id: int | None = None
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=timezone.now)
    source: str = ''                          # originating service/module


# ============================================================================
# Event Bus
# ============================================================================

class EventBus:
    """
    Simple in-process pub/sub with glob-pattern matching.
    Thread-safe; listeners are called synchronously in the publisher's thread.
    For async processing, listeners should defer to Celery tasks.
    """

    def __init__(self):
        self._listeners: list[tuple[str, Callable]] = []
        self._lock = threading.Lock()
        self._event_log: list[dict] = []      # ring buffer (last 1 000)
        self._LOG_MAX = 1000

    # ── Publish ──────────────────────────────────────────────────────────

    def publish(self, event: DomainEvent):
        """
        Publish an event to all matching subscribers.
        Subscribers matching on exact type or glob pattern receive the event.
        """
        self._record(event)
        matched = 0
        with self._lock:
            listeners = list(self._listeners)  # snapshot

        for pattern, callback in listeners:
            if self._matches(pattern, event.event_type):
                try:
                    callback(event)
                    matched += 1
                except Exception as exc:
                    logger.error(
                        "Event listener %s failed for %s: %s",
                        callback.__qualname__, event.event_type, exc,
                    )

        logger.debug(
            "Published %s (id=%s) → %d listeners",
            event.event_type, event.event_id[:8], matched,
        )

    # ── Subscribe / Unsubscribe ──────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Callable):
        """
        Register a listener for events matching ``pattern``.
        Supports exact match and glob (*) patterns:
            'booking.confirmed'   — exact
            'booking.*'           — all booking events
            '*'                   — everything
        """
        with self._lock:
            self._listeners.append((pattern, callback))
        logger.debug("Subscribed %s to '%s'", callback.__qualname__, pattern)

    def unsubscribe(self, callback: Callable):
        """Remove all subscriptions for a callback."""
        with self._lock:
            self._listeners = [(p, cb) for p, cb in self._listeners if cb is not callback]

    # ── Query ────────────────────────────────────────────────────────────

    def recent_events(self, limit: int = 50) -> list[dict]:
        """Return recent events from the ring buffer."""
        return list(reversed(self._event_log[-limit:]))

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _matches(pattern: str, event_type: str) -> bool:
        if pattern == event_type:
            return True
        return fnmatch.fnmatch(event_type, pattern)

    def _record(self, event: DomainEvent):
        entry = {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'user_id': event.user_id,
            'timestamp': str(event.timestamp),
            'payload_keys': list(event.payload.keys()),
        }
        self._event_log.append(entry)
        if len(self._event_log) > self._LOG_MAX:
            self._event_log = self._event_log[-self._LOG_MAX:]


# ── Singleton ────────────────────────────────────────────────────────────────

event_bus = EventBus()


# ============================================================================
# Built-in listeners (auto-registered on import)
# ============================================================================

def _on_inventory_change(event: DomainEvent):
    """Invalidate availability cache + recompute InventoryPool on inventory mutations."""
    room_type_id = event.payload.get('room_type_id')
    target_date = event.payload.get('date')
    if not room_type_id:
        return
    try:
        from apps.search.engine.cache_manager import availability_cache
        availability_cache.invalidate_availability(room_type_id)
    except Exception:
        pass
    # Recompute pool asynchronously
    if target_date:
        try:
            from apps.inventory.models import InventoryPool
            from apps.rooms.models import RoomType
            rt = RoomType.objects.get(id=room_type_id)
            InventoryPool.recompute(rt, target_date)
        except Exception as e:
            logger.warning("Pool recompute failed for %s/%s: %s", room_type_id, target_date, e)


def _on_booking_event(event: DomainEvent):
    """Track booking-related analytics events."""
    try:
        from apps.core.analytics import track_event, AnalyticsEvent
        etype_map = {
            'booking.confirmed': AnalyticsEvent.EVENT_BOOKING_CONFIRMED,
            'booking.cancelled': AnalyticsEvent.EVENT_BOOKING_CANCELLED,
            'booking.payment_success': AnalyticsEvent.EVENT_PAYMENT_SUCCESS,
            'booking.payment_failed': AnalyticsEvent.EVENT_PAYMENT_FAIL,
        }
        analytics_type = etype_map.get(event.event_type)
        if analytics_type:
            track_event(
                analytics_type,
                user=None,
                property_id=event.payload.get('property_id'),
                amount=event.payload.get('amount'),
                properties=event.payload,
            )
    except Exception as e:
        logger.warning("Analytics tracking failed for %s: %s", event.event_type, e)


def _on_supplier_response(event: DomainEvent):
    """Update SupplierHealth metrics on every supplier API call."""
    supplier_name = event.payload.get('supplier_name')
    if not supplier_name:
        return
    try:
        from apps.inventory.models import SupplierHealth
        sh, _ = SupplierHealth.objects.get_or_create(supplier_name=supplier_name)
        latency = event.payload.get('latency_ms', 0)
        if event.payload.get('success'):
            sh.record_success(latency)
        else:
            sh.record_failure(latency, is_timeout=event.payload.get('is_timeout', False))
    except Exception as e:
        logger.warning("SupplierHealth update failed for %s: %s", supplier_name, e)


def _on_review_created(event: DomainEvent):
    """
    On review creation: recompute property rating aggregate,
    invalidate search cache, and trigger ranking recomputation.
    """
    property_id = event.payload.get('property_id')
    if not property_id:
        return
    try:
        # Recompute aggregate rating on the search index
        from apps.search.models import PropertySearchIndex
        idx = PropertySearchIndex.objects.filter(property_id=property_id).first()
        if idx:
            from django.db.models import Avg
            from django.apps import apps
            try:
                Review = apps.get_model('hotels', 'Review')
                avg = Review.objects.filter(
                    property_id=property_id, is_verified=True,
                ).aggregate(avg=Avg('rating'))['avg']
                if avg is not None:
                    idx.review_score = float(avg)
                    idx.save(update_fields=['review_score'])
            except Exception:
                pass

        # Invalidate search cache for the affected property
        try:
            from apps.search.engine.cache_manager import price_cache
            price_cache.invalidate(f'property:{property_id}:*')
        except Exception:
            pass

        # Trigger async ranking recomputation
        try:
            from apps.core.tasks import bulk_update_property_rankings
            bulk_update_property_rankings.apply_async(
                kwargs={'property_ids': [property_id]},
                countdown=30,  # Debounce 30s
            )
        except Exception:
            pass

        logger.info("Review event processed for property=%s", property_id)

    except Exception as e:
        logger.warning("review_created handler failed for property=%s: %s", property_id, e)


# Auto-register built-in listeners
event_bus.subscribe('inventory.*', _on_inventory_change)
event_bus.subscribe('booking.*', _on_booking_event)
event_bus.subscribe('supplier.response', _on_supplier_response)
event_bus.subscribe('review.*', _on_review_created)
