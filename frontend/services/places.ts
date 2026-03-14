/**
 * Places API client — Google Places + local DB hybrid.
 *
 * Endpoints:
 *   GET /api/v1/places/autocomplete/?q=...&types=...&lang=en
 *   GET /api/v1/places/details/?place_id=ChIJ...
 *   GET /api/v1/places/geocode/?address=...
 *   GET /api/v1/geo-search/?q=...&radius=5&sort=distance
 *   GET /api/v1/geo-search/nearby/?lat=...&lng=...&radius=5
 *   GET /api/v1/route/calculate/?from=...&to=...
 */

import apiClient from './apiClient';

// ── Places ──────────────────────────────────────────────────────────────

export interface PlacesSuggestion {
  place_id: string;
  label: string;
  sublabel: string;
  description: string;
  type: string;
  source: 'google' | 'local';
  id?: number | string;
  slug?: string;
}

export interface PlaceDetails {
  latitude: number;
  longitude: number;
  city: string;
  state: string;
  country: string;
  country_code: string;
  place_id: string;
  formatted_address?: string;
  types?: string[];
}

export async function fetchPlacesAutocomplete(
  query: string,
  options?: { types?: string; lang?: string; components?: string; session_token?: string },
): Promise<PlacesSuggestion[]> {
  if (!query || query.length < 2) return [];
  try {
    const { data } = await apiClient.get('/places/autocomplete/', {
      params: { q: query, ...options },
      signal: AbortSignal.timeout(3000),
    });
    return data?.results ?? [];
  } catch {
    return [];
  }
}

export async function fetchPlaceDetails(
  placeId: string,
  sessionToken?: string,
): Promise<PlaceDetails | null> {
  try {
    const { data } = await apiClient.get('/places/details/', {
      params: { place_id: placeId, session_token: sessionToken },
    });
    return data?.result ?? null;
  } catch {
    return null;
  }
}

export async function geocodeAddress(address: string): Promise<PlaceDetails | null> {
  try {
    const { data } = await apiClient.get('/places/geocode/', {
      params: { address },
    });
    return data?.result ?? null;
  } catch {
    return null;
  }
}

export async function reverseGeocode(lat: number, lng: number): Promise<PlaceDetails | null> {
  try {
    const { data } = await apiClient.get('/places/geocode/', {
      params: { lat, lng },
    });
    return data?.result ?? null;
  } catch {
    return null;
  }
}

// ── Geo Search ──────────────────────────────────────────────────────────

export interface GeoSearchResult {
  id: number;
  name: string;
  city: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  base_price: number;
  rating: number;
  review_count: number;
  property_type: string;
  star_rating: number;
  ranking_score?: number;
}

export interface GeoSearchResponse {
  query: string;
  resolved_location: PlaceDetails | null;
  results: GeoSearchResult[];
  total: number;
  radius_km: number;
  sort_by: string;
}

export interface GeoSearchFilters {
  min_price?: number;
  max_price?: number;
  star_rating?: number;
  property_type?: string;
}

export async function geoSearch(
  query: string,
  options?: { radius?: number; sort?: string; limit?: number; filters?: GeoSearchFilters },
): Promise<GeoSearchResponse | null> {
  try {
    const { data } = await apiClient.get('/geo-search/', {
      params: {
        q: query,
        radius: options?.radius,
        sort: options?.sort,
        limit: options?.limit,
        ...options?.filters,
      },
    });
    return data;
  } catch {
    return null;
  }
}

export async function geoSearchNearby(
  lat: number,
  lng: number,
  options?: { radius?: number; sort?: string; limit?: number; filters?: GeoSearchFilters },
): Promise<GeoSearchResponse | null> {
  try {
    const { data } = await apiClient.get('/geo-search/nearby/', {
      params: {
        lat,
        lng,
        radius: options?.radius,
        sort: options?.sort,
        limit: options?.limit,
        ...options?.filters,
      },
    });
    return data;
  } catch {
    return null;
  }
}

// ── Route ───────────────────────────────────────────────────────────────

export interface RouteResult {
  distance_km: number;
  duration_minutes: number;
  eta: string;
  estimated_toll: number;
  fare_estimate: {
    base_fare: number;
    distance_fare: number;
    platform_margin: number;
    total_fare: number;
  };
  source: string;
  cached: boolean;
}

export async function calculateRoute(
  from: string,
  to: string,
  vehicle?: string,
): Promise<RouteResult | null> {
  try {
    const { data } = await apiClient.get('/route/calculate/', {
      params: { from, to, vehicle },
    });
    return data?.route ?? null;
  } catch {
    return null;
  }
}
