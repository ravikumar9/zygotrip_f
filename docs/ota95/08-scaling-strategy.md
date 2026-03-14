# 8) Scaling Strategy

## Capacity targets

- Daily searches: 5M+
- Concurrent bookings: 10k+
- Search latency target: < 50ms for warm cache path
- Uptime: 99.9%

## Horizontal scaling rules

### Search services

- Autoscale on CPU > 60% or p95 latency > 80ms
- Keep warm pool for peak windows
- Use Redis query cache and pre-warmed city/date keys

### Booking and inventory

- Separate write-heavy booking workers from read APIs
- Lock service shard by property_id hash
- Use Redis lock key pattern: property:{id}:room:{type}:date:{yyyy-mm-dd}

### Payment

- Route by gateway health score and success rate
- Circuit breaker per gateway
- Queue webhook retries with exponential backoff and dead-letter topic

### Supplier integrations

- One adapter pool per supplier
- Timeout budget and fallback cache per supplier
- Bulkhead isolation to avoid cascading failure

## Data scaling

- PostgreSQL partition booking and event tables by month
- Read replicas for analytics and read-heavy APIs
- Elasticsearch ILM for hot-warm-cold index lifecycle
- Kafka retention tuned for replay windows and compliance

## Performance strategy for <50ms search

- Elasticsearch query only for candidate retrieval
- Ranking engine in-memory feature fetch with Redis side cache
- Response cache for common city/date/occupancy combinations
- Async enrichment; no blocking supplier calls on search path
