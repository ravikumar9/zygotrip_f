# 1) Service Architecture Diagram

## Domain services

- Identity: auth-service, user-profile-service, session-service, otp-verification-service, loyalty-service
- Search: search-service, search-indexer, autocomplete-service, recommendation-service, ranking-engine
- Inventory: property-inventory-service, room-inventory-service, seat-inventory-service, cab-fleet-service, availability-sync-service
- Booking: booking-service, booking-modification-service, cancellation-service, refund-service, invoice-service
- Pricing: pricing-engine, dynamic-pricing-service, surge-pricing-service, discount-engine, coupon-service
- Payment: payment-gateway-service, wallet-service, refund-processor, fraud-detection-service
- Supplier: hotel-supplier-service, flight-supplier-service, bus-supplier-service, cab-partner-service
- Content: review-service, rating-aggregator, moderation-service
- Notification: email-service, sms-service, push-notification-service
- Analytics: event-tracking-service, analytics-pipeline, reporting-service
- Infrastructure: api-gateway, service-discovery, monitoring-stack

## Logical architecture

```mermaid
flowchart LR
  C[Web and Mobile Clients] --> G[API Gateway]

  subgraph ID[Identity Domain]
    AU[auth-service]
    UP[user-profile-service]
    SS[session-service]
    OTP[otp-verification-service]
    LOY[loyalty-service]
  end

  subgraph SE[Search Domain]
    SRCH[search-service]
    AUTO[autocomplete-service]
    REC[recommendation-service]
    RANK[ranking-engine]
    IDX[search-indexer]
    ES[(Elasticsearch Cluster)]
  end

  subgraph INV[Inventory Domain]
    PI[property-inventory-service]
    RI[room-inventory-service]
    SI[seat-inventory-service]
    CF[cab-fleet-service]
    AS[availability-sync-service]
    RLOCK[(Redis Lock Cluster)]
  end

  subgraph BK[Booking Domain]
    BS[booking-service]
    BM[booking-modification-service]
    CS[cancellation-service]
    RF[cancellation refund-service]
    INVCS[invoice-service]
  end

  subgraph PR[Pricing Domain]
    PE[pricing-engine]
    DP[dynamic-pricing-service]
    SP[surge-pricing-service]
    DE[discount-engine]
    CO[coupon-service]
  end

  subgraph PM[Payment Domain]
    PG[payment-gateway-service]
    WA[wallet-service]
    RP[refund-processor]
    FR[fraud-detection-service]
  end

  subgraph SUP[Supplier Integration]
    HS[hotel-supplier-service]
    FS[flight-supplier-service]
    BUS[bus-supplier-service]
    CAB[cab-partner-service]
  end

  subgraph CT[Content and Notifications]
    RV[review-service]
    RA[rating-aggregator]
    MOD[moderation-service]
    EM[email-service]
    SMS[sms-service]
    PUSH[push-notification-service]
  end

  subgraph AN[Analytics]
    ET[event-tracking-service]
    AP[analytics-pipeline]
    RP2[reporting-service]
    KF[(Kafka Cluster)]
  end

  subgraph DS[Source of Truth]
    PGSQL[(PostgreSQL Primary and Replicas)]
    RED[(Redis Cluster)]
  end

  G --> AU
  G --> SRCH
  G --> BS
  G --> PE
  G --> PG
  G --> RV

  SRCH --> ES
  IDX --> ES
  IDX --> PGSQL

  BS --> RI
  RI --> RLOCK
  BS --> PG
  PG --> WA
  BS --> INVCS

  PE --> DP
  PE --> SP
  PE --> DE
  PE --> CO

  HS --> AS
  BUS --> AS
  CAB --> AS
  AS --> RI

  BS --> KF
  PG --> KF
  RI --> KF
  PE --> KF
  RV --> KF

  KF --> ET
  ET --> AP
  AP --> RP2

  AU --> PGSQL
  BS --> PGSQL
  PE --> PGSQL
  RV --> PGSQL
  WA --> PGSQL

  SRCH --> RED
  BS --> RED
  PE --> RED
```

## Critical booking lifecycle

search -> hold inventory -> payment -> confirm booking
