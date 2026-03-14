# ZygoTrip API Contracts

## Authentication

All authenticated endpoints require a JWT Bearer token.

| Parameter | Value |
|-----------|-------|
| Access token TTL | 15 minutes |
| Refresh token TTL | 7 days |
| Header format | `Authorization: Bearer {token}` |
| Token endpoint | `POST /api/v1/auth/token/` |
| Refresh endpoint | `POST /api/v1/auth/token/refresh/` |

**Obtain token**:

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secret"
}
```

---

## Standard Response Envelope

All API responses are wrapped in a standard envelope:

```json
{
  "success": true,
  "data": { },
  "error": null,
  "trace_id": "abc123..."
}
```

On error:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "check_in must be before check_out",
    "field": "check_in"
  },
  "trace_id": "abc123..."
}
```

---

## Error Codes

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | VALIDATION_ERROR | Request body or query params failed validation |
| 401 | AUTHENTICATION_REQUIRED | Missing or expired JWT token |
| 403 | PERMISSION_DENIED | Authenticated user lacks required role/permission |
| 404 | NOT_FOUND | Requested resource does not exist |
| 409 | CONFLICT | State conflict (e.g., booking already confirmed, inventory already held) |
| 410 | INVENTORY_UNAVAILABLE | Requested rooms are no longer available for selected dates |
| 422 | BUSINESS_RULE_VIOLATION | Valid request but violates a business rule (e.g., check-out before check-in) |
| 429 | RATE_LIMITED | Too many requests - see Retry-After header |
| 500 | INTERNAL_ERROR | Unexpected server error - trace_id included for support |
| 502 | GATEWAY_ERROR | Upstream payment gateway or supplier returned an error |
| 503 | SERVICE_UNAVAILABLE | Scheduled maintenance or overload - see Retry-After header |

---

## Core Endpoints

### Search

#### GET /api/v1/hotels/search/

Hotel search with filters. Backed by Elasticsearch (falls back to PostgreSQL FTS).

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `city` | string | Yes | City slug, e.g. `goa` |
| `check_in` | date (YYYY-MM-DD) | Yes | Check-in date |
| `check_out` | date (YYYY-MM-DD) | Yes | Check-out date |
| `guests` | integer | Yes | Number of guests |
| `rooms` | integer | No | Number of rooms (default: 1) |
| `min_price` | decimal | No | Minimum price per night |
| `max_price` | decimal | No | Maximum price per night |
| `category` | string | No | Hotel category slug |
| `amenities` | comma-separated string | No | Filter by amenities, e.g. `wifi,pool` |
| `rating_min` | float (1.0-5.0) | No | Minimum guest rating |
| `sort` | string | No | Sort: `price_asc`, `price_desc`, `rating`, `relevance` (default) |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Results per page, max 50 (default: 20) |

**Response**:

```json
{
  "success": true,
  "data": {
    "count": 142,
    "next": "/api/v1/hotels/search/?page=2&...",
    "results": [
      {
        "slug": "sea-view-resort-goa",
        "name": "Sea View Resort",
        "city": "Goa",
        "star_category": 4,
        "price_from": "4500.00",
        "guest_rating": 4.3,
        "thumbnail": "https://cdn.zygotrip.com/..."
      }
    ]
  }
}
```

---

#### GET /api/v1/search/autocomplete/

City and property name autocomplete for the search bar.

**Query parameters**: `q` (string, min 2 chars), `type` (optional: `city`, `property`, `all`)

#### GET /api/v1/search/geo/

Viewport/map-bounds search. Returns properties within a geographic bounding box.

**Query parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `swlat` | float | Southwest corner latitude |
| `swlng` | float | Southwest corner longitude |
| `nelat` | float | Northeast corner latitude |
| `nelng` | float | Northeast corner longitude |
| `check_in` | date | Check-in date |
| `check_out` | date | Check-out date |
| `guests` | integer | Number of guests |

---

### Hotel Detail

