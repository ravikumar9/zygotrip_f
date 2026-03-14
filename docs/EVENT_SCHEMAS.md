# ZygoTrip Domain Event Schemas

## Overview

ZygoTrip uses a layered event bus architecture:

| Layer | Transport | Use Case |
|-------|-----------|----------|
| In-process (sync) | Python function calls | Same-request side effects (e.g., cache invalidation) |
| Celery queue (async) | Redis broker | Cross-service fanout, retryable tasks |
| Optional Kafka | Kafka topics | High-throughput analytics pipeline, audit log |

- **Base class**: `TypedDomainEvent` in `apps/core/domain_events.py`
- **Topic naming convention**: `zygotrip.{event_type}` (dots as separators, not underscores)
  - Example: `zygotrip.booking.confirmed`, `zygotrip.payment.succeeded`
- **Schema version**: Every event payload carries `schema_version` (current: `1`)
- **Envelope fields** present on every event:

```json
{
  "event_id": "uuid-v4",
  "event_type": "booking.confirmed",
  "schema_version": 1,
  "occurred_at": "2026-03-14T10:00:00Z",
  "producer": "apps.booking.services",
  "correlation_id": "request-trace-id",
  "payload": {}
}
```

---

## Booking Events

### `booking.confirmed`

- **Trigger**: Payment succeeds and booking status is set to `confirmed`
- **Producer**: `apps/booking/services.py` -> `confirm_booking()`
- **Consumers**:
  - Notification service (`apps/core/push_notification_service.py`) - sends FCM push + WhatsApp confirmation
  - Loyalty engine (`apps/core/loyalty.py`) - awards points
  - Analytics pipeline (`apps/core/analytics.py`) - records conversion event
  - Settlement engine (`apps/booking/settlement_tasks.py`) - enqueues settlement record

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Unique booking identifier |
| `property_id` | `integer` | Hotel property PK |
| `check_in` | `string (ISO 8601 date)` | Check-in date, e.g. 2026-04-01 |
| `check_out` | `string (ISO 8601 date)` | Check-out date |
| `total_amount` | `decimal string` | Total charged to guest including taxes |
| `guest_email` | `string` | Guest email address |
| `rooms` | `integer` | Number of rooms booked |
| `nights` | `integer` | Number of nights |

**Example**:

```json
{
  "event_type": "booking.confirmed",
  "schema_version": 1,
  "payload": {
    "booking_uuid": "a1b2c3d4-...",
    "property_id": 42,
    "check_in": "2026-04-01",
    "check_out": "2026-04-03",
    "total_amount": "8500.00",
    "guest_email": "guest@example.com",
    "rooms": 1,
    "nights": 2
  }
}
```

---

### `booking.cancelled`

- **Trigger**: Guest or owner cancels a confirmed booking
- **Producer**: `apps/booking/services.py` -> `cancel_booking()`
- **Consumers**:
  - Inventory service - releases room holds
  - Notification service - sends cancellation email/SMS/push
  - Refund processor (`apps/payments/gateways.py`)
  - Analytics pipeline

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Booking identifier |
| `property_id` | `integer` | Hotel property PK |
| `reason` | `string` | Cancellation reason code: guest_request, owner_request, no_show, system |
| `refund_amount` | `decimal string` | Amount to be refunded (may be 0.00 for non-refundable rates) |
| `cancelled_by` | `string` | Actor: guest, owner, admin, system |

---

### `booking.checked_in`

- **Trigger**: Property marks booking as checked-in via owner dashboard
- **Producer**: `apps/booking/services.py` -> `check_in_booking()`
- **Consumers**: Analytics, loyalty (start-of-stay tracking), WhatsApp notifications

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Booking identifier |
| `property_id` | `integer` | Hotel property PK |
| `timestamp` | `string (ISO 8601 datetime)` | Actual check-in time |

---

### `booking.checked_out`

- **Trigger**: Property marks booking as checked-out
- **Producer**: `apps/booking/services.py` -> `check_out_booking()`
- **Consumers**: Analytics, review solicitation task, settlement trigger

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Booking identifier |
| `property_id` | `integer` | Hotel property PK |
| `timestamp` | `string (ISO 8601 datetime)` | Actual check-out time |

---

## Payment Events

### `payment.succeeded`

- **Trigger**: Gateway callback confirmed, `PaymentTransaction.status` set to `success`
- **Producer**: `apps/payments/gateways.py` -> `verify_payment()`
- **Consumers**: Booking confirmation flow, ledger entry creation, analytics

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Associated booking |
| `amount` | `decimal string` | Amount charged |
| `currency` | `string (ISO 4217)` | Currency code, e.g. INR |
| `gateway` | `string` | Gateway used: wallet, cashfree, stripe, paytm_upi |
| `transaction_id` | `string` | Gateway-issued transaction ID |
| `idempotency_key` | `string` | Client-generated key to prevent double-charge |

---

### `payment.failed`

