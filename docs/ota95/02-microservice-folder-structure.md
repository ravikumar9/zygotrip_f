# 2) Microservice Folder Structure

```text
platform/
  gateway/
    api-gateway/
  services/
    identity/
      auth-service/
      user-profile-service/
      session-service/
      otp-verification-service/
      loyalty-service/
    search/
      search-service/
      search-indexer/
      autocomplete-service/
      recommendation-service/
      ranking-engine/
    inventory/
      property-inventory-service/
      room-inventory-service/
      seat-inventory-service/
      cab-fleet-service/
      availability-sync-service/
    booking/
      booking-service/
      booking-modification-service/
      cancellation-service/
      refund-service/
      invoice-service/
    pricing/
      pricing-engine/
      dynamic-pricing-service/
      surge-pricing-service/
      discount-engine/
      coupon-service/
    payment/
      payment-gateway-service/
      wallet-service/
      refund-processor/
      fraud-detection-service/
    supplier/
      hotel-supplier-service/
      flight-supplier-service/
      bus-supplier-service/
      cab-partner-service/
    content/
      review-service/
      rating-aggregator/
      moderation-service/
    notifications/
      email-service/
      sms-service/
      push-notification-service/
    analytics/
      event-tracking-service/
      analytics-pipeline/
      reporting-service/
  contracts/
    openapi/
    events/
    protobuf/
  shared/
    libs/
      authz/
      tracing/
      idempotency/
      retry/
      cache/
    schema-registry/
  infra/
    k8s/
      base/
      overlays/
    terraform/
    helm/
    observability/
      prometheus/
      grafana/
      opentelemetry/
  migration/
    strangler-router/
    dual-write-workers/
    replay-tools/
```

## Service template (each service)

```text
service-name/
  cmd/
  app/
    api/
    domain/
    repository/
    workers/
  tests/
    unit/
    integration/
    contract/
  deploy/
    Dockerfile
    k8s.yaml
  openapi/
  README.md
```

## Backward compatibility lane

- Keep current Django monolith active as compatibility core during migration.
- New services read from existing PostgreSQL schema first.
- Any new write path uses outbox and idempotency keys.
- API gateway routes per endpoint, not big-bang cutover.
