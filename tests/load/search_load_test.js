/**
 * ZygoTrip Search Load Test — k6
 *
 * Target:   1,000 RPS sustained, p95 < 200ms, error rate < 0.1%
 * Duration: 10-minute ramp-up → 5-minute sustained → 2-minute ramp-down
 *
 * Tests:
 *   1. Hotel search (primary endpoint — 70% of traffic)
 *   2. Property detail page (20% — browsing after search)
 *   3. Price calendar (10% — availability check)
 *
 * Run:
 *   k6 run tests/load/search_load_test.js
 *
 * With custom target:
 *   k6 run --env BASE_URL=https://api.zygotrip.com tests/load/search_load_test.js
 *
 * With HTML report:
 *   k6 run --out json=results/search_$(date +%Y%m%d_%H%M).json tests/load/search_load_test.js
 *
 * Install k6: https://k6.io/docs/get-started/installation/
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ── Custom metrics ──────────────────────────────────────────────────────────
const searchSuccessRate    = new Rate('search_success_rate');
const detailSuccessRate    = new Rate('detail_success_rate');
const calendarSuccessRate  = new Rate('calendar_success_rate');
const searchLatency        = new Trend('search_latency_ms', true);
const detailLatency        = new Trend('detail_latency_ms', true);
const cacheHitRate         = new Rate('cache_hit_rate');
const errorCounter         = new Counter('error_count');

// ── Configuration ───────────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

const CITIES = [
  'goa', 'mumbai', 'delhi', 'bangalore', 'jaipur',
  'udaipur', 'shimla', 'manali', 'kerala', 'ooty',
];

const PROPERTY_SLUGS = [
  'the-taj-mahal-palace-mumbai',
  'leela-palace-udaipur',
  'aman-new-delhi',
  'park-hyatt-goa',
  'wildflower-hall-shimla',
  'yatt-goa',
  'sea-view-resort-goa',
  'mountain-retreat-manali',
];

const SORT_OPTIONS = ['relevance', 'price_asc', 'price_desc', 'rating'];

// ── Load profile ─────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // ── Ramp-up scenario (progressive load)
    ramp_up: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 500,
      stages: [
        { target: 200,  duration: '2m' },    // Ramp 50 → 200 RPS
        { target: 600,  duration: '3m' },    // Ramp 200 → 600 RPS
        { target: 1000, duration: '5m' },    // Ramp 600 → 1000 RPS
        { target: 1000, duration: '5m' },    // Sustain 1000 RPS (peak)
        { target: 0,    duration: '2m' },    // Ramp down
      ],
    },
  },

  // ── SLA thresholds ──────────────────────────────────────────────────────
  thresholds: {
    // Primary target: p95 < 200ms for search
    'search_latency_ms': [
      { threshold: 'p(50) < 80',  abortOnFail: false },
      { threshold: 'p(95) < 200', abortOnFail: true  },   // SLA
      { threshold: 'p(99) < 500', abortOnFail: false },
    ],
    // Detail page: p95 < 500ms (heavier query)
    'detail_latency_ms': [
      { threshold: 'p(95) < 500', abortOnFail: false },
    ],
    // Error rates
    'search_success_rate':   [{ threshold: 'rate > 0.999', abortOnFail: true }],
    'detail_success_rate':   [{ threshold: 'rate > 0.995', abortOnFail: false }],
    'calendar_success_rate': [{ threshold: 'rate > 0.995', abortOnFail: false }],
    // Overall HTTP error rate
    'http_req_failed': [{ threshold: 'rate < 0.001', abortOnFail: true }],
    // Cache hit rate target (informational)
    'cache_hit_rate': [{ threshold: 'rate > 0.40', abortOnFail: false }],
  },

  // ── Output ───────────────────────────────────────────────────────────────
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function futureDate(daysFromNow) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().slice(0, 10);
}

function randomSearchParams() {
  const checkIn  = futureDate(randomIntBetween(7, 90));
  const checkOut = futureDate(randomIntBetween(91, 150));
  return {
    city:     randomItem(CITIES),
    check_in:  checkIn,
    check_out: checkOut,
    guests:   randomIntBetween(1, 4),
    rooms:    1,
    sort:     randomItem(SORT_OPTIONS),
  };
}

// ── Test scenarios ────────────────────────────────────────────────────────────

/**
 * Hotel Search — 70% of traffic
 * Tests Elasticsearch search (with PostgreSQL fallback),
 * caching layer, and DRF serialization.
 */
