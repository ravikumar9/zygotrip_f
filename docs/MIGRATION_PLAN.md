# ZygoTrip Production Migration Plan

## Pre-Deployment Checklist

### Environment Variables Required (all P0)

All variables below are required before starting the application. Missing any P0 variable will cause startup failure.

#### Database

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgres://user:pass@host:5432/zygotrip` | PostgreSQL connection string |
| `REDIS_URL` | `redis://host:6379/0` | Redis for Celery broker + cache |

#### Payments

| Variable | Notes |
|----------|-------|
| `CASHFREE_APP_ID` | Cashfree merchant app ID |
| `CASHFREE_SECRET_KEY` | Cashfree secret key for HMAC signing |
| `STRIPE_SECRET_KEY` | Stripe secret key (sk_live_...) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook endpoint signing secret |
| `PAYTM_MERCHANT_ID` | Paytm merchant ID |
| `PAYTM_MERCHANT_KEY` | Paytm merchant key for checksum |

#### Push Notifications

| Variable | Notes |
|----------|-------|
| `FCM_PROJECT_ID` | Firebase project ID |
| `FCM_SERVER_KEY` | Firebase Cloud Messaging server key |

#### WhatsApp & SMS

| Variable | Notes |
|----------|-------|
| `WHATSAPP_ACCESS_TOKEN` | Meta WhatsApp Business API token |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID for sending |
| `SMS_PROVIDER` | Set to `msg91` |
| `MSG91_AUTH_KEY` | MSG91 authentication key |
| `MSG91_TEMPLATE_ID` | MSG91 OTP/notification template ID |

#### Search

| Variable | Default | Notes |
|----------|---------|-------|
| `ELASTICSEARCH_HOST` | `localhost` | ES host (optional - falls back to PG FTS if unavailable) |
| `ELASTICSEARCH_PORT` | `9200` | ES port |
| `ELASTICSEARCH_INDEX` | `zygotrip_properties` | Index name |

#### Monitoring & Observability

| Variable | Notes |
|----------|-------|
| `SENTRY_DSN` | Sentry error tracking DSN |
| `ADMIN_ALERT_EMAIL` | Email for critical system alerts |

#### Supplier Webhooks

| Variable | Notes |
|----------|-------|
| `SUPPLIER_HOTELBEDS_WEBHOOK_SECRET` | HMAC secret for Hotelbeds webhooks |
| `SUPPLIER_STAAH_WEBHOOK_SECRET` | HMAC secret for STAAH webhooks |

#### Django Core

| Variable | Notes |
|----------|-------|
| `DJANGO_SECRET_KEY` | Django secret key (min 50 chars, randomly generated) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |
| `DJANGO_DEBUG` | Set to `False` in production |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins |

---

### Database Migrations (run in order)

Run migrations in the following order to avoid foreign key constraint errors:

