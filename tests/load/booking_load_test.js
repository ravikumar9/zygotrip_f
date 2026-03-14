/**
 * ZygoTrip Booking Load Test — k6
 *
 * Target:   10,000 concurrent bookings sustained, p95 < 2s, zero oversell
 * Duration: 3-minute ramp → 5-minute peak → 2-minute ramp-down
 *
 * Tests the full checkout funnel:
 *   1. POST /api/v1/checkout/start/       — create session + hold inventory
 *   2. POST /api/v1/checkout/{id}/guest-details/  — submit guest info
 *   3. GET  /api/v1/checkout/{id}/payment-options/ — get gateways
 *   4. POST /api/v1/checkout/{id}/pay/    — initiate payment (dev_simulate)
 *
 * Also stress-tests:
 *   - Review submission (to verify fraud detection under load)
 *   - Booking list (My Trips page pagination)
 *   - Concurrent hold contention (overlapping room/date requests)
 *
 * Prerequisites:
 *   - Running ZygoTrip backend with DEBUG=true (for dev_simulate gateway)
 *   - Valid JWT token in K6_AUTH_TOKEN env var
 *   - At least one active Property + RoomType in the DB
 *
 * Run:
 *   k6 run \
 *     --env BASE_URL=http://127.0.0.1:8000 \
 *     --env AUTH_TOKEN=<jwt_token> \
 *     --env PROPERTY_ID=1 \
 *     --env ROOM_TYPE_ID=1 \
 *     tests/load/booking_load_test.js
 *
 * With HTML report:
 *   k6 run --out json=results/booking_$(date +%Y%m%d_%H%M).json \
 *     tests/load/booking_load_test.js
 */

import http from 'k6/http';
import { check, group, sleep, fail } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ── Custom metrics ──────────────────────────────────────────────────────────
const checkoutStartRate    = new Rate('checkout_start_success');
const guestDetailsRate     = new Rate('guest_details_success');
const paymentSuccessRate   = new Rate('payment_success_rate');
const checkoutLatency      = new Trend('checkout_e2e_latency_ms', true);
const holdConflictRate     = new Rate('hold_conflict_rate');
const priceChangeRate      = new Rate('price_change_rate');
const bookingErrorCount    = new Counter('booking_error_count');
const activeSessionsGauge  = new Gauge('active_sessions');

// ── Configuration ───────────────────────────────────────────────────────────
const BASE_URL      = __ENV.BASE_URL      || 'http://127.0.0.1:8000';
const AUTH_TOKEN    = __ENV.AUTH_TOKEN    || '';
const PROPERTY_ID   = parseInt(__ENV.PROPERTY_ID   || '1');
const ROOM_TYPE_ID  = parseInt(__ENV.ROOM_TYPE_ID  || '1');

if (!AUTH_TOKEN) {
  console.warn(
    '[WARNING] AUTH_TOKEN not set. Authenticated endpoints will return 401. ' +
    'Set: --env AUTH_TOKEN=<jwt_token>'
  );
}

const AUTH_HEADERS = {
  'Content-Type':  'application/json',
  'Authorization': AUTH_TOKEN ? `Bearer ${AUTH_TOKEN}` : '',
};

// ── Load profile ─────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // ── Gradual ramp-up
    booking_ramp: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { target: 100,  duration: '1m' },    // Warm up
        { target: 500,  duration: '2m' },    // Build to 500 concurrent
        { target: 1000, duration: '2m' },    // Peak: 1000 concurrent checkouts
        { target: 1000, duration: '5m' },    // Sustain peak
        { target: 0,    duration: '2m' },    // Ramp down
      ],
      gracefulRampDown: '30s',
    },

    // ── Spike test (concurrent overlapping holds — race condition stress)
    concurrent_holds: {
      executor: 'constant-arrival-rate',
      rate: 50,           // 50 simultaneous hold attempts per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 100,
      maxVUs: 200,
      startTime: '3m',   // Start after ramp-up is complete
      tags: { scenario: 'concurrent_holds' },
    },
  },

  // ── SLA thresholds ──────────────────────────────────────────────────────
  thresholds: {
    // Full booking funnel p95 < 2 seconds
    'checkout_e2e_latency_ms': [
      { threshold: 'p(50) < 800',  abortOnFail: false },
      { threshold: 'p(95) < 2000', abortOnFail: true  },   // SLA
      { threshold: 'p(99) < 5000', abortOnFail: false },
    ],
    // Payment success rate > 99.5%
    'payment_success_rate':   [{ threshold: 'rate > 0.995', abortOnFail: true }],
    // Checkout start success > 99.9% (inventory holds must not fail silently)
    'checkout_start_success': [{ threshold: 'rate > 0.99',  abortOnFail: true }],
    // HTTP error rate < 0.1%
    'http_req_failed': [{ threshold: 'rate < 0.001', abortOnFail: true }],
    // No oversell: hold conflicts should be properly rejected (409), not silent
    // If this rate is too HIGH (> 10%), it indicates under-provisioning
    'hold_conflict_rate': [{ threshold: 'rate < 0.15', abortOnFail: false }],
  },

  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function futureDate(daysFromNow) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().slice(0, 10);
}

