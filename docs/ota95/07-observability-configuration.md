# 7) Observability Configuration

## Metrics to track

- search_latency_ms
- booking_success_rate
- payment_failure_rate
- inventory_lock_conflict_rate
- api_p95_ms by route

## SLOs and alert thresholds

- Search p95 < 200ms alert if > 200ms for 10 minutes
- Booking end-to-end p95 < 2s alert if > 2s for 5 minutes
- Payment failure rate < 5% alert if >= 5% for 5 minutes
- Inventory lock conflict rate < 2% alert if >= 2% for 10 minutes

## Prometheus alert examples

```yaml
groups:
- name: ota-critical
  rules:
  - alert: HighPaymentFailureRate
    expr: sum(rate(payment_failed_total[5m])) / sum(rate(payment_attempt_total[5m])) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: Payment failure rate above 5%

  - alert: BookingLatencyHigh
    expr: histogram_quantile(0.95, sum(rate(booking_duration_seconds_bucket[5m])) by (le)) > 2
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: Booking p95 latency above 2s

  - alert: SearchLatencyHigh
    expr: histogram_quantile(0.95, sum(rate(search_duration_seconds_bucket[5m])) by (le)) > 0.2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: Search p95 latency above 200ms
```

## OpenTelemetry collector baseline

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

processors:
  batch:
  memory_limiter:
    limit_mib: 512

exporters:
  prometheus:
    endpoint: 0.0.0.0:9464
  otlp:
    endpoint: tempo.ota-observability.svc.cluster.local:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

## Dashboards

- Executive: bookings, GMV, success rate, uptime
- Search: QPS, cache hit ratio, ES latency, ranking latency
- Booking: hold success, lock waits, booking state transition failures
- Payment: gateway-wise conversion, webhook lag, refund turnaround time
