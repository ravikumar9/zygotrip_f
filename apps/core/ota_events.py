"""Canonical OTA event catalog and publisher helpers.

Provides a stable public event vocabulary for external stream consumers while
reusing the internal dotted topic conventions already used by the in-process
event bus.
"""

from apps.core.event_bus import DomainEvent, event_bus


BOOKING_CREATED = 'booking_created'
BOOKING_CANCELLED = 'booking_cancelled'
INVENTORY_UPDATED = 'inventory_updated'
PRICE_UPDATED = 'price_updated'


OTA_EVENT_TOPIC_MAP = {
    BOOKING_CREATED: 'booking.created',
    BOOKING_CANCELLED: 'booking.cancelled',
    INVENTORY_UPDATED: 'inventory.updated',
    PRICE_UPDATED: 'pricing.updated',
}


def canonical_event_topic(event_name: str) -> str:
    """Resolve the internal event-bus topic for a canonical OTA event name."""
    return OTA_EVENT_TOPIC_MAP.get(event_name, event_name.replace('_', '.'))


def publish_ota_event(event_name: str, payload: dict | None = None, user_id: int | None = None, source: str = '') -> DomainEvent:
    """Publish a canonical OTA event to the internal event bus."""
    event = DomainEvent(
        event_type=canonical_event_topic(event_name),
        payload={
            'ota_event': event_name,
            **(payload or {}),
        },
        user_id=user_id,
        source=source,
    )
    event_bus.publish(event)
    return event