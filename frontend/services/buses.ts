/**
 * buses.ts — Frontend service for Bus search & booking APIs.
 * Calls /api/v1/buses/* via the public apiClient (Next.js proxy → Django).
 */

import apiClient from './apiClient';
import type {
  Bus, BusSeat, BusSearchParams, BusSearchResult, BusRoute,
} from '@/types/buses';

// ── Search ────────────────────────────────────────────────────────────────

export async function searchBuses(params: BusSearchParams): Promise<BusSearchResult> {
  const { data } = await apiClient.get('/buses/search/', { params });
  return data?.data ?? data;
}

// ── Detail ────────────────────────────────────────────────────────────────

export async function getBusDetail(busId: number): Promise<Bus & { seat_map: Record<string, BusSeat[]> }> {
  const { data } = await apiClient.get(`/buses/${busId}/`);
  return data?.data ?? data;
}

// ── Seats ─────────────────────────────────────────────────────────────────

export async function getBusSeats(busId: number): Promise<{ seats: BusSeat[]; available_count: number; total_count: number }> {
  const { data } = await apiClient.get(`/buses/${busId}/seats/`);
  return data?.data ?? data;
}

// ── Popular Routes ────────────────────────────────────────────────────────

export async function getPopularRoutes(): Promise<BusRoute[]> {
  const { data } = await apiClient.get('/buses/routes/');
  return data?.data ?? data;
}
