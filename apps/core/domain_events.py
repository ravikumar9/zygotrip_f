"""
ZygoTrip Typed Domain Events — Kafka-ready strongly-typed event dataclasses.

Companion to apps/core/event_bus.py.

All domain events are dataclasses that:
  1. Can be published via event_bus.publish_typed(event) (Celery/Kafka backends)
  2. Can be published via event_bus.publish(DomainEvent(...)) for in-process sync
  3. Are JSON-serializable via .to_dict() / .to_json()

Usage::

    from apps.core.domain_events import BookingConfirmedEvent, publish_event

    publish_event(BookingConfirmedEvent(
        booking_id=booking.id,
        booking_uuid=str(booking.uuid),
        property_id=booking.property_id,
        user_id=booking.user_id,
        check_in=str(booking.check_in),
        check_out=str(booking.check_out),
        total_amount=str(booking.total_amount),
        gateway=payment.gateway,
    ))

Kafka-ready design:
  - Each event_type maps to a Kafka topic: zygotrip.{event_type}
    e.g. booking.confirmed → zygotrip.booking.confirmed
  - Schema versioned via schema_version field
  - event_id is UUID — safe idempotency key for exactly-once consumers
"""
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from django.utils import timezone

logger = logging.getLogger('zygotrip.domain_events')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid4())