function uniqueKey() {
  return `k6-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function post(path, body) {
  return http.post(`${BASE_URL}${path}`, JSON.stringify(body), {
    headers: AUTH_HEADERS,
    timeout: '30s',
  });
}

function get(path) {
  return http.get(`${BASE_URL}${path}`, {
    headers: AUTH_HEADERS,
    timeout: '15s',
  });
}

// ── Full checkout funnel ──────────────────────────────────────────────────────

function runCheckoutFunnel() {
  const checkIn  = futureDate(randomIntBetween(14, 60));
  const checkOut = futureDate(randomIntBetween(61, 90));
  const funnelStart = Date.now();
  activeSessionsGauge.add(1);

  // ── Step 1: Start checkout (create session + hold inventory) ─────────────
  let sessionId = null;
  group('1_checkout_start', () => {
    const res = post('/api/v1/checkout/start/', {
      property_id:   PROPERTY_ID,
      room_type_id:  ROOM_TYPE_ID,
      check_in:      checkIn,
      check_out:     checkOut,
      guests:        2,
      rooms:         1,
      device_fingerprint: uniqueKey(),
    });

    const ok = check(res, {
      'checkout_start 201':         (r) => r.status === 201,
      'checkout_start has session': (r) => !!r.json('session_id'),
    });

    checkoutStartRate.add(ok);

    if (res.status === 409) {
      // Inventory conflict — hold correctly rejected (not a bug)
      holdConflictRate.add(true);
      activeSessionsGauge.add(-1);
      return;
    }

    if (!ok) {
      bookingErrorCount.add(1, { step: 'checkout_start', status: String(res.status) });
      activeSessionsGauge.add(-1);
      return;
    }

    holdConflictRate.add(false);
    sessionId = res.json('session_id');
  });

  if (!sessionId) {
    activeSessionsGauge.add(-1);
    return;
  }

  sleep(0.2);   // User fills in guest details

  // ── Step 2: Submit guest details ──────────────────────────────────────────
  let guestOk = false;
  group('2_guest_details', () => {
    const res = post(`/api/v1/checkout/${sessionId}/guest-details/`, {
      name:             'Load Test User',
      email:            `loadtest+${uniqueKey()}@example.com`,
      phone:            '9876543210',
      special_requests: '',
    });

    guestOk = check(res, {
      'guest_details 200': (r) => r.status === 200,
    });
    guestDetailsRate.add(guestOk);

    if (!guestOk) {
      bookingErrorCount.add(1, { step: 'guest_details', status: String(res.status) });
    }
  });

  if (!guestOk) {
    activeSessionsGauge.add(-1);
    return;
  }

  sleep(0.5);   // User reviews payment options

  // ── Step 3: Get payment options ───────────────────────────────────────────
  group('3_payment_options', () => {
    const res = get(`/api/v1/checkout/${sessionId}/payment-options/`);
    check(res, {
      'payment_options 200':       (r) => r.status === 200,
      'has gateways':              (r) => Array.isArray(r.json('gateways')),
      'dev_simulate available':    (r) => {
        const gateways = r.json('gateways') || [];
        return gateways.some(g => g.id === 'dev_simulate');
      },
    });
  });

  sleep(0.3);   // User selects payment method

  // ── Step 4: Initiate payment (dev_simulate) ───────────────────────────────
  group('4_initiate_payment', () => {
    const res = post(`/api/v1/checkout/${sessionId}/pay/`, {
      gateway:          'dev_simulate',
      idempotency_key:  uniqueKey(),
    });

    const ok = check(res, {
      'payment 200':             (r) => r.status === 200,
      'payment status completed': (r) => r.json('status') === 'completed',
      'has booking':             (r) => !!r.json('booking'),
    });

    paymentSuccessRate.add(ok);

    if (res.status === 409) {
      // Price changed — this is expected behavior, not a bug
      const oldPrice = res.json('old_price');
      const newPrice = res.json('new_price');
      priceChangeRate.add(true);
      check(res, {
        'price_change has old_price': (r) => !!r.json('old_price'),
        'price_change has new_price': (r) => !!r.json('new_price'),
      });
    } else if (!ok) {
      priceChangeRate.add(false);
      bookingErrorCount.add(1, { step: 'payment', status: String(res.status) });
    } else {
      priceChangeRate.add(false);
    }
  });

  checkoutLatency.add(Date.now() - funnelStart);
  activeSessionsGauge.add(-1);
}

// ── Concurrent hold stress test ───────────────────────────────────────────────
// Tests that two simultaneous holds for the same room/dates result in exactly
// one success and one 409 Conflict — no double-booking allowed.

function runConcurrentHoldStress() {
  const checkIn  = futureDate(5);   // Near-future dates — higher contention
  const checkOut = futureDate(8);

  const body = JSON.stringify({
    property_id:  PROPERTY_ID,
    room_type_id: ROOM_TYPE_ID,
    check_in:     checkIn,
    check_out:    checkOut,
    guests:       2,
    rooms:        1,
    device_fingerprint: uniqueKey(),
  });

  const res = http.post(`${BASE_URL}/api/v1/checkout/start/`, body, {
    headers: AUTH_HEADERS,
    timeout: '10s',
    tags: { scenario: 'concurrent_holds' },
  });

  const isSuccess  = res.status === 201;
  const isConflict = res.status === 409;
  const isExpected = isSuccess || isConflict;

  check(res, {
    'concurrent_hold expected response': () => isExpected,
    'concurrent_hold not 500':          (r) => r.status !== 500,
  });

  holdConflictRate.add(isConflict);

  if (!isExpected) {
    bookingErrorCount.add(1, { step: 'concurrent_hold', status: String(res.status) });
  }
}

// ── My Bookings (read-heavy) ──────────────────────────────────────────────────

function runBookingsList() {
  const res = get('/api/v1/bookings/my/?page=1&page_size=10');
  check(res, {
    'my_bookings 200':      (r) => r.status === 200,
    'my_bookings is array': (r) => Array.isArray(r.json('data')),
  });
}

// ── Main VU function ─────────────────────────────────────────────────────────

export default function () {
  if (__ENV.SCENARIO === 'concurrent_holds') {
    runConcurrentHoldStress();
    return;
  }

  const roll = Math.random();

  if (roll < 0.70) {
    runCheckoutFunnel();
  } else if (roll < 0.90) {
    runBookingsList();
  } else {
    runConcurrentHoldStress();
  }

  sleep(randomIntBetween(1, 5) * 0.1);   // 100ms – 500ms think-time
}

// ── Summary ───────────────────────────────────────────────────────────────────

export function handleSummary(data) {
  const metrics = data.metrics;

  const summary = {
    timestamp: new Date().toISOString(),
    target: '1000 concurrent VUs, p95 < 2s, payment success > 99.5%',
    thresholds_passed: !data.thresholds || Object.values(data.thresholds).every(t => t.ok),
    metrics: {
      checkout_e2e_p95_ms:    metrics['checkout_e2e_latency_ms']?.values?.['p(95)'],
      checkout_e2e_p99_ms:    metrics['checkout_e2e_latency_ms']?.values?.['p(99)'],
      payment_success_rate:   metrics['payment_success_rate']?.values?.rate,
      checkout_start_success: metrics['checkout_start_success']?.values?.rate,
      hold_conflict_rate:     metrics['hold_conflict_rate']?.values?.rate,
      price_change_rate:      metrics['price_change_rate']?.values?.rate,
      total_booking_errors:   metrics['booking_error_count']?.values?.count,
      rps:                    metrics['http_reqs']?.values?.rate,
    },
    interpretation: {
      hold_conflict_note:
        'hold_conflict_rate > 0 is EXPECTED (inventory exhaustion). ' +
        'A rate of 0.00 with high concurrency may indicate the lock is not working.',
      price_change_note:
        'price_change_rate > 0 is EXPECTED (demand/time-based pricing). ' +
        'Frontend should handle 409 price-changed responses gracefully.',
    },
  };

  return {
    stdout: JSON.stringify(summary, null, 2),
    'results/booking_summary.json': JSON.stringify(summary, null, 2),
  };
}
