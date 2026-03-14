# ZygoTrip Production Microservices Blueprint

## Target Service Topology

ZygoTrip should evolve from the current modular monolith into a service-oriented platform with explicit ownership boundaries and shared platform capabilities.

### Edge and Control Plane

- API Gateway
  - authentication, JWT validation, API version routing, rate limits, request tracing, canary routing
- Web BFF / Mobile BFF
  - channel-specific aggregation for frontend clients

### Core Commerce Services

- Search Service
  - Elasticsearch or OpenSearch index, geo search, faceting, personalization, ranking experiments
- Pricing Service
  - canonical pricing pipeline, calendar pricing, taxes, promotions, loyalty, dynamic commission levers
- Inventory Service
  - atomic holds, availability, supplier inventory normalization, Redis-assisted locking, source-of-truth calendars
- Booking Orchestrator
  - saga workflow: inventory check, hold, price lock, coupon, payment, confirm, compensate
- Payment Service
  - gateway adapters, webhooks, retries, reconciliation, refunds, payment risk gates
- Promotion Service
  - coupons, bank offers, seasonal deals, campaign targeting, eligibility rules
- Finance Service
  - invoices, commission accounting, settlement, payout adjustments, GST reporting

### Intelligence and Optimization Services

- Revenue Intelligence Service
  - competitor prices, price recommendations, dynamic commission recommendations, owner alerts
- Demand Forecast Service
  - demand score, occupancy forecasts, seasonal signals, event uplift models
- Supply Quality Service
  - cancellation risk, review quality, complaint rate, inventory reliability, supplier scorecards
- Fraud and Risk Service
  - booking fraud, coupon abuse, payment anomalies, device fingerprinting, rules engine
- Experimentation Service
  - A/B assignment, exposure logging, outcome attribution, ranking/pricing experiments

### Channel and Ops Services

- Notification Service
  - email, SMS, WhatsApp, push notifications, delivery status, retries
- Supplier Sync Service
  - supplier webhooks, periodic pulls, conflict arbitration, ingestion normalization
- Owner Insights Service
  - read-optimized analytics API for hotel owners, bus operators, cab fleets, package providers

## Event Backbone

Use Kafka in production, with RabbitMQ acceptable for lower-throughput transactional orchestration.

### Core Topics

- booking.created
- booking.cancelled
- inventory.updated
- pricing.updated
- payment.initiated
- payment.succeeded
- payment.failed
- promotion.applied
- supplier.sync.completed
- fraud.assessed
- demand.forecast.updated
- owner.alert.created

### Event Contract Principles

- every event must include event_id, occurred_at, source_service, aggregate_id, aggregate_type
- business-facing canonical names should remain stable even if internal handlers evolve
- events must be idempotent for downstream consumers
- replayable topics should avoid destructive semantics in consumers

## Data Ownership

- Search owns search documents and query ranking read models
- Pricing owns price breakdowns and tax logic
- Inventory owns availability and holds
- Booking owns lifecycle state machine and saga state
- Payments owns transaction attempts and gateway reconciliation
- Finance owns invoices, commissions, settlement batches, payout journals
- Intelligence services own derived scores and forecasts, not transactional source data

## Storage Model

- PostgreSQL for transactional consistency
- Redis for caching, request dedupe, short-lived locks, search result cache, calendar cache
- Elasticsearch/OpenSearch for hotel and multi-vertical discovery indexes
- Kafka for stream transport
- ClickHouse, BigQuery, or Redshift for analytics warehouse
- Prometheus and Grafana for observability

## Booking Flow

1. Client hits API Gateway.
2. Booking Orchestrator requests availability from Inventory Service.
3. Inventory Service acquires atomic hold and emits inventory.updated.
4. Pricing Service returns canonical quote with promotion and tax breakdown.
5. Promotion Service validates coupons and bank offers.
6. Payment Service initiates payment and emits payment.initiated.
7. On success, Booking Orchestrator confirms booking and emits booking.created.
8. Finance Service records commission, tax, payout liability, and invoice generation.
9. Notification Service sends customer and owner confirmations.
10. Analytics warehouse ingests events asynchronously.

## Search Flow

1. Search Service receives query, geo, date, occupancy, and filters.
2. Elasticsearch executes geo + facet + availability-aware retrieval.
3. Ranking layer applies price competitiveness, rating, conversion, commission, promotion, cancellation risk, and personalization.
4. Results are cached in Redis using demand-aware TTLs.
5. Search impression and clickstream events are emitted for optimization loops.

## Reliability and Recovery

- gateway-level circuit breaker for degraded dependencies
- booking saga compensation for payment or supplier failures
- fallback from Elasticsearch to denormalized PostgreSQL search index
- retryable payment verification and webhook reconciliation
- supplier failover and stale-data protection for inventory/search outages
- runbook-driven incident classes for search, payment, supplier, and settlement failures

## Extraction Sequence

1. Search Service
2. Pricing Service
3. Inventory Service
4. Booking Orchestrator
5. Payment Service
6. Finance Service
7. Owner Insights Service
8. Supplier Sync Service
9. Intelligence services

This sequence minimizes blast radius because it extracts the most read-heavy and independently testable domains first, while keeping the booking transaction boundary coherent until inventory, pricing, and payments are mature.