function searchHotels() {
  const params = randomSearchParams();
  const qs = Object.entries(params).map(([k, v]) => `${k}=${v}`).join('&');
  const url = `${BASE_URL}/api/v1/hotels/search/?${qs}`;

  const startTime = Date.now();
  const res = http.get(url, {
    tags: { endpoint: 'search' },
    timeout: '10s',
  });
  searchLatency.add(Date.now() - startTime);

  const ok = check(res, {
    'search 200':             (r) => r.status === 200,
    'search has results key': (r) => r.json('success') === true,
    'search latency < 200ms': (r) => r.timings.duration < 200,
  });

  searchSuccessRate.add(ok);
  if (!ok) errorCounter.add(1, { type: 'search' });

  // Track cache hits via header (if backend sends X-Cache header)
  const cacheHeader = res.headers['X-Cache'] || res.headers['x-cache'] || '';
  cacheHitRate.add(cacheHeader.toLowerCase().includes('hit'));

  return res;
}

/**
 * Property Detail — 20% of traffic
 * Tests property + room availability + pricing aggregation.
 */
function propertyDetail() {
  const slug = randomItem(PROPERTY_SLUGS);
  const params = randomSearchParams();
  const qs = `check_in=${params.check_in}&check_out=${params.check_out}&guests=${params.guests}`;
  const url = `${BASE_URL}/api/v1/hotels/${slug}/?${qs}`;

  const startTime = Date.now();
  const res = http.get(url, {
    tags: { endpoint: 'detail' },
    timeout: '15s',
  });
  detailLatency.add(Date.now() - startTime);

  const ok = check(res, {
    'detail 200 or 404':      (r) => r.status === 200 || r.status === 404,
    'detail not 500':         (r) => r.status !== 500,
    'detail latency < 500ms': (r) => r.timings.duration < 500,
  });

  detailSuccessRate.add(ok);
  if (!ok) errorCounter.add(1, { type: 'detail' });

  return res;
}

/**
 * Price Calendar — 10% of traffic
 * Tests 30-day availability + pricing calendar endpoint.
 */
function priceCalendar() {
  const slug = randomItem(PROPERTY_SLUGS);
  const url = `${BASE_URL}/api/v1/properties/price-calendar/?property_slug=${slug}`;

  const res = http.get(url, {
    tags: { endpoint: 'calendar' },
    timeout: '10s',
  });

  const ok = check(res, {
    'calendar 200 or 404': (r) => r.status === 200 || r.status === 404,
    'calendar not 500':    (r) => r.status !== 500,
  });

  calendarSuccessRate.add(ok);
  if (!ok) errorCounter.add(1, { type: 'calendar' });
}

// ── Main VU function ─────────────────────────────────────────────────────────

export default function () {
  const roll = Math.random();

  if (roll < 0.70) {
    group('hotel_search', searchHotels);
  } else if (roll < 0.90) {
    group('property_detail', propertyDetail);
  } else {
    group('price_calendar', priceCalendar);
  }

  // Small think-time between requests (simulates real user behavior)
  sleep(randomIntBetween(1, 3) * 0.1);   // 100ms – 300ms
}

// ── Summary output ───────────────────────────────────────────────────────────

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    target: '1000 RPS, p95 < 200ms',
    thresholds_passed: Object.values(data.metrics)
      .filter(m => m.thresholds)
      .every(m => Object.values(m.thresholds).every(t => t.ok)),
    metrics: {
      search_p95_ms:     data.metrics['search_latency_ms']?.values?.['p(95)'],
      detail_p95_ms:     data.metrics['detail_latency_ms']?.values?.['p(95)'],
      search_success:    data.metrics['search_success_rate']?.values?.rate,
      cache_hit_rate:    data.metrics['cache_hit_rate']?.values?.rate,
      total_errors:      data.metrics['error_count']?.values?.count,
      http_rps:          data.metrics['http_reqs']?.values?.rate,
    },
  };

  return {
    stdout: JSON.stringify(summary, null, 2),
    'results/search_summary.json': JSON.stringify(summary, null, 2),
  };
}