- **Trigger**: Gateway returns failure or webhook signals failure
- **Producer**: `apps/payments/gateways.py`
- **Consumers**: Booking status update, notification service, fraud detection

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Associated booking |
| `amount` | `decimal string` | Amount attempted |
| `gateway` | `string` | Gateway that failed |
| `error_code` | `string` | Gateway error code |
| `error_message` | `string` | Human-readable error message |

---

### `refund.processed`

- **Trigger**: Refund is successfully initiated via gateway API
- **Producer**: `apps/payments/gateways.py` -> `process_refund()`
- **Consumers**: Wallet credit (if original payment was wallet), ledger entry, notification

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `booking_uuid` | `string (UUID)` | Associated booking |
| `amount` | `decimal string` | Refunded amount |
| `gateway` | `string` | Gateway processing refund |
| `refund_id` | `string` | Gateway-issued refund ID |
| `reason` | `string` | Reason code: cancellation, overpayment, dispute, manual |

---

## Inventory Events

### `inventory.hold_created`

- **Trigger**: Guest begins checkout; `InventoryHold` record created with 30-minute TTL
- **Producer**: `apps/inventory/lock_manager.py`
- **Consumers**: Availability cache invalidation, analytics

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `room_type_id` | `integer` | RoomType PK |
| `check_in` | `string (ISO 8601 date)` | First night of hold |
| `check_out` | `string (ISO 8601 date)` | Last night of hold |
| `rooms` | `integer` | Number of rooms held |
| `hold_id` | `string (UUID)` | Hold record identifier |
| `expires_at` | `string (ISO 8601 datetime)` | Hold expiry time (30 min from creation) |

---

### `inventory.released`

- **Trigger**: Hold expires, booking is cancelled, or checkout is abandoned
- **Producer**: `apps/inventory/lock_manager.py`
- **Consumers**: Availability cache invalidation, search re-index trigger

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `room_type_id` | `integer` | RoomType PK |
| `check_in` | `string (ISO 8601 date)` | First night released |
| `check_out` | `string (ISO 8601 date)` | Last night released |
| `rooms` | `integer` | Number of rooms released |
| `reason` | `string` | Release reason: expired, cancelled, abandoned, confirmed |

---

## Search Events

### `search.performed`

- **Trigger**: User submits a search query via any frontend or API client
- **Producer**: `apps/search/views_production.py`
- **Consumers**: Analytics warehouse (`apps/core/analytics_warehouse_api.py`), personalization engine (`apps/search/personalization.py`), learning loop (`apps/search/learning_loop.py`)

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `query` | `string` | Raw search query string |
| `city` | `string` | Resolved city slug |
| `check_in` | `string (ISO 8601 date)` | Requested check-in |
| `check_out` | `string (ISO 8601 date)` | Requested check-out |
| `guests` | `integer` | Number of guests |
| `result_count` | `integer` | Number of results returned |
| `latency_ms` | `integer` | Query latency in milliseconds |
| `cache_hit` | `boolean` | Whether result was served from Redis cache |

---

## Review Events

### `review.submitted`

- **Trigger**: Guest submits a review after checkout; review enters moderation queue
- **Producer**: `apps/hotels/api/v1/review_views.py`
- **Consumers**: Moderation service (`apps/hotels/moderation_service.py`), notification to property owner

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | `integer` | Review PK |
| `property_id` | `integer` | Property being reviewed |
| `rating` | `integer (1-5)` | Star rating |
| `reviewer_id` | `integer` | User PK of reviewer |

---

### `review.approved`

- **Trigger**: Admin or auto-moderation approves a review
- **Producer**: `apps/hotels/moderation_service.py`
- **Consumers**: Search index update (re-compute property rating), analytics, push notification to reviewer

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | `integer` | Review PK |
| `property_id` | `integer` | Property PK |
| `rating` | `integer (1-5)` | Star rating |
| `reviewer_id` | `integer` | User PK of reviewer |

---

## Price Events

### `price.changed`

- **Trigger**: Owner updates base price, seasonal pricing rule activates, or admin overrides price
- **Producer**: `apps/pricing/pricing_service.py`
- **Consumers**: Search index update, cache invalidation, competitor intelligence audit log

**Payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `property_id` | `integer` | Property PK |
| `room_type_id` | `integer` | RoomType PK (nullable for property-level changes) |
| `old_price` | `decimal string` | Previous base price |
| `new_price` | `decimal string` | New base price |
| `reason` | `string` | Change reason: manual, seasonal_rule, weekend_rule, event_rule, admin_override |

---

## Schema Version Policy

| Change Type | Action | Backward Compatible |
|-------------|--------|-------------------|
| Add optional field to payload | No version bump | Yes |
| Rename or remove field | Bump `schema_version` | No - consumers must handle both versions during migration window |
| Change field type | Bump `schema_version` | No |
| Add new event type | No version bump | Yes |

**Migration window**: During a schema version bump, both versions are emitted in parallel for a minimum of **14 days**. Consumers must register handlers for both `schema_version: 1` and `schema_version: 2` before the old version is retired.

**Consumer resilience**: All consumers must implement a dead-letter queue (DLQ) path. Events that cannot be processed after 3 retries are moved to `zygotrip.dlq.{original_event_type}` for manual inspection.
