/**
 * apiClient — lightweight PUBLIC Axios instance.
 *
 * Phase 3 API Contract:
 *   Browser: baseURL = '/api/v1' (routed through Next.js rewrite proxy → Django)
 *   Server:  baseURL = BACKEND_URL/api/v1 (direct connection)
 *
 * Using the Next.js proxy eliminates all CORS issues.
 *
 * For authenticated requests use the default `api` export from ./api
 * which adds Authorization: Bearer headers automatically.
 */

import axios from 'axios';

// Phase 3: Relative URL for browser (proxy), absolute for SSR.
const BASE_URL =
  typeof window === 'undefined'
    ? `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/v1`
    : (process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1');

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 12000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
});

// Simple response error logger — no retry logic (use api.ts for that)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (process.env.NODE_ENV === 'development') {
      const url    = error?.config?.url ?? '';
      const status = error?.response?.status ?? 'network-error';
      console.warn(`[apiClient] ${status} ${url}`);
    }
    return Promise.reject(error);
  },
);

export default apiClient;

// ── Typed helper wrappers ─────────────────────────────────────────────────────

/** GET /autosuggest/?q=…&limit=… */
export async function fetchAutosuggest(
  query: string,
  limit = 8,
): Promise<Array<{
  type:      'city' | 'area' | 'property' | 'bus_city' | 'cab_city' | 'landmark';
  label:     string;
  sublabel?: string;
  count?:    number;
  slug?:     string;
  id?:       number | string | null;
  place_id?: string;
  source?:   'local' | 'google';
}>> {
  if (!query || query.length < 2) return [];
  try {
    const { data } = await apiClient.get('/autosuggest/', {
      params: { q: query, limit },
      signal: AbortSignal.timeout(3000),
    });
    // Handle both raw array and {success, results} envelope
    if (Array.isArray(data))          return data;
    if (Array.isArray(data?.results)) return data.results;
    return [];
  } catch {
    return [];
  }
}

/** GET /hotels/aggregations/ */
export async function fetchAggregations(): Promise<{
  cities: Array<{ name: string; count: number; slug: string }>;
  areas:  Array<{ name: string; city: string; count: number }>;
  total:  number;
}> {
  try {
    const { data } = await apiClient.get('/hotels/aggregations/');
    if (data?.success) return data.data;
    return { cities: [], areas: [], total: 0 };
  } catch {
    return { cities: [], areas: [], total: 0 };
  }
}
