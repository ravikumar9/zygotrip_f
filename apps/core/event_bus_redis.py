"""
System 13 Enhancement — Redis Streams Backed Event Bus.

Extends the in-process EventBus with optional Redis Streams backing for
cross-process event delivery:
  - Publishes events to Redis XADD in addition to in-process dispatch
  - Consumer group support for Celery workers (XREADGROUP)
  - Event persistence and replay capability
  - Dead-letter queue for failed events
  - Graceful fallback to in-process when Redis is unavailable

Usage:
    from apps.core.event_bus_redis import redis_event_bus

    # Publishing works the same as in-process event_bus:
    redis_event_bus.publish(DomainEvent(
        event_type='booking.confirmed',
        payload={'booking_id': 123},
    ))

    # Start a consumer (in a Celery worker or management command):
    redis_event_bus.start_consumer('worker-1', ['booking.*', 'inventory.*'])
"""
import json
import logging
import time
import threading
from typing import Optional

from django.conf import settings

from apps.core.event_bus import EventBus, DomainEvent, event_bus

logger = logging.getLogger('zygotrip.events.redis')

# Redis Streams config
STREAM_KEY = 'zygotrip:events'
CONSUMER_GROUP = 'zygotrip-workers'
DLQ_KEY = 'zygotrip:events:dlq'
MAX_STREAM_LEN = 50000  # Trim stream to last 50k events


def _get_redis():
    """Get Redis connection, return None if unavailable."""
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection('default')
        conn.ping()
        return conn
    except Exception:
        return None


class RedisStreamEventBus(EventBus):
    """
    EventBus with Redis Streams backing.

    publish() → in-process dispatch + XADD to Redis Stream
    consume() → XREADGROUP from Redis Stream (for cross-process delivery)

    Falls back to in-process only if Redis is unavailable.
    """

    def __init__(self):
        super().__init__()
        self._redis = None
        self._consumer_running = False
        self._ensure_stream()

    def _ensure_stream(self):
        """Create consumer group if it doesn't exist."""
        redis = _get_redis()
        if not redis:
            return
        self._redis = redis
        try:
            redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id='0', mkstream=True)
        except Exception:
            # Group already exists
            pass

    def publish(self, event: DomainEvent):
        """Publish event: in-process + Redis Stream."""
        # Always dispatch in-process first
        super().publish(event)

        # Then persist to Redis Stream
        redis = self._redis or _get_redis()
        if not redis:
            return

        try:
            event_data = {
                'event_type': event.event_type,
                'event_id': event.event_id,
                'payload': json.dumps(event.payload, default=str),
                'user_id': str(event.user_id or ''),
                'source': event.source,
                'timestamp': str(event.timestamp),
            }
            redis.xadd(STREAM_KEY, event_data, maxlen=MAX_STREAM_LEN)
            logger.debug('Published to Redis Stream: %s (id=%s)', event.event_type, event.event_id[:8])
        except Exception as exc:
            logger.warning('Redis Stream publish failed (in-process delivery succeeded): %s', exc)

    def consume_batch(self, consumer_name: str, count: int = 10, block_ms: int = 5000):
        """
        Read a batch of events from Redis Stream using consumer group.

        Returns list of (stream_id, DomainEvent) tuples.
        Called by Celery task or management command.
        """
        redis = self._redis or _get_redis()
        if not redis:
            return []

        try:
            results = redis.xreadgroup(
                CONSUMER_GROUP, consumer_name,
                {STREAM_KEY: '>'},
                count=count,
                block=block_ms,
            )
        except Exception as exc:
            logger.error('Redis XREADGROUP failed: %s', exc)
            return []

        events = []
        if results:
            for stream_name, messages in results:
                for msg_id, data in messages:
                    try:
                        # Decode bytes to strings
                        decoded = {}
                        for k, v in data.items():
                            key = k.decode() if isinstance(k, bytes) else k
                            val = v.decode() if isinstance(v, bytes) else v
                            decoded[key] = val

                        payload = json.loads(decoded.get('payload', '{}'))
                        event = DomainEvent(
                            event_type=decoded.get('event_type', ''),
                            payload=payload,
                            user_id=int(decoded['user_id']) if decoded.get('user_id') else None,
                            event_id=decoded.get('event_id', ''),
                            source=decoded.get('source', ''),
                        )
                        events.append((msg_id, event))
                    except Exception as exc:
                        logger.error('Failed to deserialize event %s: %s', msg_id, exc)
                        self._send_to_dlq(redis, msg_id, data)

        return events

    def ack(self, stream_ids):
        """Acknowledge processed events."""
        redis = self._redis or _get_redis()
        if not redis or not stream_ids:
            return
        try:
            redis.xack(STREAM_KEY, CONSUMER_GROUP, *stream_ids)
        except Exception as exc:
            logger.error('Redis XACK failed: %s', exc)

    def replay(self, start_id='0', count=100):
        """
        Replay events from a specific stream ID (for recovery).
        Does NOT use consumer groups — reads raw stream.
        """
        redis = self._redis or _get_redis()
        if not redis:
            return []

        try:
            results = redis.xrange(STREAM_KEY, min=start_id, count=count)
            events = []
            for msg_id, data in results:
                decoded = {}
                for k, v in data.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    val = v.decode() if isinstance(v, bytes) else v
                    decoded[key] = val
                events.append({
                    'stream_id': msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                    'event_type': decoded.get('event_type'),
                    'event_id': decoded.get('event_id'),
                    'payload': json.loads(decoded.get('payload', '{}')),
                    'timestamp': decoded.get('timestamp'),
                })
            return events
        except Exception as exc:
            logger.error('Redis Stream replay failed: %s', exc)
            return []

    def pending_count(self):
        """Return number of pending (unacknowledged) events in the consumer group."""
        redis = self._redis or _get_redis()
        if not redis:
            return 0
        try:
            info = redis.xpending(STREAM_KEY, CONSUMER_GROUP)
            return info.get('pending', 0) if isinstance(info, dict) else (info[0] if info else 0)
        except Exception:
            return 0

    def stream_length(self):
        """Return total length of the event stream."""
        redis = self._redis or _get_redis()
        if not redis:
            return 0
        try:
            return redis.xlen(STREAM_KEY)
        except Exception:
            return 0

    @staticmethod
    def _send_to_dlq(redis, msg_id, data):
        """Move unprocessable event to dead-letter queue."""
        try:
            dlq_entry = {
                'original_id': msg_id if isinstance(msg_id, str) else msg_id.decode(),
                'data': json.dumps(
                    {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                     for k, v in data.items()},
                    default=str,
                ),
                'failed_at': str(time.time()),
            }
            redis.xadd(DLQ_KEY, dlq_entry, maxlen=5000)
        except Exception as exc:
            logger.error('Failed to send to DLQ: %s', exc)


# ── Singleton ────────────────────────────────────────────────────────────────

redis_event_bus = RedisStreamEventBus()

# Re-register the built-in listeners on the Redis-backed bus
from apps.core.event_bus import (
    _on_inventory_change,
    _on_booking_event,
    _on_supplier_response,
)
redis_event_bus.subscribe('inventory.*', _on_inventory_change)
redis_event_bus.subscribe('booking.*', _on_booking_event)
redis_event_bus.subscribe('supplier.response', _on_supplier_response)
