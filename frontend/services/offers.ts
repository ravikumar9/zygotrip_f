import apiClient from './apiClient';

export interface FeaturedOffer {
  id: number;
  title: string;
  description: string;
  offer_type: 'percentage' | 'flat' | 'bogo' | 'bundle';
  coupon_code: string;
  discount_percentage: string;
  discount_flat: string;
  start_datetime: string;
  end_datetime: string;
  is_global: boolean;
}

/**
 * Fetch featured offers from backend — no auth required.
 * GET /api/v1/offers/featured/
 */
export async function fetchFeaturedOffers(): Promise<FeaturedOffer[]> {
  try {
    const { data } = await apiClient.get('/offers/featured/');
    if (data?.success) return data.data;
    return [];
  } catch {
    return [];
  }
}
