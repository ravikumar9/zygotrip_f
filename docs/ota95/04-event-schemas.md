# 4) Event Schemas

## Kafka topic model

- `zygotrip.search.performed`
- `zygotrip.property.viewed`
- `zygotrip.room.selected`
- `zygotrip.booking.created`
- `zygotrip.booking.confirmed`
- `zygotrip.booking.cancelled`
- `zygotrip.payment.failed`
- `zygotrip.inventory.locked`
- `zygotrip.inventory.released`
- `zygotrip.price.updated`
- `zygotrip.review.created`

## Common event envelope

```json
{
  "event_id": "uuid",
  "event_type": "booking.created",
  "event_version": 1,
  "occurred_at": "2026-03-13T10:00:00Z",
  "trace_id": "trace-abc",
  "source": "booking-service",
  "actor": {
    "user_id": 501,
    "session_id": "sess_123",
    "device_fingerprint": "fp_abc"
  },
  "payload": {}
}
```

## Required OTA events

### search.performed

```json
{
  "query": "goa",
  "city_id": 101,
  "check_in": "2026-04-01",
  "check_out": "2026-04-03",
  "rooms": 1,
  "guests": 2,
  "result_count": 124,
  "latency_ms": 42
}
```

### property.viewed

```json
{
  "property_id": 1001,
  "slug": "aurora-bay-hotel",
  "city_id": 101,
  "position": 3,
  "search_trace_id": "trace-abc"
}
```

### room.selected

```json
{
  "property_id": 1001,
  "room_type_id": 8801,
  "rate_plan_id": "R+B-FLEX",
  "check_in": "2026-04-01",
  "check_out": "2026-04-03",
  "quoted_total": 6195.0
}
```

### booking.created

```json
{
  "booking_id": "bk_101",
  "booking_uuid": "uuid",
  "property_id": 1001,
  "user_id": 501,
  "check_in": "2026-04-01",
  "check_out": "2026-04-03",
  "amount": 6195.0,
  "currency": "INR",
  "status": "payment_pending"
}
```

### booking.confirmed

```json
{
  "booking_id": "bk_101",
  "booking_uuid": "uuid",
  "payment_id": "pay_445",
  "confirmation_code": "ZYGO-AB12",
  "confirmed_at": "2026-03-13T10:01:00Z"
}
```

### booking.cancelled

```json
{
  "booking_id": "bk_101",
  "cancelled_at": "2026-03-30T08:15:00Z",
  "cancel_reason": "user_request",
  "refund_policy_bucket": "24_72_hours"
}
```

### payment.failed

```json
{
  "payment_id": "pay_445",
  "booking_id": "bk_101",
  "gateway": "cashfree",
  "failure_code": "INSUFFICIENT_FUNDS",
  "retryable": true
}
```

### inventory.locked

```json
{
  "lock_id": "lock_789",
  "lock_key": "property:1001:room:dlx:2026-04-01",
  "booking_reference": "ctx_abc123",
  "ttl_seconds": 600
}
```

### inventory.released

```json
{
  "lock_id": "lock_789",
  "lock_key": "property:1001:room:dlx:2026-04-01",
  "release_reason": "payment_failed"
}
```

### price.updated

```json
{
  "property_id": 1001,
  "room_type_id": "dlx",
  "effective_date": "2026-04-01",
  "old_price": 4200,
  "new_price": 4500,
  "driver": "demand_surge"
}
```

### review.created

```json
{
  "review_id": "rev_910",
  "booking_id": "bk_101",
  "property_id": 1001,
  "user_id": 501,
  "rating": 4,
  "spam_score": 0.03
}
```

## Compatibility rules

- Use an outbox table in the monolith for guaranteed publication.
- Keep `event_version` for additive schema evolution.
- Consumers must be forward compatible and ignore unknown fields.
- Partition booking, payment, and inventory topics by booking UUID to preserve ordering for transactional consumers.