#### GET /api/v1/hotels/{slug}/

Full property detail including amenities, images, policies, and reviews summary.

**Path parameter**: `slug` - property slug, e.g. `sea-view-resort-goa`

**Response includes**: name, description, star_category, amenities, images, cancellation_policy, house_rules, review_summary, coordinates

#### GET /api/v1/hotels/{slug}/rooms/

Room availability and pricing for a property. Requires `check_in`, `check_out`, `guests` query params.

**Response includes**: room_type_id, name, max_occupancy, available_count, meal_plans, price_per_night, total_price, cancellation_policy

#### GET /api/v1/properties/price-calendar/

30-60 day price calendar for a property/room type. Holiday-aware - marks dates with demand multipliers.

**Query parameters**: `property_id`, `room_type_id` (optional), `month` (YYYY-MM), `guests`

**Response**: Array of date objects with `date`, `price`, `available`, `is_holiday`, `holiday_name`, `season_tag`

---

### Booking Flow

The booking flow is a 3-step stateful checkout session:

    Step 1: POST /api/v1/checkout/start/         - Create session + hold inventory
    Step 2: PATCH /api/v1/checkout/{uuid}/details/ - Add guest details
    Step 3: POST /api/v1/checkout/{uuid}/payment-intent/ - Create payment intent
    Step 4: (client) Redirect to gateway or confirm wallet payment
    Step 5: POST /api/v1/payments/verify/        - Confirm payment + finalize booking

#### POST /api/v1/checkout/start/

Creates a checkout session and places an inventory hold (30-minute TTL).

**Request body**:

```json
{
  "property_id": 42,
  "room_type_id": 15,
  "rate_plan_id": 3,
  "check_in": "2026-04-01",
  "check_out": "2026-04-03",
  "rooms": 1,
  "guests": 2
}
```

**Response**: `checkout_uuid`, `hold_expires_at`, `price_summary`

#### PATCH /api/v1/checkout/{uuid}/details/

Add or update guest details for the checkout session.

**Request body**:

```json
{
  "guest_name": "Rahul Sharma",
  "guest_email": "rahul@example.com",
  "guest_phone": "+919876543210",
  "special_requests": "High floor preferred",
  "coupon_code": "SUMMER20"
}
```

#### POST /api/v1/checkout/{uuid}/payment-intent/

Creates a payment intent. Returns gateway-specific data needed to redirect the user or render the payment UI.

**Request body**: `gateway` (one of: `wallet`, `cashfree`, `stripe`, `paytm_upi`)

**Response includes**: `payment_session_id` (Cashfree), `client_secret` (Stripe), `txn_token` (Paytm), or direct confirmation for wallet

#### GET /api/v1/booking/{uuid}/invoice/

Retrieve the invoice for a confirmed booking. Returns 404 if invoice has not been generated yet.

#### POST /api/v1/booking/{uuid}/invoice/

Generate and return the invoice. Booking must be in status: `confirmed`, `checked_in`, `checked_out`, `settled`, or `settlement_pending`.

**Invoice number format**: `ZT-YYYYMMDD-NNNNNN` (sequential per day)

---

### Payments

#### POST /api/v1/payments/initiate/

Initiate a payment for a booking. Idempotent - re-submitting the same `idempotency_key` returns the existing transaction.

**Request body**:

```json
{
  "booking_uuid": "a1b2c3d4-...",
  "gateway": "cashfree",
  "amount": "8500.00",
  "currency": "INR",
  "idempotency_key": "client-generated-uuid"
}
```

#### POST /api/v1/payments/verify/

Verify payment after gateway callback. Triggers booking confirmation on success.

**Request body**: `booking_uuid`, `transaction_id`, `gateway`, gateway-specific callback params

**Note**: This endpoint is also called as a webhook by gateways. HMAC signature verification is enforced.

#### POST /api/v1/payments/refund/

Request a refund for a cancelled or partially cancelled booking.

**Request body**:

