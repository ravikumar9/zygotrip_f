/**
 * Axios instance with JWT auth interceptors.
 * Tokens are stored in memory (access) and localStorage (refresh).
 * On 401, attempts token refresh before retrying.
 *
 * Phase 2: baseURL reads from NEXT_PUBLIC_API_BASE_URL env var.
 * Direct connection to Django — Django CORS allows http://localhost:3000.
 */
import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

// Phase 2: Env-var driven base URL. NEVER hardcode this.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://127.0.0.1:8000/api/v1';

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
        tokenStore.clear();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
