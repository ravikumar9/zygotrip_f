# 10) Migration Plan from Monolith to Distributed OTA

## Guiding principle

Strangler Fig migration with strict backward compatibility:
- Keep current Django monolith logic operational.
- Move one bounded context at a time behind API gateway routes.
- Use outbox + Kafka for event consistency.

## Phase plan

### Phase 0: Foundation (Weeks 1-2)

- Stand up API gateway, Kafka, Elasticsearch, Redis cluster, OpenTelemetry.
- Add event_outbox and idempotency_keys tables in current PostgreSQL.
- Add distributed lock abstraction without changing booking API behavior.

Exit criteria:
- No functional regression in current booking and payment flows.

### Phase 1: Search extraction (Weeks 3-5)

- Deploy search-service and search-indexer.
- Build PostgreSQL -> outbox -> Kafka -> indexer -> Elasticsearch pipeline.
- Route read-only hotel search endpoints through gateway to search-service.

Exit criteria:
- Search parity > 99% vs monolith for top routes.
- Search p95 <= 120ms at staging load.

### Phase 2: Inventory lock service (Weeks 6-7)

- Introduce room-inventory-service lock APIs backed by Redis lock cluster.
- Monolith booking API calls lock service via adapter.

Exit criteria:
- Lock conflict handling verified under concurrent booking tests.

### Phase 3: Booking and payment decomposition (Weeks 8-10)

- Extract booking-service write APIs and payment-gateway-service.
- Keep existing state machine and refund logic rules intact.
- Dual-write audit logs and validate event completeness.

Exit criteria:
- Booking success rate >= baseline.
- Payment failure not increased above 5% threshold.

### Phase 4: Pricing and coupons decomposition (Weeks 11-12)

- Extract pricing-engine and coupon-service using existing formulas:

final_price = base_price + weekend_multiplier + seasonal_multiplier + demand_surge - coupon_discount

- Keep monolith as fallback evaluator via feature flag.

Exit criteria:
- Price parity >= 99.5% on replay set.

### Phase 5: Modifications, cancellations, refunds (Weeks 13-14)

Implement modify_booking flow:
1. retrieve booking
2. check new availability
3. reprice booking
4. adjust payment
5. update invoice

Implement policy refund rules:
- >72h: 100%
- 24-72h: 50%
- <24h: 0%

Exit criteria:
- Refund accuracy 100% on policy regression suite.

### Phase 6: Full cutover and optimization (Weeks 15-16)

- Route all critical endpoints through gateway to new services.
- Keep monolith in shadow mode for 2 release cycles.
- Decommission only after replay and audit sign-off.

## Testing plan by phase

- Unit tests for each service
- Integration tests for lock-payment-booking lifecycle
- Contract tests for supplier adapters
- Load tests for 10k concurrent booking attempts
- Chaos tests for gateway, Kafka, Redis, and payment provider failures

## Rollback strategy

- Route-level rollback at API gateway
- Feature flags for service fallback to monolith
- Event replay from Kafka for recovery and reconciliation

## Final readiness scorecard

- Search latency < 50ms warm path
- Booking success rate > 99%
- Refund accuracy 100%
- Uptime 99.9%
- Daily search throughput 5M+
