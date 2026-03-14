import api from './api';
import type { BookingContext, BookingDetail, BookingSummary } from '@/types';

/** Unwrap both {success,data} envelope and raw responses */
function unwrap<T>(data: unknown): T {
  if (data && typeof data === 'object' && 'success' in data) {
    const d = data as { success: boolean; data: T; error?: { message: string } };
    if (!d.success) throw new Error(String(d.error?.message ?? 'API error'));
    return d.data;
  }
  return data as T;
}

export const bookingsService = {
  /**
   * Create a booking context (price-lock step before payment).
   *
   * Canonical field names per API contract:
   *   property_id   — not property
   *   room_type_id  — not room_type
   *   checkin       — not check_in
   *   checkout      — not check_out
   *   adults        — not guests
   */
  async createContext(payload: {
    property_id: number;
    room_type_id: number;
    checkin: string;
    checkout: string;
    rooms: number;
    adults: number;
    meal_plan?: string;
    promo_code?: string;
  }): Promise<BookingContext> {
    const { data } = await api.post('/booking/context/', payload);
    return unwrap<BookingContext>(data);
  },

  /**
   * Retrieve an existing booking context by UUID (canonical) or numeric ID (legacy).
   * All new code should pass a UUID string.
   */
  async getContext(id: string | number): Promise<BookingContext> {
    const { data } = await api.get(`/booking/context/${id}/`);
    return unwrap<BookingContext>(data);
  },

  /**
   * Confirm & pay for a booking using a context.
   *
   * Backend accepts context_uuid (UUID string, preferred) or context_id (int, legacy).
   */
  async confirmBooking(payload: {
    context_uuid?: string;
    context_id?: string | number;
    payment_method: 'wallet' | 'gateway';
    guest_name?: string;
    guest_email?: string;
    guest_phone?: string;
    use_wallet?: boolean;
    idempotency_key?: string;
  }): Promise<BookingDetail> {
    const { data } = await api.post('/booking/', payload);
    return unwrap<BookingDetail>(data);
  },

  /**
   * Apply a promo code and get the updated price breakdown.
   * Frontend must NEVER calculate discounts locally — use this endpoint.
   */
  async applyPromo(payload: {
    promo_code: string;
    base_amount: number | string;
    meal_amount?: number | string;
    context_uuid?: string;
  }): Promise<{
    valid: boolean;
    promo_code?: string;
    discount_amount?: string;
    updated_breakdown?: {
      base_amount: string; meal_amount: string; service_fee: string;
      gst_percentage: string; gst_amount: string; promo_discount: string;
      total_amount: string;
    };
    new_total?: string;
  }> {
    const { data } = await api.post('/promo/apply/', payload);
    return unwrap(data);
  },

  /**
   * Apply (or remove) a promo code on an existing BookingContext.
   * The backend recalculates service_fee, tax, final_price, locked_price.
   * Send promo_code="" to remove a previously applied promo.
   */
  async applyPromoToContext(contextUuid: string, promoCode: string): Promise<BookingContext> {
    const { data } = await api.post(`/booking/context/${contextUuid}/apply-promo/`, { promo_code: promoCode });
    return unwrap<BookingContext>(data);
  },

  /** Fetch the current user's bookings */
  async getMyBookings(page = 1): Promise<{ results: BookingSummary[]; count: number }> {
    const { data } = await api.get('/booking/my/', { params: { page } });
    return unwrap<{ results: BookingSummary[]; count: number }>(data);
  },

  /** Fetch a single booking by UUID */
  async getBooking(uuid: string): Promise<BookingDetail> {
    const { data } = await api.get(`/booking/${uuid}/`);
    return unwrap<BookingDetail>(data);
  },

  /** Cancel a booking */
  async cancelBooking(uuid: string, reason?: string): Promise<{ message: string }> {
    const { data } = await api.post(`/booking/${uuid}/cancel/`, { reason });
    return unwrap<{ message: string }>(data);
  },
};
