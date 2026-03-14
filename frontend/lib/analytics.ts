/**
 * ZygoTrip Analytics — Production-grade event tracking.
 *
 * Supports:
 *  - Google Analytics 4 (GA4) via gtag.js
 *  - Google Tag Manager (GTM) dataLayer
 *  - Sentry error tracking (lazy-loaded)
 *  - Custom event queue for offline buffering
 *
 * All public functions are safe to call SSR — they no-op on the server.
 *
 * Usage:
 *   import { analytics } from '@/lib/analytics';
 *   analytics.track('search_submitted', { destination: 'Goa', guests: 2 });
 */

// ── Types ────────────────────────────────────────────────────────

export type EventName =
  | 'page_view'
  | 'search_submitted'
  | 'autosuggest_selected'
  | 'hotel_card_clicked'
  | 'hotel_card_impression'
  | 'hotel_page_viewed'
  | 'room_selected'
  | 'room_viewed'
  | 'gallery_opened'
  | 'filter_applied'
  | 'sort_changed'
  | 'coupon_applied'
  | 'coupon_failed'
  | 'wallet_applied'
  | 'booking_started'
  | 'booking_completed'
  | 'booking_failed'
  | 'payment_initiated'
  | 'payment_completed'
  | 'payment_failed'
  | 'payment_method_selected'
  | 'promo_section_opened'
  | 'promo_applied'
  | 'promo_removed'
  | 'wishlist_toggled'
  | 'share_clicked'
  | 'login_started'
  | 'login_completed'
  | 'signup_completed'
  | 'error_boundary_triggered'
  | 'api_error'
  | 'experiment_assigned'
  | 'cta_clicked'
  | 'scroll_depth'
  | 'time_on_page';

export interface EventProperties {
  [key: string]: string | number | boolean | null | undefined;
}

interface GTMDataLayer {
  push: (data: Record<string, unknown>) => void;
}

// Extend Window for gtag and GTM
declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: GTMDataLayer;
  }
}

// ── Constants ────────────────────────────────────────────────────

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '';
const GTM_CONTAINER_ID  = process.env.NEXT_PUBLIC_GTM_CONTAINER_ID || '';
const SENTRY_DSN        = process.env.NEXT_PUBLIC_SENTRY_DSN || '';
const IS_BROWSER        = typeof window !== 'undefined';
const IS_PRODUCTION     = process.env.NODE_ENV === 'production';

// ── Offline Event Queue ──────────────────────────────────────────

const eventQueue: Array<{ name: EventName; properties: EventProperties; timestamp: number }> = [];
const MAX_QUEUE_SIZE = 50;

function flushQueue() {
  if (!IS_BROWSER) return;
  while (eventQueue.length > 0) {
    const event = eventQueue.shift();
    if (event) {
      sendToGA4(event.name, event.properties);
      sendToGTM(event.name, event.properties);
    }
  }
}

// ── GA4 ──────────────────────────────────────────────────────────

function sendToGA4(name: string, properties: EventProperties) {
  if (!IS_BROWSER || !window.gtag) return;
  window.gtag('event', name, {
    ...properties,
    send_to: GA_MEASUREMENT_ID,
  });
}

// ── GTM dataLayer ────────────────────────────────────────────────

function sendToGTM(name: string, properties: EventProperties) {
  if (!IS_BROWSER || !window.dataLayer) return;
  window.dataLayer.push({
    event: name,
    ...properties,
    _timestamp: Date.now(),
  });
}

// ── Sentry (lazy) ────────────────────────────────────────────────

// Webpack-opaque require — prevents static analysis/resolution of optional deps
// eslint-disable-next-line @typescript-eslint/no-implied-eval
const dynamicRequire = new Function('mod', 'return require(mod)') as (mod: string) => unknown;

let sentryInitialized = false;

async function initSentry() {
  if (sentryInitialized || !SENTRY_DSN || !IS_BROWSER) return;
  try {
    const Sentry = dynamicRequire('@sentry/browser') as {
      init: (opts: Record<string, unknown>) => void;
    };
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: IS_PRODUCTION ? 'production' : 'development',
      tracesSampleRate: IS_PRODUCTION ? 0.1 : 1.0,
    });
    sentryInitialized = true;
  } catch {
    // @sentry/browser not installed — errors go to console only
  }
}

function captureException(error: Error, context?: Record<string, unknown>) {
  if (!IS_BROWSER) return;
  try {
    const Sentry = dynamicRequire('@sentry/browser') as {
      withScope: (fn: (scope: { setExtra: (k: string, v: unknown) => void }) => void) => void;
      captureException: (error: Error) => void;
    };
    Sentry.withScope((scope) => {
      if (context) {
        Object.entries(context).forEach(([key, value]) => {
          scope.setExtra(key, value);
        });
      }
      Sentry.captureException(error);
    });
  } catch {
    console.error('[Analytics] Error captured:', error, context);
  }
}

