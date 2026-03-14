/**
 * Checkout Domain Types — Matches Django checkout API response schema.
 */

// ---- Request Types ----

export interface CheckoutStartRequest {
  property_id: number;
  room_type_id: number;
  check_in: string;        // YYYY-MM-DD
  check_out: string;       // YYYY-MM-DD
  guests?: number;
  rooms?: number;
  rate_plan_id?: string;
  meal_plan_code?: string;
  promo_code?: string;
  device_fingerprint?: string;
  device_type?: string;
  traffic_source?: string;
}

export interface CheckoutGuestDetails {
  name: string;
  email: string;
  phone: string;
  special_requests?: string;
}

export interface CheckoutPayRequest {
  gateway: 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi' | 'dev_simulate';
  idempotency_key?: string;
}

// ---- Response Types ----

export interface CheckoutPriceSnapshot {
  base_price: string;
  meal_amount: string;
  service_fee: string;
  gst: string;
  total: string;
  tariff_per_night: string;
  property_discount: string;
  platform_discount: string;
  demand_adjustment: string;
  advance_modifier: string;
}

export interface CheckoutSearchSnapshot {
  city: string;
  check_in: string;
  check_out: string;
  guests: number;
  rooms: number;
  meal_plan_code: string;
  promo_code: string;
}

export interface CheckoutInventoryToken {
  token_id: string;
  token_status: 'active' | 'payment_pending' | 'converted' | 'expired' | 'released';
  date_start: string;
  date_end: string;
  reserved_rooms: number;
  expires_at: string;
}

export type CheckoutSessionStatus =
  | 'created'
  | 'room_selected'
  | 'guest_details'
  | 'payment_initiated'
  | 'payment_processing'
  | 'completed'
  | 'expired'
  | 'abandoned'
  | 'failed';

export interface CheckoutSession {
  session_id: string;
  session_status: CheckoutSessionStatus;
  expires_at: string;
  property_id: number;
  property_name: string;
  room_type_id: number;
  room_type_name: string;
  search_snapshot: CheckoutSearchSnapshot;
  price_snapshot: CheckoutPriceSnapshot;
  guest_details: CheckoutGuestDetails | Record<string, never>;
  price_revalidated_at: string | null;
  price_changed: boolean;
  inventory_token: CheckoutInventoryToken | null;
  created_at: string;
}

export interface CheckoutPaymentGateway {
  id: string;
  name: string;
  available: boolean;
  description: string;
  balance?: number;
}

export interface CheckoutPaymentOptions {
  session_id: string;
  amount: string;
  currency: string;
  gateways: CheckoutPaymentGateway[];
}

export interface CheckoutPaymentIntent {
  intent_id: string;
  amount: string;
  currency: string;
  original_amount: string;
  price_revalidated: boolean;
  price_delta: string;
  payment_status: string;
  idempotency_key: string;
  created_at: string;
}

export interface CheckoutPaymentAttempt {
  attempt_id: string;
  gateway: string;
  attempt_status: string;
  amount: string;
  failure_reason: string;
  created_at: string;
}

export interface CheckoutBookingConfirmation {
  booking_uuid: string;
  booking_id: string;
  status: string;
  total_amount: string;
  check_in: string;
  check_out: string;
  property_name: string;
  room_type_name: string;
}

export type CheckoutPaymentResult = {
  status: 'completed';
  session: CheckoutSession;
  payment_intent: CheckoutPaymentIntent;
  booking: CheckoutBookingConfirmation;
} | {
  status: 'pending';
  payment_intent: CheckoutPaymentIntent;
  attempt: CheckoutPaymentAttempt;
  gateway: string;
  next_action: string;
} | {
  status: 'failed';
  error: string;
  can_retry: boolean;
};
