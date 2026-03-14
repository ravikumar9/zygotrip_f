# 5) Database Schemas

## Data ownership model

- PostgreSQL remains source of truth.
- Elasticsearch remains query index for search only.
- Redis stores locks, caches, and short-lived sessions.
- Kafka stores event stream and replay capability.

## Existing monolith compatibility

Keep existing core tables as canonical during migration:
- hotels_property
- rooms_roomtype
- rooms_roominventory
- booking_booking
- payments_paymenttransaction
- wallet_wallet
- search_propertysearchindex

## New shared platform tables (in PostgreSQL)

### event_outbox

```sql
CREATE TABLE event_outbox (
  id BIGSERIAL PRIMARY KEY,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(128) NOT NULL,
  event_version INT NOT NULL DEFAULT 1,
  payload JSONB NOT NULL,
  trace_id VARCHAR(128),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at TIMESTAMPTZ
);
CREATE INDEX idx_outbox_unpublished ON event_outbox (published_at) WHERE published_at IS NULL;
```

### idempotency_keys

```sql
CREATE TABLE idempotency_keys (
  id BIGSERIAL PRIMARY KEY,
  idempotency_key VARCHAR(128) NOT NULL,
  service_name VARCHAR(64) NOT NULL,
  request_hash VARCHAR(128) NOT NULL,
  response_body JSONB,
  status_code INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (service_name, idempotency_key)
);
```

### booking_locks_audit

```sql
CREATE TABLE booking_locks_audit (
  id BIGSERIAL PRIMARY KEY,
  lock_id VARCHAR(64) NOT NULL,
  lock_key VARCHAR(256) NOT NULL,
  booking_reference VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### refund_policy_versions

```sql
CREATE TABLE refund_policy_versions (
  id BIGSERIAL PRIMARY KEY,
  product_type VARCHAR(32) NOT NULL,
  rules JSONB NOT NULL,
  active BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Search index schema (Elasticsearch)

Index: properties_v3
- property_id (keyword)
- city_id (keyword)
- geo (geo_point)
- price_min (scaled_float)
- price_max (scaled_float)
- rating (float)
- review_count (integer)
- amenities (keyword)
- available_rooms (integer)
- recent_bookings (integer)
- ranking_features (rank_features)

## Read/write split

- Writes: PostgreSQL primary only
- Reads: PostgreSQL replicas for non-transactional queries
- Search reads: Elasticsearch
- Lock reads/writes: Redis

## Backward compatibility constraints

- No renames or drops of monolith tables in migration phases 1-4.
- New services use views/materialized views where possible.
- Any schema change requires dual-read validation before cutover.