// ── Web Vitals ───────────────────────────────────────────────────

function reportWebVitals() {
  if (!IS_BROWSER) return;
  try {
    const wv = dynamicRequire('web-vitals') as {
      onCLS: (fn: (m: { name: string; value: number; id: string }) => void) => void;
      onFID: (fn: (m: { name: string; value: number; id: string }) => void) => void;
      onFCP: (fn: (m: { name: string; value: number; id: string }) => void) => void;
      onLCP: (fn: (m: { name: string; value: number; id: string }) => void) => void;
      onTTFB: (fn: (m: { name: string; value: number; id: string }) => void) => void;
    };
    const report = (metric: { name: string; value: number; id: string }) => {
      sendToGA4('web_vitals', {
        metric_name: metric.name,
        metric_value: Math.round(metric.value),
        metric_id: metric.id,
      });
    };
    wv.onCLS(report);
    wv.onFID(report);
    wv.onFCP(report);
    wv.onLCP(report);
    wv.onTTFB(report);
  } catch {
    // web-vitals not installed — that's fine
  }
}

// ── Scroll Depth Tracking ────────────────────────────────────────

const scrollMilestones = new Set<number>();

function initScrollTracking() {
  if (!IS_BROWSER) return;
  const milestones = [25, 50, 75, 100];
  const handler = () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;
    const pct = Math.round((scrollTop / docHeight) * 100);
    milestones.forEach((m) => {
      if (pct >= m && !scrollMilestones.has(m)) {
        scrollMilestones.add(m);
        analytics.track('scroll_depth', { depth_percent: m, page: window.location.pathname });
      }
    });
  };
  window.addEventListener('scroll', handler, { passive: true });
  return () => window.removeEventListener('scroll', handler);
}

// ── Time on Page ─────────────────────────────────────────────────

let pageEntryTime = 0;

function startTimeTracking() {
  if (!IS_BROWSER) return;
  pageEntryTime = Date.now();
  const sendTime = () => {
    if (pageEntryTime) {
      const seconds = Math.round((Date.now() - pageEntryTime) / 1000);
      if (seconds > 5) {
        analytics.track('time_on_page', {
          seconds,
          page: window.location.pathname,
        });
      }
    }
  };
  window.addEventListener('beforeunload', sendTime);
  return () => window.removeEventListener('beforeunload', sendTime);
}

// ── E-commerce Helpers ───────────────────────────────────────────

function trackEcommerceEvent(
  action: 'view_item' | 'add_to_cart' | 'begin_checkout' | 'purchase',
  item: {
    item_id: string | number;
    item_name: string;
    price?: number;
    currency?: string;
    category?: string;
    quantity?: number;
  },
  value?: number
) {
  if (!IS_BROWSER || !window.gtag) return;
  window.gtag('event', action, {
    currency: item.currency || 'INR',
    value: value ?? item.price,
    items: [
      {
        item_id: String(item.item_id),
        item_name: item.item_name,
        price: item.price,
        item_category: item.category || 'Hotels',
        quantity: item.quantity || 1,
      },
    ],
  });
}

// ── Public API ───────────────────────────────────────────────────

export const analytics = {
  /**
   * Initialize analytics — call once from layout.tsx useEffect.
   * Safe to call multiple times (idempotent).
   */
  init() {
    if (!IS_BROWSER) return;
    initSentry();
    reportWebVitals();
    initScrollTracking();
    startTimeTracking();
    flushQueue();
  },

  /**
   * Track any named event with optional properties.
   * Fires to GA4, GTM, and logs in dev.
   */
  track(name: EventName, properties: EventProperties = {}) {
    if (!IS_BROWSER) return;

    const enrichedProps = {
      ...properties,
      page_path: window.location.pathname,
      page_url: window.location.href,
      timestamp: new Date().toISOString(),
    };

    if (!IS_PRODUCTION) {
      console.debug(`[Analytics] ${name}`, enrichedProps);
    }

    // If GA/GTM not loaded yet, queue event
    if (!window.gtag && !window.dataLayer) {
      if (eventQueue.length < MAX_QUEUE_SIZE) {
        eventQueue.push({ name, properties: enrichedProps, timestamp: Date.now() });
      }
      return;
    }

    sendToGA4(name, enrichedProps);
    sendToGTM(name, enrichedProps);
  },

  /**
   * Track page view — called from route change handler.
   */
  pageView(path: string, title?: string) {
    if (!IS_BROWSER) return;
    scrollMilestones.clear();
    pageEntryTime = Date.now();
    sendToGA4('page_view', { page_path: path, page_title: title || document.title });
    sendToGTM('page_view', { page_path: path, page_title: title || document.title });
  },

  /**
   * Track GA4 e-commerce events (view_item, add_to_cart, begin_checkout, purchase).
   */
  ecommerce: trackEcommerceEvent,

  /**
   * Report errors to Sentry + track as analytics event.
   */
  captureError(error: Error, context?: Record<string, unknown>) {
    captureException(error, context);
    analytics.track('api_error', {
      error_name: error.name,
      error_message: error.message.slice(0, 200),
      ...Object.fromEntries(
        Object.entries(context || {}).map(([k, v]) => [k, String(v)])
      ),
    });
  },

  /**
   * GA4 Measurement ID and GTM Container ID getters for Script tags.
   */
  GA_MEASUREMENT_ID,
  GTM_CONTAINER_ID,
};

