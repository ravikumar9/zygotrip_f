/**
 * Axios instance with JWT auth interceptors + retry with exponential backoff.
 * Tokens are stored in memory (access) and localStorage (refresh).
 * On 401, attempts token refresh before retrying.
 * On network/5xx errors, retries up to 3 times with exponential backoff.
 *
 * Phase 3: Uses relative URL '/api/v1' to go through the Next.js proxy,
 * eliminating all CORS issues. The proxy rewrites /api/* → Django backend.
 * For SSR/server-side, falls back to BACKEND_URL for direct access.
 */
import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

// Phase 3: Relative URL routes through the Next.js rewrite proxy (no CORS).
// Server-side (SSR) needs the absolute URL since there's no browser proxy.
const API_BASE =
  typeof window === 'undefined'
    ? `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/v1`
    : (process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1');

// In-memory token storage (avoids XSS via localStorage for access tokens)
let accessToken: string | null = null;

export const tokenStore = {
  getAccess: () => accessToken,
  setAccess: (token: string) => { accessToken = token; },
  getRefresh: () => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('zygotrip_refresh');
  },
  setRefresh: (token: string) => {
    if (typeof window !== 'undefined') localStorage.setItem('zygotrip_refresh', token);
  },
  clear: () => {
    accessToken = null;
    if (typeof window !== 'undefined') localStorage.removeItem('zygotrip_refresh');
  },
};

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
});

// Request interceptor — attach Bearer token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 token refresh
let isRefreshing = false;
let failedQueue: Array<{ resolve: (value: string) => void; reject: (err: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token as string);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = tokenStore.getRefresh();
      if (!refreshToken) {
        tokenStore.clear();
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const response = await axios.post(`${API_BASE}/auth/token/refresh/`, { refresh: refreshToken });
        const newToken = response.data.access;
        tokenStore.setAccess(newToken);
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        const _re = refreshError as any;
        if (_re?.response?.status === 401 || _re?.response?.status === 400) {
          tokenStore.clear();
          if (typeof window !== "undefined" && !window.location.pathname.includes("checkout") && !window.location.pathname.includes("payment")) {
            setTimeout(() => { window.location.href = "/account/login?session_expired=1"; }, 100);
          }
        }
        // tokenStore.clear() moved above
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── Retry interceptor — exponential backoff for network/5xx errors ──

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY = 1000; // 1s base, then 2s, 4s

function isRetryableError(error: AxiosError): boolean {
  // Network errors (no response)
  if (!error.response) return true;
  // Server errors (5xx)
  if (error.response.status >= 500) return true;
  // Rate limiting (429)
  if (error.response.status === 429) return true;
  return false;
}

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig & { _retryCount?: number; _retry?: boolean };
    if (!config) return Promise.reject(error);

    // Skip retry for auth-related failures (handled by refresh logic above)
    if (error.response?.status === 401) return Promise.reject(error);

    const retryCount = config._retryCount || 0;
    if (retryCount >= MAX_RETRIES || !isRetryableError(error)) {
      return Promise.reject(error);
    }

    config._retryCount = retryCount + 1;
    const delay = RETRY_BASE_DELAY * Math.pow(2, retryCount) + Math.random() * 500;

    await new Promise((resolve) => setTimeout(resolve, delay));
    return api(config);
  }
);

export default api;
