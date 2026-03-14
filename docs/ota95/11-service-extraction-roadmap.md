# 11) Service Extraction Roadmap

## Goal

Extract services in the order that reduces operational risk while preserving the existing Django codebase as the source of truth during migration.

## Principles

- PostgreSQL remains authoritative until dual-read validation is complete.
- Every extraction starts behind an internal adapter and strangler route.
- Events are emitted through an outbox before downstream consumers are made authoritative.
- Shared entities keep stable IDs and public contracts through the migration.

## Phase 0: Monolith hardening

Scope:

- stabilize canonical checkout, pricing, booking, and payment contracts
- add outbox table and trace propagation
- publish core OTA event schemas

Current code anchors:

- `apps/checkout/*`
- `apps/booking/*`
- `apps/pricing/*`
- `apps/payments/*`
- `apps/core/domain_events.py`

Exit criteria:

- one authoritative checkout path
- canonical event envelope live
- idempotency and retry semantics documented and tested

## Phase 1: Search and indexer extraction

Why first:

- read-heavy domain with the lowest transactional coupling
- biggest latency upside for the 5M daily search target

Scope:

- extract `search-service`
- extract `search-indexer`
- make Elasticsearch the default query engine

Current code anchors:

- `apps/search/es_engine.py`
- `apps/search/engine/search_engine.py`
- `apps/search/tasks.py`
- `apps/core/geo_search.py`

Compatibility plan:

- dual-read shadow queries on PostgreSQL and Elasticsearch
- compare ranking and result coverage before cutover

## Phase 2: Inventory and availability extraction

Why second:

- inventory safety is the core transactional dependency for booking confidence

Scope:

- isolate hold creation, hold conversion, hold release, and supplier sync
- unify legacy `RoomInventory` and `InventoryCalendar` ownership behind one API

Current code anchors:

- `apps/inventory/atomic_ops.py`
- `apps/inventory/lock_manager.py`
- `apps/inventory/services.py`

Compatibility plan:

- monolith delegates writes to extracted inventory service through internal client
- shared DB first, isolated DB only after consistency validation

## Phase 3: Pricing extraction

Why third:

- pricing is already highly encapsulated and has clear read/write edges

Scope:

- extract canonical pricing engine
- expose price quote, revalidation, calendar pricing, and rule management APIs

Current code anchors:

- `apps/pricing/pricing_service.py`
- `apps/pricing/dynamic_engine.py`
- `apps/pricing/calendar_api.py`

Compatibility plan:

- preserve the existing pricing response contract
- keep cache keys and promo/loyalty integrations stable

## Phase 4: Booking and checkout extraction

Why fourth:

- depends on search, inventory, and pricing already being stable service boundaries

Scope:

- extract checkout session orchestration
- extract booking state machine and modification flows
- move saga and recovery logic into dedicated workers

Current code anchors:

- `apps/checkout/services.py`
- `apps/booking/state_machine.py`
- `apps/booking/orchestrator.py`
- `apps/booking/saga.py`

Compatibility plan:

- keep booking UUIDs and public booking IDs unchanged
- maintain read access through monolith APIs until consumers are migrated

## Phase 5: Payments and fraud extraction

Why fifth:

- payment orchestration becomes safer once booking and checkout flows are isolated

Scope:

- extract payment initiation, webhook reconciliation, refunds, and gateway routing
- centralize fraud decisioning around payment and booking risk

Current code anchors:

- `apps/payments/api/v1/views.py`
- `apps/payments/gateways.py`
- `apps/core/fraud_detection.py`
- `apps/core/fraud_engine.py`

Compatibility plan:

- keep `PaymentTransaction` as source-of-truth schema during migration
- use idempotency keys and webhook replay protection as non-negotiables

## Phase 6: Supplier, analytics, and notifications extraction

Scope:

- supplier services by vertical
- analytics/event-consumer services
- email, SMS, WhatsApp, and push notification services

Current code anchors:

- `apps/core/supplier_framework.py`
- `apps/core/supplier_adapters.py`
- `apps/core/analytics.py`
- `apps/core/email_service.py`
- `apps/core/whatsapp_notifications.py`

Compatibility plan:

- consume canonical OTA events from Kafka
- keep analytics warehouse and notification fan-out eventually consistent

## Recommended cutover order

1. Search/indexer
2. Inventory
3. Pricing
4. Checkout/booking
5. Payments/fraud
6. Supplier services
7. Analytics and notifications

## Success metrics per phase

- Search: p95 search latency under 50 ms for cached and ES-backed city queries
- Inventory: zero oversell during concurrency tests
- Pricing: 100% parity on quoted vs charged totals within approved drift rules
- Booking: state transition errors under 0.1% of booking attempts
- Payments: booking success rate above 99% and payment failure rate under 5%
- Eventing: no unrecoverable message loss and full replay from outbox to Kafka consumers