```bash
# 1. Core app (cities, geo index, A/B experiments, holiday calendar, device fingerprint)
python manage.py migrate core 0020_add_district_to_city
python manage.py migrate core 0021_geoindex_geohash4_geoindex_geohash6_and_more
python manage.py migrate core 0022_experiment
python manage.py migrate core 0023_holidaycalendar
python manage.py migrate core 0024_devicefingerprint_fcm_token

# 2. Hotels app (review photos/helpfulness, rate plans, cancellation, check-in times, saved properties)
python manage.py migrate hotels 0026_reviewphoto_reviewhelpfulness
python manage.py migrate hotels 0027_cancellationpolicy_cancellationtier_rateplan
python manage.py migrate hotels 0028_add_property_checkin_times_house_rules
python manage.py migrate hotels 0029_add_savedproperty

# 3. Pricing app (occupancy/LOS pricing, property discounts)
python manage.py migrate pricing 0003_occupancypricing_lospricing
python manage.py migrate pricing 0004_propertydiscount

# 4. Booking app (rate plan policies, vouchers, reconciliation, invoices)
python manage.py migrate booking 0019_rateplanpolicy
python manage.py migrate booking 0020_bookingvoucher
python manage.py migrate booking 0021_supplierreconciliation_supplierreconciliationitem
python manage.py migrate booking 0022_bookinginvoice

# 5. Wallet app (updated transaction types)
python manage.py migrate wallet 0005_alter_wallettransaction_txn_type

# 6. Search app (extended search index, user search profiles)
python manage.py migrate search 0007_propertysearchindex_cashback_amount_and_more
python manage.py migrate search 0008_propertysearchindex_click_through_rate_and_more
python manage.py migrate search 0009_propertysearchindex_availability_reliability_and_more
python manage.py migrate search 0010_usersearchprofile

# 7. Rooms app (indexes)
python manage.py migrate rooms 0010_roomtype_indexes

# 8. Packages app (booking support, add-ons)
python manage.py migrate packages 0002_packagebooking_packagebookingtraveler_and_more
python manage.py migrate packages 0003_packageaddon_packagebookingaddon_and_more

# 9. Buses app (seats, lock sessions, bookings)
python manage.py migrate buses 0008_boardingpoint_droppingpoint_busseat_lock_session_and_more
python manage.py migrate buses 0009_busbooking_contact_email_busbooking_contact_phone_and_more

# 10. Cabs app (cab types, drop address, driver reviews, dispatch)
python manage.py migrate cabs 0008_cab_cab_type_cabbooking_drop_address_and_more
python manage.py migrate cabs 0009_cabtrip_driverreview
python manage.py migrate cabs 0010_dispatchrequest_driverlocation

# 11. Payments app (allow null user for guest bookings)
python manage.py migrate payments 0007_allow_null_user_for_guest_bookings
```

**Verify all migrations applied cleanly**:

```bash
python manage.py showmigrations | grep -v [X]  # Should return nothing if all applied
```

---

### Seed Data Commands

Run these management commands after migrations, before the first traffic:

```bash
# Seed 2025 and 2026 Indian public holidays into HolidayCalendar
# Required for holiday-aware pricing and demand forecasting (Systems 1, 2, 7)
python manage.py seed_holiday_calendar

# Seed Indian cities (tier 1/2/3) with geo coordinates and GeoHash
# Required for location-based search and map features
python manage.py seed_indian_cities

# Optional: Pre-warm Playwright screenshots for SEO (run in background)
# python manage.py seed_playwright_live  # takes ~30 min for large catalogs
```

---

### Pre-Launch Smoke Tests

Run the following checks before switching traffic to the new environment:

```bash
# Django system checks
python manage.py check --deploy

# Celery worker connectivity
celery -A zygotrip_project inspect ping

# Elasticsearch connection (optional)
curl -s http://$ELASTICSEARCH_HOST:9200/_cluster/health | python -m json.tool

# Redis connectivity
redis-cli -u $REDIS_URL ping

# API health endpoint
curl -s https://api.zygotrip.com/api/v1/admin/monitoring/health/ -H Authorization: Bearer $ADMIN_TOKEN
```

---

## Blue-Green Deployment Steps

ZygoTrip uses a blue-green deployment model to achieve zero-downtime releases.

### Step 1: Provision Green Environment

1. Spin up new (green) application servers and Celery workers matching the blue configuration
2. Green environment connects to a **snapshot replica** of the production database
3. Confirm green instances are healthy but receiving no traffic (`health = starting`)

### Step 2: Run Migrations on Green Database

1. Point green environment at the production database (migrations are run against prod DB)
2. All migrations in this release are **additive only** (no column drops or renames)
3. Run the migration sequence listed in the Pre-Deployment Checklist above
4. Verify: `python manage.py showmigrations | grep -v [X]` returns empty

### Step 3: Deploy Application Containers

```bash
# Pull and start containers on green servers
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --no-deps web celery celery-beat
```

