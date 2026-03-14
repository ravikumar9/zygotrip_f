# 0) Architecture Gap Report

## Executive summary

ZygoTrip is not a greenfield OTA. The repository already contains a strong modular-monolith foundation for booking orchestration, pricing, inventory holds, payments, search, fraud checks, supplier integration, analytics, and Kubernetes-oriented deployment assets.

Effective maturity from the audited codebase is approximately 80-84% production readiness, with the remaining gap concentrated in consistency and operations rather than missing domains.

The biggest blockers to a true 95% OTA platform are:

- multiple overlapping runtime paths for checkout and booking, with the newer session-based checkout not fully normalized until this audit pass
- Elasticsearch, Kafka-ready eventing, and service boundaries implemented as optional or secondary paths instead of the default production path
- infrastructure manifests that show the target stack, but mostly in single-cluster or non-hardened form rather than fully HA rollouts
- testing breadth present in repo, but contract, concurrency, and failure-mode automation still incomplete for the critical transactional paths

## Audit matrix

| Subsystem | Current state | Evidence in repo | Gaps | Priority |
| --- | --- | --- | --- | --- |
| Checkout & Booking | Strong but split across legacy and formal session flow | `apps/checkout/models.py`, `apps/checkout/services.py`, `apps/booking/services.py`, `apps/booking/state_machine.py` | Consolidate price-lock checkout as default, remove duplicated booking creation semantics, expand failure recovery automation | P0 |
| Inventory Safety | Strong | `apps/inventory/atomic_ops.py`, `apps/inventory/lock_manager.py`, `apps/inventory/services.py` | Add unified inventory audit trail across legacy `RoomInventory` and `InventoryCalendar`, expose conflict metrics per supplier and room type | P0 |
| Pricing Engine | Strong | `apps/pricing/pricing_service.py`, `apps/pricing/dynamic_engine.py`, `apps/pricing/discount_engine.py` | Make canonical pricing response contract enforced everywhere, standardize drift tolerance across checkout, booking, and payment APIs | P0 |
| Supplier Integration | Moderate to strong | `apps/core/supplier_framework.py`, `apps/core/supplier_adapters.py`, `apps/core/supplier_failover.py` | Normalize cross-vertical adapter contracts, add stronger verify-booking semantics, add supplier SLA scoring and circuit-breaker dashboards | P1 |
| Search Platform | Moderate | `apps/search/engine/search_engine.py`, `apps/search/es_engine.py`, `apps/search/views_production.py`, `apps/core/geo_search.py` | Elasticsearch exists but is not the primary search orchestrator, ranking pipeline still partly DB-bound, no dedicated indexing service boundary | P0 |
| Event Architecture | Moderate | `apps/core/event_bus.py`, `apps/core/event_bus_redis.py`, `apps/core/domain_events.py`, `apps/core/ota_events.py` | Kafka publication is optional, no transactional outbox, consumers still largely in-process callbacks | P0 |
| Analytics Pipeline | Moderate | `apps/core/analytics.py`, `apps/core/analytics_tasks.py`, `apps/core/analytics_warehouse_api.py`, `apps/checkout/analytics_models.py` | Good event capture, but warehouse and replay story still architectural rather than operationalized | P1 |
| Fraud Detection | Strong | `apps/core/fraud_detection.py`, `apps/core/fraud_engine.py`, `apps/core/device_fingerprint.py`, `apps/checkout/services.py` | Policy engine overlaps between multiple fraud modules, critical-block decisions should be centralized and observable | P1 |
| API Platform | Moderate to strong | `apps/core/gateway_middleware.py`, `apps/core/throttles.py`, `apps/core/middleware/*`, DRF endpoints across apps | Stable API governance and service ownership boundaries need tightening, contract tests are not comprehensive yet | P1 |
| Infrastructure & Deployment | Moderate | `docker-compose.yml`, `k8s/`, `deployment/prometheus.yml`, `zygotrip_project/settings.py` | HA topology is documented but not fully encoded for multi-AZ replicas, managed Kafka, managed ES, CDN/WAF, and replica failover | P0 |
| Observability | Moderate to strong | `apps/core/metrics.py`, `apps/core/telemetry.py`, `apps/core/observability.py`, `deployment/prometheus.yml` | Metrics and OTEL tracing exist, but alert rules, runbooks, and golden dashboards need promotion to first-class ops assets | P1 |
| Testing | Moderate | `apps/core/tests*.py`, `test_booking_flow.py`, `test_e2e_payment_gateway.py`, `tests/load/*`, `locustfile.py` | Strong seeds for load and safety testing, but missing reliable automated contract tests and concurrency regression tests around the formal checkout path | P0 |

