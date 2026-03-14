/**
 * ZygoTrip Personalization Engine.
 *
 * Tracks:
 *  - Recently viewed hotels (localStorage, max 10)
 *  - Search history (localStorage, for recommendation signals)
 *  - Returning user detection
 *
 * All functions are SSR-safe (no-op on server).
 *
 * Usage:
 *   import { personalization } from '@/lib/personalization';
 *   personalization.trackView({ id: 123, name: 'Taj Palace', ... });
 *   const recent = personalization.getRecentlyViewed();
 */

const IS_BROWSER = typeof window !== 'undefined';

// ── Storage Keys ─────────────────────────────────────────────────

const RECENTLY_VIEWED_KEY = 'zygo_recently_viewed';
const SEARCH_HISTORY_KEY  = 'zygo_search_history';
const FIRST_VISIT_KEY     = 'zygo_first_visit';
const VISIT_COUNT_KEY     = 'zygo_visit_count';

const MAX_RECENTLY_VIEWED = 10;
const MAX_SEARCH_HISTORY  = 20;

// ── Types ────────────────────────────────────────────────────────

export interface RecentlyViewedHotel {
  id: number;
  name: string;
  slug: string;
  city: string;
  image?: string;
  price?: number;
  rating?: number;
  stars?: number;
  viewedAt: number; // timestamp
}

export interface SearchHistoryEntry {
  location: string;
  checkin?: string;
  checkout?: string;
  guests?: number;
  timestamp: number;
}

export interface UserProfile {
  isReturning: boolean;
  visitCount: number;
  firstVisit: string | null;
  topDestinations: string[];      // from search history
  pricePreference: 'budget' | 'mid' | 'luxury' | null;
  recentlyViewedCount: number;
}

// ── Storage Helpers ──────────────────────────────────────────────

function getJSON<T>(key: string, fallback: T): T {
  if (!IS_BROWSER) return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function setJSON(key: string, value: unknown) {
  if (!IS_BROWSER) return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage full — clear oldest entries
  }
}

// ── Price Category ───────────────────────────────────────────────

function inferPricePreference(
  hotels: RecentlyViewedHotel[]
): 'budget' | 'mid' | 'luxury' | null {
  const prices = hotels.filter((h) => h.price).map((h) => h.price!);
  if (prices.length < 2) return null;
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  if (avg < 2000) return 'budget';
  if (avg < 6000) return 'mid';
  return 'luxury';
}

// ── Visit Tracking ───────────────────────────────────────────────

function trackVisit() {
  if (!IS_BROWSER) return;
  const now = new Date().toISOString();
  if (!localStorage.getItem(FIRST_VISIT_KEY)) {
    localStorage.setItem(FIRST_VISIT_KEY, now);
  }
  const count = parseInt(localStorage.getItem(VISIT_COUNT_KEY) || '0', 10);
  localStorage.setItem(VISIT_COUNT_KEY, String(count + 1));
}

// ── Public API ───────────────────────────────────────────────────

export const personalization = {
  /**
   * Initialize — call once from app mount. Tracks visit count.
   */
  init() {
    trackVisit();
  },

  /**
   * Track a hotel view. Deduplicates by ID, keeps most recent 10.
   */
  trackView(hotel: Omit<RecentlyViewedHotel, 'viewedAt'>) {
    const items = getJSON<RecentlyViewedHotel[]>(RECENTLY_VIEWED_KEY, []);
    const filtered = items.filter((h) => h.id !== hotel.id);
    const entry: RecentlyViewedHotel = { ...hotel, viewedAt: Date.now() };
    setJSON(RECENTLY_VIEWED_KEY, [entry, ...filtered].slice(0, MAX_RECENTLY_VIEWED));
  },

  /**
   * Get recently viewed hotels, newest first.
   */
  getRecentlyViewed(): RecentlyViewedHotel[] {
    return getJSON<RecentlyViewedHotel[]>(RECENTLY_VIEWED_KEY, []);
  },

  /**
   * Clear recently viewed history.
   */
  clearRecentlyViewed() {
    if (IS_BROWSER) localStorage.removeItem(RECENTLY_VIEWED_KEY);
  },

  /**
   * Track a search action.
   */
  trackSearch(entry: Omit<SearchHistoryEntry, 'timestamp'>) {
    const items = getJSON<SearchHistoryEntry[]>(SEARCH_HISTORY_KEY, []);
    const newEntry: SearchHistoryEntry = { ...entry, timestamp: Date.now() };
    // Deduplicate by location
    const filtered = items.filter((h) => h.location !== entry.location);
    setJSON(SEARCH_HISTORY_KEY, [newEntry, ...filtered].slice(0, MAX_SEARCH_HISTORY));
  },

  /**
   * Get search history.
   */
  getSearchHistory(): SearchHistoryEntry[] {
    return getJSON<SearchHistoryEntry[]>(SEARCH_HISTORY_KEY, []);
  },

  /**
   * Build a user profile for personalization decisions.
   */
  getUserProfile(): UserProfile {
    const visitCount = IS_BROWSER
      ? parseInt(localStorage.getItem(VISIT_COUNT_KEY) || '0', 10)
      : 0;
    const firstVisit = IS_BROWSER ? localStorage.getItem(FIRST_VISIT_KEY) : null;
    const recentlyViewed = personalization.getRecentlyViewed();
    const searchHistory = personalization.getSearchHistory();

    // Top destinations from search history
    const destCounts: Record<string, number> = {};
    searchHistory.forEach((s) => {
      if (s.location) destCounts[s.location] = (destCounts[s.location] || 0) + 1;
    });
    const topDestinations = Object.entries(destCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([loc]) => loc);

    return {
      isReturning: visitCount > 1,
      visitCount,
      firstVisit,
      topDestinations,
      pricePreference: inferPricePreference(recentlyViewed),
      recentlyViewedCount: recentlyViewed.length,
    };
  },

  /**
   * Get recommended destinations based on user history.
   * Falls back to popular destinations if no history.
   */
  getRecommendedDestinations(): string[] {
    const profile = personalization.getUserProfile();
    if (profile.topDestinations.length > 0) {
      return profile.topDestinations;
    }
    // Default popular destinations
    return ['Goa', 'Jaipur', 'Manali', 'Mumbai', 'Bangalore'];
  },
};

export default personalization;