2. Run seed commands on green environment (idempotent - safe to re-run)
3. Start Celery beat scheduler on green (pause blue beat scheduler first to avoid duplicate scheduled tasks)

### Step 4: Run Smoke Tests Against Green

Run the pre-launch smoke test suite against the green environment on its internal/staging URL before exposing to traffic.

Key tests to verify:
- [ ] `GET /api/v1/admin/monitoring/health/` returns all green
- [ ] `GET /api/v1/hotels/search/?city=goa&check_in=...&check_out=...&guests=2` returns results
- [ ] Auth token obtain + refresh flow works
- [ ] Celery worker processes a test task
- [ ] Redis cache read/write works
- [ ] Invoice generation endpoint works on a known test booking

### Step 5: Flip DNS/Load Balancer

1. Update load balancer (AWS ALB / Nginx / Caddy) to point to green target group
2. Set blue target group weight to 0% and green to 100%
3. Record the exact timestamp of the flip for monitoring reference

### Step 6: Monitor for 30 Minutes

After the flip, actively monitor:

| Signal | Target | Action if Breached |
|--------|--------|-------------------|
| HTTP 5xx rate | < 0.1% of requests | Immediate rollback |
| P95 response time | < 500ms | Investigate, rollback if sustained |
| Celery queue depth (bookings queue) | < 100 tasks | Investigate |
| Payment gateway success rate | > 99% | Immediate rollback |
| Sentry error rate | < 5 new errors/min | Investigate |

### Step 7: Decommission Blue

After 30 minutes of stable metrics:
1. Stop blue application containers
2. Retain blue infrastructure for 24 hours (for rapid rollback if a delayed issue surfaces)
3. Terminate blue instances after 24 hours if stable

---

## Rollback Procedure

**Target time to rollback**: < 5 minutes

### Immediate Rollback (< 5 min)

1. Flip load balancer back to blue target group (set green weight to 0%, blue to 100%)
2. Restart blue Celery beat scheduler
3. Verify: monitor health endpoint on blue environment

### Why No Reverse Migrations Are Needed

All migrations in this release are strictly **additive**:
- New tables are added (`BookingInvoice`, `HolidayCalendar`, `SupplierReconciliation`, etc.)
- New columns are added to existing tables
- New indexes are added
- No existing columns are dropped or renamed
- No data is transformed or deleted

The old (blue) application code ignores unknown columns, so rolling back to blue with the new schema applied is safe.

### If Rollback Is Not Sufficient

In the rare case of a data corruption issue requiring schema reversal:
1. Restore from the last pre-deployment database snapshot (taken automatically before migration step)
2. Accept potential data loss of transactions during the green deployment window
3. Replay transactions from application logs if available

---

## Performance Targets Post-Deploy

These are the SLO targets to confirm within 24 hours of deployment:

### API Latency

| Endpoint | P50 Target | P95 Target | P99 Target |
|----------|------------|------------|------------|
| Hotel search (Elasticsearch) | < 50ms | < 200ms | < 500ms |
| Hotel search (PG fallback) | < 100ms | < 500ms | < 1000ms |
| Hotel detail | < 30ms | < 100ms | < 300ms |
| Booking creation | < 200ms | < 800ms | < 2000ms |
| Payment verification | < 100ms | < 500ms | < 1000ms |
| All other endpoints | < 50ms | < 200ms | < 500ms |

### Reliability

| Metric | Target |
|--------|--------|
| Overall API success rate | > 99.9% |
| Booking flow success rate (hold to confirmation) | > 99.5% |
| Payment gateway success rate | > 99% |
| Celery critical queue latency (bookings queue) | < 5 seconds |
| Celery scheduled task on-time rate | > 99% |
| API error rate (HTTP 5xx) | < 0.1% |

### Infrastructure

| Resource | Target |
|---------|--------|
| Redis memory usage | < 80% |
| PostgreSQL connection pool utilization | < 70% |
| Elasticsearch cluster health | Green |
| Celery worker CPU | < 70% average |

