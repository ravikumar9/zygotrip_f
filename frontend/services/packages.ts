/**
 * packages.ts — Frontend service for Holiday-Package APIs.
 * Calls /api/v1/packages/* via the public apiClient (Next.js proxy → Django).
 */

import apiClient from './apiClient';
import type {
  TravelPackage, PackageSearchParams, PackageSearchResult,
  PackageCategory, PackageDestination,
} from '@/types/packages';

// ── Search ────────────────────────────────────────────────────────────────

export async function searchPackages(params: PackageSearchParams): Promise<PackageSearchResult> {
  const { data } = await apiClient.get('/packages/search/', { params });
  return data?.data ?? data;
}

// ── Detail ────────────────────────────────────────────────────────────────

export async function getPackageDetail(slug: string): Promise<TravelPackage> {
  const { data } = await apiClient.get(`/packages/${slug}/`);
  return data?.data ?? data;
}

// ── Popular Destinations ──────────────────────────────────────────────────

export async function getPopularDestinations(): Promise<PackageDestination[]> {
  const { data } = await apiClient.get('/packages/destinations/');
  return data?.data ?? data;
}

// ── Categories ────────────────────────────────────────────────────────────

export async function getPackageCategories(): Promise<PackageCategory[]> {
  const { data } = await apiClient.get('/packages/categories/');
  return data?.data ?? data;
}
