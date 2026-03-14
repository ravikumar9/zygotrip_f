import api, { tokenStore } from './api';
import type { ApiResponse, AuthData, User } from '@/types';

export async function login(email: string, password: string): Promise<AuthData> {
  const { data } = await api.post<ApiResponse<AuthData>>('/auth/login/', { email, password });
  if (!data.success) throw new Error('Login failed');
  tokenStore.setAccess(data.data.tokens.access);
  tokenStore.setRefresh(data.data.tokens.refresh);
  return data.data;
}

export async function register(
  full_name: string,
  email: string,
  password: string,
  role: string = 'traveler',
  phone?: string,
): Promise<AuthData> {
  const payload = { full_name, email, password, role, ...(phone ? { phone } : {}) };
  const { data } = await api.post<ApiResponse<AuthData>>('/auth/register/', payload);
  if (!data.success) throw new Error('Registration failed');
  tokenStore.setAccess(data.data.tokens.access);
  tokenStore.setRefresh(data.data.tokens.refresh);
  return data.data;
}

export async function logout(): Promise<void> {
  const refresh = tokenStore.getRefresh();
  if (refresh) {
    try {
      await api.post('/auth/logout/', { refresh });
    } catch {
      // Ignore logout errors — clear locally regardless
    }
  }
  tokenStore.clear();
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await api.get<ApiResponse<User>>('/users/me/');
  if (!data.success) throw new Error('Could not fetch user');
  return data.data;
}

export async function updateProfile(payload: { full_name?: string; phone?: string }): Promise<User> {
  const { data } = await api.patch<ApiResponse<User>>('/users/me/', payload);
  if (!data.success) throw new Error('Update failed');
  return data.data;
}

// ── OTP Authentication ──────────────────────────────────────

export interface OtpSendResponse {
  message: string;
  expires_in_seconds: number;
  phone: string;
}

export interface OtpVerifyResponse extends AuthData {
  is_new_user: boolean;
}

export async function sendOtp(phone: string, purpose: 'login' | 'verify' = 'login'): Promise<OtpSendResponse> {
  const { data } = await api.post<ApiResponse<OtpSendResponse>>('/auth/otp/send/', { phone, purpose });
  if (!data.success) throw new Error('Failed to send OTP');
  return data.data;
}

export async function verifyOtp(phone: string, code: string, full_name?: string): Promise<OtpVerifyResponse> {
  const payload: Record<string, string> = { phone, code };
  if (full_name) payload.full_name = full_name;
  const { data } = await api.post<ApiResponse<OtpVerifyResponse>>('/auth/otp/verify/', payload);
  if (!data.success) throw new Error('OTP verification failed');
  tokenStore.setAccess(data.data.tokens.access);
  tokenStore.setRefresh(data.data.tokens.refresh);
  return data.data;
}
