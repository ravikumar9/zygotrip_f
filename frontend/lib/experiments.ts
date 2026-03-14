/**
 * ZygoTrip A/B Testing & Feature Flag Framework.
 *
 * Supports:
 *  - Cookie-based experiment assignment (persistent across sessions)
 *  - Multiple concurrent experiments
 *  - Variant weights (traffic allocation)
 *  - Analytics integration (auto-tracks experiment_assigned events)
 *  - Server-safe (no-ops during SSR)
 *
 * Usage:
 *   import { experiments, useExperiment } from '@/lib/experiments';
 *
 *   // In a component:
 *   const variant = useExperiment('hero_cta_test');
 *   if (variant === 'green_button') { ... }
 */

import { analytics } from '@/lib/analytics';

// ── Types ────────────────────────────────────────────────────────

export interface ExperimentConfig {
  /** Unique experiment identifier */
  id: string;
  /** Human-readable name */
  name: string;
  /** Variant definitions with traffic weights (must sum to 100) */
  variants: Array<{
    id: string;
    weight: number; // percentage: 0–100
  }>;
  /** Whether the experiment is active */
  active: boolean;
  /** Optional: percentage of total traffic to include (0–100) */
  trafficAllocation?: number;
}

// ── Experiment Registry ──────────────────────────────────────────
// Add new experiments here. Deactivate old ones by setting active: false.

export const EXPERIMENT_REGISTRY: ExperimentConfig[] = [
  {
    id: 'hero_search_layout',
    name: 'Hero Search Bar Layout Test',
    variants: [
      { id: 'control', weight: 50 },
      { id: 'tabs_visible', weight: 50 },
    ],
    active: true,
    trafficAllocation: 100,
  },
  {
    id: 'hotel_card_cta',
    name: 'Hotel Card CTA Button Text',
    variants: [
      { id: 'view_details', weight: 34 },
      { id: 'book_now', weight: 33 },
      { id: 'check_price', weight: 33 },
    ],
    active: true,
    trafficAllocation: 100,
  },
  {
    id: 'listing_infinite_scroll',
    name: 'Infinite Scroll vs Pagination',
    variants: [
      { id: 'infinite', weight: 80 },
      { id: 'paginated', weight: 20 },
    ],
    active: true,
    trafficAllocation: 100,
  },
  {
    id: 'pricing_display',
    name: 'Pricing Display Format',
    variants: [
      { id: 'per_night', weight: 50 },
      { id: 'total_stay', weight: 50 },
    ],
    active: false, // Not yet launched
    trafficAllocation: 100,
  },
];

// ── Cookie Helpers ───────────────────────────────────────────────

const COOKIE_PREFIX = 'zygo_exp_';
const IS_BROWSER = typeof window !== 'undefined';

function getCookie(name: string): string | null {
  if (!IS_BROWSER) return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function setCookie(name: string, value: string, days: number = 30) {
  if (!IS_BROWSER) return;
  const expires = new Date(Date.now() + days * 86400000).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires};path=/;SameSite=Lax`;
}

// ── Assignment Logic ─────────────────────────────────────────────

/**
 * Deterministic assignment based on a random number and variant weights.
 */
function assignVariant(config: ExperimentConfig): string {
  const rand = Math.random() * 100;
  let cumulative = 0;
  for (const variant of config.variants) {
    cumulative += variant.weight;
    if (rand < cumulative) return variant.id;
  }
  return config.variants[config.variants.length - 1].id;
}

/**
 * Get (or create) the variant assignment for an experiment.
 * Persistent via cookies — same user sees same variant.
 */
function getAssignment(experimentId: string): string | null {
  const config = EXPERIMENT_REGISTRY.find((e) => e.id === experimentId);
  if (!config || !config.active) return null;

  const cookieKey = `${COOKIE_PREFIX}${experimentId}`;
  const existing = getCookie(cookieKey);
  if (existing) {
    // Validate it's still a valid variant
    if (config.variants.some((v) => v.id === existing)) return existing;
  }

  // Check traffic allocation
  if (config.trafficAllocation && config.trafficAllocation < 100) {
    if (Math.random() * 100 >= config.trafficAllocation) {
      setCookie(cookieKey, '__excluded');
      return null;
    }
  }

  // Assign new variant
  const variant = assignVariant(config);
  setCookie(cookieKey, variant);

  // Track assignment
  analytics.track('experiment_assigned', {
    experiment_id: experimentId,
    experiment_name: config.name,
    variant_id: variant,
  });

  return variant;
}

// ── Public API ───────────────────────────────────────────────────

export const experiments = {
  /**
   * Get variant for an experiment. Returns variant ID or null if excluded/inactive.
   */
  getVariant(experimentId: string): string | null {
    return getAssignment(experimentId);
  },

  /**
   * Check if a specific variant is assigned.
   */
  isVariant(experimentId: string, variantId: string): boolean {
    return getAssignment(experimentId) === variantId;
  },

  /**
   * Get all active experiment assignments for the current user.
   */
  getAllAssignments(): Record<string, string | null> {
    const result: Record<string, string | null> = {};
    for (const config of EXPERIMENT_REGISTRY) {
      if (config.active) {
        result[config.id] = getAssignment(config.id);
      }
    }
    return result;
  },

  /**
   * Force a specific variant (for testing/QA).
   * Set via URL param: ?exp_hero_search_layout=tabs_visible
   */
  applyOverrides() {
    if (!IS_BROWSER) return;
    const params = new URLSearchParams(window.location.search);
    for (const config of EXPERIMENT_REGISTRY) {
      const override = params.get(`exp_${config.id}`);
      if (override && config.variants.some((v) => v.id === override)) {
        setCookie(`${COOKIE_PREFIX}${config.id}`, override);
      }
    }
  },

  /** Experiment registry for external access */
  registry: EXPERIMENT_REGISTRY,
};

// ── React Hook ───────────────────────────────────────────────────

/**
 * React hook to get the current variant for an experiment.
 * Returns null if experiment is inactive or user is excluded.
 *
 * Usage:
 *   const variant = useExperiment('hero_search_layout');
 */
export function useExperiment(experimentId: string): string | null {
  // Note: This is intentionally not using useState/useEffect
  // because experiment assignment is cookie-based and stable.
  // Re-renders won't change the assignment.
  if (!IS_BROWSER) return null;
  return getAssignment(experimentId);
}

export default experiments;
