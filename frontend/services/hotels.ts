import api from './api';
import apiClient, { fetchAutosuggest } from './apiClient';
import type {
  ApiResponse, PaginatedData, Property, PropertyDetail,
  AvailabilityData, PricingQuote, HotelSearchParams, PricingIntelligence,
} from '@/types';

// Suppress unused import warning — ApiResponse used in JSDoc / callers
void (null as unknown as ApiResponse<unknown>);

// ── Core Functions ──────────────────────────────────────────────────

export interface FilterCounts {
  free_cancellation?: number;
  breakfast?: number;
  pay_at_hotel?: number;
  trending?: number;
  deals?: number;
  ratings?: Record<string, number>;      // e.g. { rating_5: 10, rating_4plus: 80 }
  user_ratings?: Record<string, number>; // e.g. { rating_4_5plus: 50 }
  property_types?: Record<string, number>;
  amenities?: Record<string, number>;
  cities?: Record<string, number>;
}

export interface PopularArea {
  area: string;
  count: number;
}

export async function listHotels(params: HotelSearchParams = {}): Promise<{
  results: Property[];
  pagination: PaginatedData<Property>['pagination'];
  filter_counts?: FilterCounts;
  popular_areas?: PopularArea[];
  meta?: Record<string, unknown>;
}> {
  const { data } = await api.get('/properties/', { params });
  if (data && 'success' in data) {
    if (!data.success) throw new Error('Failed to fetch hotels');
    // filter_counts, popular_areas and meta sit at the envelope root, not inside data.data
    return {
      ...data.data,
      filter_counts: data.filter_counts,
      popular_areas: data.popular_areas,
      meta: data.meta,
    };
  }
  return data; // fallback for unwrapped responses
}

export async function getHotel(idOrSlug: string | number): Promise<PropertyDetail> {
  const { data } = await api.get(`/properties/${idOrSlug}/`);
  if (data && 'success' in data) {
    if (!data.success) throw new Error('Hotel not found');
    return data.data;
  }
  return data;
}

export const getPropertyDetail = async (
  slug: string,
  checkin?: string,
  checkout?: string,
  rooms?: number,
): Promise<Property> => {
  const params: Record<string, string> = {};
  if (checkin) params.checkin = checkin;
  if (checkout) params.checkout = checkout;
  if (rooms) params.rooms = String(rooms);

  const { data } = await api.get(`/properties/${slug}/`, { params });
  const unwrapped = data && 'success' in data
    ? (data.success ? data.data : null)
    : data;

  if (!unwrapped) {
    throw new Error('Hotel not found');
  }

  return (unwrapped.data ?? unwrapped) as Property;
};

export async function checkAvailability(
  propertyId: number,
  checkin: string,
  checkout: string,
  rooms: number = 1
): Promise<AvailabilityData> {
  const { data } = await api.get(`/properties/${propertyId}/availability/`, {
    params: { checkin, checkout, rooms },
  });
  if (data && 'success' in data) {
    if (!data.success) throw new Error('Availability check failed');
    return data.data;
  }
  return data;
}

export async function getPricingQuote(payload: {
  room_type_id: number;
  nights: number;
  rooms: number;
  promo_code?: string;
}): Promise<PricingQuote> {
  const { data } = await api.post('/pricing/quote/', payload);
  if (data && 'success' in data) {
    if (!data.success) throw new Error('Pricing quote failed');
    return data.data;
  }
  return data;
}

export async function searchHotels(query: string, params: HotelSearchParams = {}): Promise<{
  results: Property[];
  pagination: PaginatedData<Property>['pagination'];
  filter_counts?: FilterCounts;
  popular_areas?: PopularArea[];
}> {
  const { data } = await api.get('/search/', { params: { q: query, ...params } });
  if (data && 'success' in data) {
    if (!data.success) throw new Error('Search failed');
    return {
      ...data.data,
      filter_counts: data.filter_counts,
      popular_areas: data.popular_areas,
    };
  }
  return data;
}

/**
 * Get city/area autocomplete suggestions.
 * Uses the public autosuggest endpoint — no JWT required.
 * Replaced broken raw axios call to non-existent /api/cities/ endpoint.
 */
export async function getCityAutocomplete(q: string): Promise<{
  cities: Array<{ name: string; slug: string; hotel_count: number }>;
}> {
  const suggestions = await fetchAutosuggest(q, 8);
  return {
    cities: suggestions
      .filter((s) => s.type === 'city')
      .map((s) => ({
        name: s.label,
        slug: s.slug ?? '',
        hotel_count: s.count ?? 0,
      })),
  };
}

/**
 * Fetch pricing intelligence (competitor benchmarking) for a property.
 * Calls GET /api/v1/pricing/intelligence/<property_uuid>/
 * Returns null if unavailable (property not approved, no competitor data).
 */
export async function fetchPricingIntelligence(propertyUuid: string): Promise<PricingIntelligence | null> {
  if (!propertyUuid) return null;
  try {
    const { data } = await apiClient.get(`/pricing/intelligence/${propertyUuid}/`);
    if (data?.success) return data.data as PricingIntelligence;
    return null;
  } catch {
    return null;
  }
}

// ── hotelsService compatibility shim ───────────────────────────────
// Referenced by app/hotels/[slug]/page.tsx and app/booking/[propertyId]/page.tsx
// using the older service-object pattern.

export const hotelsService = {
  /** Fetch a property by slug or ID */
  getProperty: (slugOrId: string | number) => getHotel(slugOrId),

  /** List properties with optional search params */
  listProperties: (params: HotelSearchParams) => listHotels(params),

  /** Check availability for a property */
  checkAvailability: (
    propertyId: number,
    checkin: string,
    checkout: string,
    rooms: number = 1
  ) => checkAvailability(propertyId, checkin, checkout, rooms),

  /** Get a pricing quote */
  getPricingQuote: (payload: {
    room_type_id: number;
    nights: number;
    rooms: number;
    promo_code?: string;
  }) => getPricingQuote(payload),
};