---

## Monitoring Alerts (Grafana)

All alerts are defined in the Grafana dashboard provisioned via `docker-compose.yml`.

### PagerDuty Alerts (P0 - wake-someone-up)

| Metric | Threshold | Duration | Action |
|--------|-----------|----------|--------|
| `booking_failures_rate` | > 1% of bookings | 5 consecutive minutes | PagerDuty + Slack #incidents |
| `payment_gateway_error_rate` | > 2% of payments | 3 consecutive minutes | PagerDuty + Slack #incidents |
| `api_5xx_rate` | > 0.5% of requests | 5 consecutive minutes | PagerDuty + Slack #incidents |
| `postgres_connection_failures` | > 0 | Immediately | PagerDuty (P0) |
| `redis_connection_failures` | > 0 | Immediately | PagerDuty (P0) |

### Slack Alerts (P1 - investigate within 30 min)

| Metric | Threshold | Duration | Channel |
|--------|-----------|----------|---------|
| `celery_queue_length{queue=bookings}` | > 100 tasks | 5 minutes | #ops-alerts |
| `celery_queue_length{queue=notifications}` | > 500 tasks | 5 minutes | #ops-alerts |
| `postgres_slow_queries_rate` | > 5/min | 10 minutes | #ops-alerts |
| `redis_memory_usage` | > 80% | 5 minutes | #ops-alerts |
| `elasticsearch_cluster_status` | Yellow | 10 minutes | #ops-alerts |
| `api_p95_latency{endpoint=search}` | > 500ms | 10 minutes | #ops-alerts |
| `celery_beat_last_run_age` | > 10 min since last beat | Immediately | #ops-alerts |

### Email Alerts (P2 - investigate next business day)

| Metric | Threshold | Recipient |
|--------|-----------|-----------|
| Daily booking success rate | < 99% | `ADMIN_ALERT_EMAIL` |
| Settlement task failure | Any failure | `ADMIN_ALERT_EMAIL` |
| Supplier sync failure | 3 consecutive failures | `ADMIN_ALERT_EMAIL` |
| Elasticsearch index lag | > 1 hour behind | `ADMIN_ALERT_EMAIL` |

---

## Celery Beat Schedule (Production)

Confirm the following scheduled tasks are registered after deployment:

| Task Name | Schedule | Queue | Purpose |
|-----------|----------|-------|---------|
| `weekly-settlements` | Monday 2 AM IST | settlements | Run weekly owner settlement payouts |
| `monthly-settlements` | 1st of month, 3 AM | settlements | Run monthly settlement batch |
| `daily-refund-adjustments` | Daily 1 AM | settlements | Process pending refund adjustments |
| `competitor-price-scan` | Every 3 hours | pricing | Crawl competitor pricing data |
| `adaptive-competitor-dispatch` | Every 15 minutes | pricing | Adaptive competitor crawl dispatch |
| `reindex-elasticsearch` | Daily 4 AM | search | Full re-index of property search index |
| `send-trip-reminders` | Hourly | notifications | Send WhatsApp trip reminders |
| `expire-inventory-holds` | Every 5 minutes | bookings | Clean up expired inventory holds |

**Verify scheduled tasks are registered**:

```bash
celery -A zygotrip_project inspect scheduled
```

---

## Post-Deployment Communication

After a successful deployment, send the following communications:

1. **Internal Slack (#deployments)**: Deployment complete message with version, timestamp, and on-call engineer
2. **Status Page**: Update status page to resolved if any maintenance window was declared
3. **Owner Newsletter** (if new features): Email property owners about new dashboard features

**Deployment log entry** (store in `docs/deployment-log.md`):

    Date: YYYY-MM-DD HH:MM IST
    Version: git SHA or tag
    Deployed by: engineer name
    Migrations run: list of migration names
    Rollback available until: YYYY-MM-DD (blue decommission date)
    Issues during deploy: none / description
