# 3) API Contracts

## Contract style

- External APIs: REST JSON via API gateway
- Internal sync calls: REST/gRPC depending on latency sensitivity
- Internal async: Kafka events with schema versioning
- All write APIs require Idempotency-Key header

## Search API

### GET /v1/search/hotels

Request query:
- city_id
- check_in
- check_out
- guests
- rooms
- filters
- page
- page_size

Response:
```json
{
  "request_id": "req_123",
  "results": [
    {
      "property_id": 1001,
      "name": "Signal Suites",
      "price": 4200,
      "currency": "INR",
      "rating": 4.3,
      "distance_km": 1.4,
      "rooms_left": 3,
      "score": 0.912
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1532
  },
  "latency_ms": 37
}
```

## Inventory lock API

### POST /v1/inventory/locks

Request:
```json
{
  "lock_key": "property:1001:room:dlx:2026-04-01",
  "booking_reference": "ctx_abc123",
  "ttl_seconds": 600,
  "quantity": 1
}
```

Response:
```json
{
  "lock_id": "lock_789",
  "status": "locked",
  "expires_at": "2026-04-01T10:10:00Z"
}
```

### DELETE /v1/inventory/locks/{lock_id}

Response:
```json
{
  "status": "released"
}
```

## Booking API

### POST /v1/bookings

Request:
```json
{
  "search_context_id": "ctx_abc123",
  "lock_id": "lock_789",
  "traveler": {
    "name": "Ravi",
    "phone": "+919999999999"
  },
  "payment_mode": "gateway"
}
```

Response:
```json
{
  "booking_id": "bk_101",
  "status": "payment_pending",
  "amount_payable": 5120,
  "currency": "INR"
}
```

### POST /v1/bookings/{booking_id}/modify

Request:
```json
{
  "new_check_in": "2026-04-03",
  "new_check_out": "2026-04-05",
  "new_room_type_id": "dlx",
  "reason": "date_change"
}
```

Response:
```json
{
  "booking_id": "bk_101",
  "status": "modified",
  "repriced_total": 6120,
  "delta_amount": 1000,
  "invoice_id": "inv_3001"
}
```

## Payment API

### POST /v1/payments/initiate

Request:
```json
{
  "booking_id": "bk_101",
  "gateway": "cashfree",
  "amount": 5120,
  "currency": "INR"
}
```

Response:
```json
{
  "payment_id": "pay_445",
  "status": "initiated",
  "redirect_url": "https://gateway.example/session/xyz"
}
```

### POST /v1/payments/webhook/{gateway}

- Must verify provider signature
- Must be idempotent using gateway_transaction_id

## Refund API

### POST /v1/refunds/compute

Request:
```json
{
  "booking_id": "bk_101",
  "cancelled_at": "2026-03-28T09:00:00Z"
}
```

Response:
```json
{
  "booking_id": "bk_101",
  "refund_percentage": 50,
  "refund_amount": 2560,
  "policy_bucket": "24_72_hours"
}
```

## Compatibility envelope

Gateway responses preserve current monolith envelope where needed:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```
