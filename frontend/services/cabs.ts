/**
 * cabs.ts — Frontend service for Cab search & booking APIs.
 * Calls /api/v1/cabs/* via the public apiClient (Next.js proxy → Django).
 */

import apiClient from './apiClient';
import type {
  Cab, CabSearchParams, CabSearchResult, CityOption,
} from '@/types/cabs';

// ── Search ────────────────────────────────────────────────────────────────

export async function searchCabs(params: CabSearchParams): Promise<CabSearchResult> {
  const { data } = await apiClient.get('/cabs/search/', { params });
  return data?.data ?? data;
}

// ── Detail ────────────────────────────────────────────────────────────────

export async function getCabDetail(cabId: number): Promise<Cab> {
  const { data } = await apiClient.get(`/cabs/${cabId}/`);
  return data?.data ?? data;
}

// ── Availability ──────────────────────────────────────────────────────────

export async function getCabAvailability(
  cabId: number,
  month?: string
): Promise<Array<{ date: string; is_available: boolean }>> {
  const { data } = await apiClient.get(`/cabs/${cabId}/availability/`, {
    params: month ? { month } : undefined,
  });
  return data?.data ?? data;
}

// ── Cities ────────────────────────────────────────────────────────────────

export async function getAvailableCities(): Promise<CityOption[]> {
  const { data } = await apiClient.get('/cabs/cities/');
  return data?.data ?? data;
}