def _now() -> str:
    return timezone.now().isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# BASE EVENT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TypedDomainEvent:
    """
    Base for all strongly-typed ZygoTrip domain events.

    Immutable after creation — use dataclass(frozen=True) in subclasses
    when Kafka guarantees strict ordering (topic + partition key = event_id).
    """
    event_id: str = field(default_factory=_uuid)
    event_type: str = field(default='domain_event')
    occurred_at: str = field(default_factory=_now)
    schema_version: str = field(default='1.0')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe). Used for Celery kwargs + Kafka value."""
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def to_legacy_payload(self) -> Dict[str, Any]:
        """Convert to legacy event_bus.DomainEvent.payload dict (for backwards compat)."""
        d = self.to_dict()
        d.pop('event_id', None)
        d.pop('event_type', None)
        d.pop('occurred_at', None)
        d.pop('schema_version', None)
        return d


# ══════════════════════════════════════════════════════════════════════════════
# BOOKING EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookingConfirmedEvent(TypedDomainEvent):
    """
    booking.confirmed — payment succeeded, Booking row created.
    Kafka topic: zygotrip.booking.confirmed
    """
    event_type: str = field(default='booking.confirmed')
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    property_id: Optional[int] = None
    property_name: Optional[str] = None
    room_type_id: Optional[int] = None
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    nights: Optional[int] = None
    rooms: Optional[int] = None
    total_amount: Optional[str] = None
    currency: str = 'INR'
    gateway: Optional[str] = None


@dataclass
class BookingCancelledEvent(TypedDomainEvent):
    """
    booking.cancelled — booking cancelled by user, admin, or system.
    Kafka topic: zygotrip.booking.cancelled
    """
    event_type: str = field(default='booking.cancelled')
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    property_id: Optional[int] = None
    user_id: Optional[int] = None
    refund_amount: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None  # 'user' | 'admin' | 'system'


@dataclass
class BookingCheckedInEvent(TypedDomainEvent):
    """booking.checked_in — property marked guest as checked in."""
    event_type: str = field(default='booking.checked_in')
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    property_id: Optional[int] = None
    user_id: Optional[int] = None


@dataclass
class BookingCheckedOutEvent(TypedDomainEvent):
    """booking.checked_out — property marked guest as checked out."""
    event_type: str = field(default='booking.checked_out')
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    property_id: Optional[int] = None
    user_id: Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PaymentSucceededEvent(TypedDomainEvent):
    """payment.succeeded — gateway confirmed payment."""
    event_type: str = field(default='payment.succeeded')
    payment_transaction_id: Optional[int] = None
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    user_id: Optional[int] = None
    amount: Optional[str] = None
    currency: str = 'INR'
    gateway: Optional[str] = None
    gateway_ref: Optional[str] = None


@dataclass
class PaymentFailedEvent(TypedDomainEvent):
    """payment.failed — gateway rejected or timed out."""
    event_type: str = field(default='payment.failed')
    payment_transaction_id: Optional[int] = None
    booking_id: Optional[int] = None
    user_id: Optional[int] = None
    amount: Optional[str] = None
    gateway: Optional[str] = None
    failure_reason: Optional[str] = None
    is_retryable: bool = True


@dataclass
class RefundProcessedEvent(TypedDomainEvent):
    """payment.refunded — refund issued to user."""
    event_type: str = field(default='payment.refunded')
    booking_id: Optional[int] = None
    booking_uuid: Optional[str] = None
    user_id: Optional[int] = None
    refund_amount: Optional[str] = None
    gateway: Optional[str] = None
    refund_ref: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class InventoryHoldCreatedEvent(TypedDomainEvent):
    """inventory.hold_created — checkout reserved rooms."""
    event_type: str = field(default='inventory.hold_created')
    room_type_id: Optional[int] = None
    property_id: Optional[int] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    rooms: int = 1
    session_id: Optional[str] = None
    hold_expires_at: Optional[str] = None


@dataclass
class InventoryReleasedEvent(TypedDomainEvent):
    """inventory.released — holds released (expired, cancelled, or converted)."""
    event_type: str = field(default='inventory.released')
    hold_ids: List[str] = field(default_factory=list)
    room_type_id: Optional[int] = None
    property_id: Optional[int] = None
    reason: Optional[str] = None   # 'expired' | 'cancelled' | 'converted'
    rooms_released: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# REVIEW EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewSubmittedEvent(TypedDomainEvent):
    """review.submitted — user submitted a review (pending moderation)."""
    event_type: str = field(default='review.submitted')
    review_id: Optional[int] = None
    property_id: Optional[int] = None
    user_id: Optional[int] = None
    overall_rating: Optional[str] = None


@dataclass
class ReviewApprovedEvent(TypedDomainEvent):
    """review.approved — admin approved a review (now publicly visible)."""
    event_type: str = field(default='review.approved')
    review_id: Optional[int] = None
    property_id: Optional[int] = None
    overall_rating: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# PRICING EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PriceChangedEvent(TypedDomainEvent):
    """price.changed — property price changed beyond 5% threshold."""
    event_type: str = field(default='price.changed')
    property_id: Optional[int] = None
    room_type_id: Optional[int] = None
    old_price: Optional[str] = None
    new_price: Optional[str] = None
    change_percent: Optional[float] = None
    change_direction: Optional[str] = None  # 'up' | 'down'


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE PUBLISHER
# ══════════════════════════════════════════════════════════════════════════════

def publish_event(typed_event: TypedDomainEvent) -> None:
    """
    Publish a typed domain event via the configured event bus.

    Routes through the legacy in-process bus (sync listeners) AND via
    the async Celery/Kafka backend (if configured).

    This is the recommended way to emit domain events from service code.

    Example::

        from apps.core.domain_events import BookingConfirmedEvent, publish_event

        publish_event(BookingConfirmedEvent(
            booking_id=booking.id,
            ...
        ))
    """
    try:
        from apps.core.event_bus import event_bus, DomainEvent as LegacyDomainEvent

        # 1. Route through in-process bus for synchronous local listeners
        legacy = LegacyDomainEvent(
            event_type=typed_event.event_type,
            payload=typed_event.to_legacy_payload(),
        )
        event_bus.publish(legacy)

        # 2. Also dispatch async via Celery 'events' queue (if backend configured)
        try:
            from celery import current_app
            current_app.send_task(
                'apps.core.event_bus_tasks.dispatch_domain_event',
                kwargs={
                    'event_type': typed_event.event_type,
                    'event_payload': typed_event.to_dict(),
                },
                queue='events',
                routing_key=typed_event.event_type,
            )
        except Exception as celery_exc:
            # Celery unavailable in dev — OK, in-process bus is sufficient
            logger.debug(
                'Async event dispatch skipped (Celery unavailable): %s',
                celery_exc,
            )

    except Exception as exc:
        # Event publishing must NEVER crash the primary flow
        logger.error(
            'publish_event FAILED: type=%s id=%s error=%s',
            typed_event.event_type, typed_event.event_id, exc,
            exc_info=True,
        )