## Core-system verification

### Checkout session model

Status: implemented with minor integration risk

- Formal session lifecycle exists in `apps/checkout/models.py`
- Session expiration exists via `expires_at` and `apps/checkout/tasks.py`
- Price snapshot and inventory token linking exist
- Payment idempotency exists at intent and transaction layers
- Failure recovery exists, but was weakened by snapshot key mismatches before this audit pass

### Booking state machine

Status: implemented, but not consistently used everywhere

- `apps/booking/state_machine.py` enforces transitions with row locking
- `apps/booking/models.py` defines OTA lifecycle states including failure and settlement paths
- Some runtime code still mutates booking or payment state through legacy paths instead of one uniform orchestration boundary

### Inventory protection

Status: implemented strongly

- Per-date distributed slot locks exist in `apps/inventory/lock_manager.py`
- Hold creation, conversion, and release exist in `apps/inventory/atomic_ops.py`
- Celery expiry path exists in `apps/checkout/tasks.py`
- Main remaining gap is unified auditability across the legacy and new inventory models

### Pricing engine

Status: implemented strongly

- Canonical pricing pipeline exists in `apps/pricing/pricing_service.py`
- Weekend, seasonal, demand, LOS, occupancy, taxes, coupon, loyalty, and wallet adjustments are implemented
- Search and checkout were not uniformly consuming the canonical response shape in all places until this audit pass

## Search assessment

Current state:

- PostgreSQL-backed unified search remains the default online path
- Elasticsearch indexing, query, autocomplete, and reindex tasks are present
- Geo radius and viewport search are implemented
- Ranking engines and personalization layers already exist

Gap to 95%:

- move search API traffic to an ES-first orchestrator with PostgreSQL fallback
- isolate index build/replay into a dedicated indexer pipeline
- publish search performance SLOs against ES rather than mixed DB behavior

## Event-streaming assessment

Current state:

- in-process event bus exists
- Redis Streams variant exists
- Kafka producer path and typed domain-event layer exist

Gap to 95%:

- add transactional outbox for exactly-once publication from booking/payment/inventory writes
- make Kafka the default broker for production event fan-out
- move analytics, notifications, and fraud enrichment to explicit consumers instead of local callback coupling

## Risk assessment

### Critical

- Transactional path drift: the repo contains both legacy and new checkout/payment paths, so correctness bugs can hide in the less-used formal flow.
- Search scale risk: ES support exists, but DB-heavy search remains the default in critical request paths.
- Event durability risk: business events can be published without outbox guarantees.

### High

- Infra mismatch risk: compose and Kubernetes assets show the target architecture, but high availability and managed-service assumptions are not fully enforced.
- Testing confidence gap: load tests exist, but repeatable CI-grade concurrency and contract coverage are not yet broad enough for 10k booking confidence.

### Medium

- Supplier consistency risk: hotels are strongest, but buses, cabs, and flights need stricter cross-vertical adapter contracts.
- Fraud policy sprawl: multiple fraud modules overlap and should be unified behind one risk decision service.

## Prioritized improvement roadmap

### P0: close correctness and reliability gaps

1. Make the session-based checkout flow the canonical pre-payment path and keep legacy booking creation only as a compatibility shim.
2. Standardize pricing snapshots and payment amounts around the canonical pricing engine contract.
3. Promote Elasticsearch to the primary search read path with PostgreSQL fallback only.
4. Introduce outbox-backed Kafka publication for booking, payment, inventory, pricing, and review events.
5. Harden production topology around PostgreSQL replicas, Redis cluster, Kafka cluster, and ES cluster.

### P1: operationalize service boundaries

1. Extract search/indexer, inventory, pricing, booking, and payments behind stable internal APIs.
2. Unify fraud decisions into one risk orchestration service.
3. Add supplier health scoring, fallback routing, and reconciliation dashboards per supplier.
4. Expand observability with real SLO alerts, runbooks, and trace-linked dashboards.

### P2: optimize and globalize

1. Expand recommendation and personalization into dedicated read-model services.
2. Add warehouse-grade analytics replay and multi-region data export paths.
3. Continue frontend/mobile parity work for share flows, booking modification, and post-stay engagement.