export default analytics;


// ── Booking Funnel Tracker ───────────────────────────────────────

/**
 * Tracks the booking conversion funnel from search → payment.
 *
 * Funnel stages:
 *  1. search_results_shown  — search results page loaded
 *  2. hotel_page_viewed     — user clicked a hotel card
 *  3. room_selected         — user selected a room type
 *  4. booking_started       — user initiated checkout
 *  5. payment_initiated     — user started payment
 *  6. booking_completed     — payment confirmed
 *
 * Usage:
 *   import { bookingFunnel } from '@/lib/analytics';
 *   bookingFunnel.enter('search_results_shown', { city: 'Goa', results: 42 });
 *   bookingFunnel.enter('hotel_page_viewed', { hotelId: 123 });
 */

type FunnelStage =
  | 'search_results_shown'
  | 'hotel_page_viewed'
  | 'room_selected'
  | 'booking_started'
  | 'payment_initiated'
  | 'booking_completed';

const FUNNEL_ORDER: FunnelStage[] = [
  'search_results_shown',
  'hotel_page_viewed',
  'room_selected',
  'booking_started',
  'payment_initiated',
  'booking_completed',
];

const SESSION_KEY = 'zygo_funnel_session';

interface FunnelSession {
  sessionId: string;
  stages: { stage: FunnelStage; timestamp: number; props?: EventProperties }[];
  startedAt: number;
}

function getFunnelSession(): FunnelSession {
  if (!IS_BROWSER) {
    return { sessionId: '', stages: [], startedAt: 0 };
  }
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  const session: FunnelSession = {
    sessionId: `fs_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    stages: [],
    startedAt: Date.now(),
  };
  if (IS_BROWSER) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

function saveFunnelSession(session: FunnelSession) {
  if (!IS_BROWSER) return;
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch {}
}

export const bookingFunnel = {
  /**
   * Record entry into a funnel stage.
   * Automatically tracks progression, drop-offs, and time between stages.
   */
  enter(stage: FunnelStage, properties: EventProperties = {}) {
    if (!IS_BROWSER) return;

    const session = getFunnelSession();
    const stageIndex = FUNNEL_ORDER.indexOf(stage);
    const lastStage = session.stages[session.stages.length - 1];
    const lastIndex = lastStage ? FUNNEL_ORDER.indexOf(lastStage.stage) : -1;

    // Reset session if going backwards (new funnel)
    if (stageIndex <= lastIndex && stageIndex === 0) {
      session.stages = [];
    }

    const entry = {
      stage,
      timestamp: Date.now(),
      props: properties,
    };
    session.stages.push(entry);
    saveFunnelSession(session);

    // Time since last stage
    const timeSinceLast = lastStage
      ? Math.round((Date.now() - lastStage.timestamp) / 1000)
      : 0;

    // Track to analytics
    analytics.track(stage === 'search_results_shown' ? 'search_submitted' : stage as EventName, {
      ...properties,
      funnel_session_id: session.sessionId,
      funnel_stage_index: stageIndex,
      funnel_time_since_last_stage: timeSinceLast,
      funnel_total_time: Math.round((Date.now() - session.startedAt) / 1000),
    });

    // Send funnel progression to backend for aggregation
    if (IS_PRODUCTION) {
      try {
        const payload = {
          session_id: session.sessionId,
          stage,
          stage_index: stageIndex,
          time_since_last: timeSinceLast,
          properties,
        };
        navigator.sendBeacon?.('/api/v1/analytics/funnel/track/', JSON.stringify(payload));
      } catch {}
    }
  },

  /**
   * Get the current funnel session summary (for debugging / display).
   */
  getSummary() {
    const session = getFunnelSession();
    return {
      sessionId: session.sessionId,
      stagesReached: session.stages.map(s => s.stage),
      totalTime: session.stages.length > 0
        ? Math.round((Date.now() - session.startedAt) / 1000)
        : 0,
      completed: session.stages.some(s => s.stage === 'booking_completed'),
    };
  },

  /**
   * Explicitly reset the funnel (e.g. after booking completion).
   */
  reset() {
    if (IS_BROWSER) sessionStorage.removeItem(SESSION_KEY);
  },
};
