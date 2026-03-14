# ZygoTrip OTA Capability Audit — March 2026

## Summary

ZygoTrip already contains substantial OTA foundations across hotels, booking, pricing, payments, search, fraud, supplier sync, analytics, dashboards, and eventing. The platform is not starting from zero; it is in a transitional state between a strong modular monolith and a cleanly extracted microservice platform.

Current assessed readiness against the requested Goibibo-comparable target is approximately 72-78% implemented in code, with the strongest areas being booking lifecycle, pricing logic, payment gateways, fraud controls, dynamic search signals, and owner analytics primitives.

The largest remaining gaps are architectural consistency and exposure:

- some production systems exist but are not surfaced through stable APIs
- service boundaries are defined but not yet extracted or uniformly enforced
- event vocabulary is inconsistent between business-facing and internal topics
- owner intelligence is fragmented across multiple endpoints
- Elasticsearch support exists but is not the default orchestrator path

## Audit Matrix

| System | Status | Notes |
| --- | --- | --- |
| API Gateway | Present | Gateway middleware, routing registry, throttles, tracing headers, health endpoints exist. |
| Search Engine | Partial | Geo search, ranking, filters, denormalized search index, caching, and Elasticsearch module exist; orchestration still mixed. |
| Pricing Engine | Present | Unified pricing service with seasonal, weekend, event, LOS, occupancy, tax, wallet, loyalty, and commission logic exists. |
| Calendar Pricing API | Present | Global and property-scoped date-wise pricing APIs already exist. |
| Rate Plan System | Present | Refundable, non-refundable, breakfast, board plans, cancellation tiers implemented. |
| Inventory System | Present | Atomic date-wise inventory, holds, locking, restrictions, and sync flows implemented. |
| Booking Orchestrator | Present | Hold, payment pending, confirm, cancel, refund, retry, and release flows implemented. |
| Payment Service | Present | Wallet, Cashfree, Stripe, Paytm UPI, webhooks, reconciliation, throttling implemented. |
| Commission and Accounting | Partial | Booking commission fields, wallet ledger, revenue splits exist; settlement domain is present but not fully unified. |
| Invoice System | Partial | Booking invoice APIs exist, but full GST-compliant supplier/customer invoice standardization should be hardened. |
| Settlement Engine | Partial | Settlement services and tasks exist; payout automation and finance control plane need stronger API/reporting exposure. |
| Promotion Engine | Present | Coupons, offers, promos, property offers, and promotion application APIs exist. |
| Revenue Intelligence | Partial | Competitor rates, forecasts, and owner revenue APIs exist; command-center consolidation was missing. |
| Owner Dashboard | Partial | Operational dashboards exist; market, conversion, demand, quality, and commission levers were fragmented. |
| Notification System | Present | Email, push, WhatsApp, notifications API, confirmation flows exist. |
| Supplier Sync | Present | Supplier sync trigger, webhook, arbitration, normalization, and health models exist. |
| Event Streaming | Partial | Event bus, Redis stream variant, and remote backend support exist; canonical OTA event contract needed tightening. |
| Analytics Pipeline | Partial | Event log, daily metrics, hotel performance, funnel analytics exist; warehouse extraction is still architectural. |
| Fraud Detection | Present | Fraud scoring, rules, alerts, velocity, device fingerprint, promo abuse detection exist. |
| Observability | Present | Prometheus endpoints, health checks, monitoring APIs, metrics instrumentation exist. |
| Caching Layer | Present | Redis-backed caching for search, availability, pricing, and fallback cache services exist. |
| Demand Forecast Engine | Present | Demand forecast models and forecaster exist. |
| Conversion Optimization | Present | Search ranking v2, conversion signals, analytics funnel, experimentation infrastructure exist. |
| Supply Quality Scoring | Partial | Quality scoring and reliability/cancellation signals exist; owner-facing quality summary needed exposure. |
| Dynamic Commission Engine | Partial | Commission fields and rules exist; recommendation/control loop needed stronger owner-facing intelligence. |
| Loyalty and Rewards | Present | Loyalty redemption, wallet support, referral and rewards infrastructure exist. |
| Cancellation Prediction | Partial | Cancellation rates exist; explicit cancellation-risk summary was missing from owner-facing insights. |
| A/B Testing Platform | Present | Experiment assignment and result APIs exist. |
| Incident Recovery | Partial | Supplier failover, payment recovery, circuit breaking exist; recovery runbooks and cross-service fallback policy should be formalized. |
| Geo Personalization | Present | User context, geo search, map search, distance-aware ranking exist. |
| Supplier Performance Scoring | Partial | Supplier health and sync accuracy models exist; scoring is not consistently exposed. |
| Booking Risk Engine | Present | Fraud engine and booking/device risk checks exist. |

## Upgrade Focus Implemented In This Iteration

1. Added a canonical OTA event layer so business events can be streamed with stable public names while preserving internal dotted topics.
2. Added an owner command-center API that consolidates booking trends, conversion, market comparison, demand forecast, supply quality, cancellation risk, and commission guidance.
3. Documented the target microservice blueprint so extraction can proceed service-by-service without redesigning the platform every sprint.

## Remaining Priority Work

1. Make Elasticsearch or OpenSearch the default search provider path behind a provider abstraction, with PostgreSQL search index as fallback.
2. Standardize invoice, settlement, and accounting APIs around a finance service boundary.
3. Move command, event, and read-model workloads into dedicated service ownership domains: search, pricing, booking, payments, supplier-sync, and owner-insights.