```json
{
  "booking_uuid": "a1b2c3d4-...",
  "amount": "4250.00",
  "reason": "cancellation"
}
```

**Authorization**: Requires staff or admin role, or booking owner.

---

### Wallet

#### GET /api/v1/wallet/

Returns the authenticated user wallet balance and summary.

**Response**:

```json
{
  "success": true,
  "data": {
    "balance": "1250.00",
    "currency": "INR",
    "cashback_balance": "200.00",
    "last_updated": "2026-03-14T09:00:00Z"
  }
}
```

#### POST /api/v1/wallet/add/

Add funds to wallet (triggers a payment intent for top-up).

**Request body**: `amount` (decimal, min 100 INR), `gateway` (cashfree, stripe, paytm_upi)

#### GET /api/v1/wallet/transactions/

Paginated transaction history for the authenticated user wallet.

**Response includes**: `txn_type` (credit/debit), `amount`, `description`, `balance_after`, `created_at`

---
### Owner Dashboard APIs

All owner dashboard endpoints require authentication with `role=property_owner`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dashboard/owner/revenue-intelligence/` | Revenue KPIs: RevPAR, ADR, occupancy rate |
| GET | `/api/v1/dashboard/owner/market-comparison/` | Compare own pricing vs competitor market rates |
| GET | `/api/v1/dashboard/owner/demand-forecast/` | 30-day demand forecast with holiday intelligence |
| GET | `/api/v1/rate-plans/` | List rate plans for a property |
| POST | `/api/v1/rate-plans/` | Create a new rate plan |
| PATCH | `/api/v1/rate-plans/{id}/` | Update a rate plan |

---

### Admin Monitoring APIs

All admin endpoints require `role=admin` or `role=staff`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/monitoring/health/` | System health: DB, Redis, Celery, ES, payment gateways |
| GET | `/api/v1/admin/monitoring/alerts/` | Active alerts and threshold breaches |
| GET | `/api/v1/admin/ops/bookings/` | Admin booking overview with filters |
| POST | `/api/v1/admin/ops/refund/` | Manual refund override |

---

### Supplier Sync APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/supplier/webhook/{provider}/` | Receive inventory/pricing webhook from supplier |
| POST | `/api/v1/supplier/sync/{property_uuid}/` | Manually trigger a supplier sync for a property |
| GET | `/api/v1/supplier/sync-status/` | Current sync status and health for all suppliers |

Supported providers: `hotelbeds`, `staah`, `channex`, `siteminder`

---

## Rate Limits

Rate limits are enforced per IP address. Authenticated requests get 2x the listed limit.

| Endpoint Pattern | Limit | Window |
|-----------------|-------|--------|
| `/api/v1/auth/` | 10 requests | per minute |
| `/api/v1/hotels/search/` | 60 requests | per minute |
| `/api/v1/search/autocomplete/` | 120 requests | per minute |
| `/api/v1/hotels/{slug}/` | 120 requests | per minute |
| `/api/v1/checkout/` | 30 requests | per minute |
| `/api/v1/payments/` | 20 requests | per minute |
| `/api/v1/wallet/` | 60 requests | per minute |
| `/api/v1/dashboard/` | 120 requests | per minute |
| `/api/v1/supplier/` | 30 requests | per minute |
| All other endpoints | 200 requests | per minute |

When rate limited, the response will include:
- HTTP status: 429
- Header: `Retry-After: {seconds}`
- Header: `X-RateLimit-Limit: {limit}`
- Header: `X-RateLimit-Remaining: 0`
- Header: `X-RateLimit-Reset: {unix_timestamp}`

---

## Versioning

- Current API version: `v1`
- All endpoints are prefixed with `/api/v1/`
- Breaking changes will be introduced under `/api/v2/` with a minimum 6-month deprecation notice on v1
- Non-breaking changes (new optional fields, new endpoints) are added in-place without a version bump
- Deprecated fields are marked in responses with a `X-Deprecated-Fields` header listing field names
