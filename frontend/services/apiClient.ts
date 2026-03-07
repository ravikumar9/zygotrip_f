/**
 * apiClient — lightweight PUBLIC Axios instance.
 *
 * Phase 2 API Contract:
 *   baseURL = NEXT_PUBLIC_API_BASE_URL env var (absolute URL)
 *   Default: http://127.0.0.1:8000/api/v1
 *
 * Django CORS is configured to allow http://localhost:3000.
 * All requests go directly to the Django backend — no Next.js proxy needed.
 *
 * For authenticated requests use the default `api` export from ./api
 * which adds Authorization: Bearer headers automatically.
 */

import axios from 'axios';

// Phase 2: Read from env var — NEVER hardcode the URL.
// NEXT_PUBLIC_ prefix exposes it to the browser bundle.
const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://127.0.0.1:8000/api/v1';

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
  type:      'city' | 'area' | 'property';
  label:     string;
  sublabel?: string;
  count?:    number;
  slug?:     string;
  id?:       number | string | null;
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
