// ============================================================
// ZygoTrip — Core TypeScript Types
// Match the Django backend API response schema exactly.
// ============================================================

// ---- API Envelope ----

export interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string | Record<string, string[]>;
    detail?: unknown;
  };
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface PaginatedData<T> {
  results: T[];
  pagination: {
    count: number;
    total_pages?: number;
    current_page?: number;
    next: string | null;
    previous: string | null;
  };
}

// ---- Auth ----

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: 'traveler' | 'property_owner' | 'cab_owner' | 'bus_operator' | 'package_provider' | 'admin';
  is_verified_vendor: boolean;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthData {
  user: User;
  tokens: AuthTokens;
}

// ---- Property / Hotel ----

export interface PropertyImage {
  id: number;
  url: string;          // resolved URL (uploaded file or image_url)
  caption: string;
  is_featured: boolean;
  display_order: number;
}

export interface PropertyAmenity {
  id?: number;
  name: string;
  icon?: string;
  category?: string;
}

export interface RoomAmenity {
  name: string;
  icon: string;
}

/** Room-level image (distinct from property gallery images) */
export interface RoomImage {
  id: number;
  url: string;          // resolved URL (CDN image_url or uploaded file)
  alt_text: string;
  is_primary: boolean;
  is_featured: boolean;
  display_order: number;
}

export interface RoomMealPlan {
  code: string;
  name: string;
  price_modifier: string;
  description: string;
  is_available: boolean;
  display_order: number;
}

export interface RoomType {
  id: number;
  uuid: string;
  name: string;
  description: string;
  capacity: number;
  max_occupancy: number;
  bed_type: string;
  meal_plan: string;           // legacy single field
  meal_plans: RoomMealPlan[];  // structured meal plan options
  base_price: number;
  available_count: number;
  room_size?: number;                                     // sq ft
  inventory_remaining?: number;                           // live count from RoomInventory
  cancellation_policy?: 'free' | 'non_refundable';
  images?: RoomImage[];                                   // room-specific gallery
  amenities?: RoomAmenity[];                              // room-specific amenities
}

// Pricing object nested inside each RoomAvailability from /availability/
export interface RoomAvailabilityPricing {
  base_price: string;
  property_discount: string;
  platform_discount: string;
  service_fee: string;
  gst: string;
  final_price: string;
  gst_percent: string;
}

// Matches the exact shape returned by GET /api/v1/properties/<id>/availability/
export interface RoomAvailability {
  room_type_id: number;
  uuid: string;
  name: string;
  description: string;
  capacity: number;
  max_occupancy: number;
  max_guests: number;
  bed_type: string;
  meal_plan: string;
  meal_plans: RoomMealPlan[];
  base_price: string;       // Decimal string, e.g. "2500.00"
  available_count: number;
  amenities: RoomAmenity[];
  images: { url: string; alt_text: string; is_primary: boolean }[];
  pricing: RoomAvailabilityPricing;
}

export interface Property {
  id: number;
  uuid?: string;           // UUID for pricing intelligence + API routing
  slug: string;
  name: string;
  property_type: string;
  city_name: string;
  locality_name?: string;
  area: string;
  landmark: string;
  address: string;
  country: string;
  latitude: string;
  longitude: string;
  rating: string;
  review_count: number;
  star_category: number;
  min_price: number;
  rack_rate?: number;       // Original price before discount (for strikethrough)
  primary_image?: string;
  amenity_names?: string[];
  rating_tier: 'excellent' | 'good' | 'average' | 'below_average';
  has_free_cancellation: boolean;
  pay_at_hotel: boolean;         // Phase 4
  is_trending: boolean;
  bookings_today: number;
  recent_bookings?: number;      // Search-index social proof from last 24h
  available_rooms?: number;      // Live inventory count (shown when low)
  cashback_amount?: number;      // Wallet cashback available on this property
  has_breakfast?: boolean;       // True if any room type includes breakfast
  distance_km?: number;          // Distance from search center in km
  discount_badge?: string | null;
  landmark_distance?: string | null;
  trust_badges?: string[];
}

export interface PropertyPolicy {
  id: number;
  title: string;
  description: string;
}

export interface RatingBreakdown {
  cleanliness: string;
  service: string;
  location: string;
  amenities: string;
  value_for_money: string;
  total_reviews: number;
}

export interface PropertyDetail extends Property {
  description: string;
  cancellation_hours: number;
  images: PropertyImage[];
  amenities: PropertyAmenity[];
  room_types: RoomType[];
  check_in_time?: string | null;
  check_out_time?: string | null;
  house_rules?: string | null;
  policies?: PropertyPolicy[];
  rating_breakdown?: RatingBreakdown;
}

// ---- Availability ----

export interface AvailabilityData {
  property_id: number;
  property_name: string;
  checkin: string;
  checkout: string;
  nights: number;
  rooms_requested: number;
  available_room_types: RoomAvailability[];
  total_types_available: number;
}

// ---- Pricing ----

export interface PricingBreakdown {
  base_price: string;
  property_discount: string;
  platform_discount: string;
  service_fee: string;
  gst: string;
  final_price: string;
  gst_percent: string;
}

export interface PricingQuote extends PricingBreakdown {
  room_type_id: number;
  room_type_name: string;
  property_id: number;
  property_name: string;
  nights: number;
  rooms: number;
  coupon_discount: string;
  promo_code_applied: string;
}

// ---- Booking ----

export interface BookingContext {
  id: number;
  uuid: string;  // UUID for all URL routing — numeric id must not appear in URLs
  property_id: number;
  property_name: string;
  property_slug: string;
  room_type_id?: number;
  room_type_name: string;
  checkin: string;
  checkout: string;
  nights: number;
  adults: number;
  children: number;
  rooms: number;
  meal_plan: string;
  base_price: string;
  meal_amount: string;         // total meal add-on from backend
  property_discount: string;
  platform_discount: string;
  promo_discount: string;
  tax: string;
  service_fee: string;
  final_price: string;
  // Price lock fields
  price_locked: boolean;
  locked_price: string;
  price_expires_at: string | null;
  rate_plan_id: string;
  supplier_id: string;
  // Phase 5 additions
  gst_amount: string;          // alias for tax
  gst_percentage: string;      // '5' or '18' per Indian GST slab
  total_price: string;         // alias for final_price
  promo_code: string;
  context_status: 'active' | 'converted' | 'expired' | 'abandoned';
  expires_at: string;
  created_at: string;
}

export interface BookingSummary {
  uuid: string;
  public_booking_id: string;
  property_name: string;
  property_slug: string;
  city_name?: string;
  check_in: string;
  check_out: string;
  nights: number;
  room_count?: number;
  adults?: number;
  status: BookingStatus;
  total_amount: string;
  created_at: string;
}

export type BookingStatus =
  | 'initiated' | 'hold' | 'payment_pending' | 'confirmed'
  | 'checked_in' | 'checked_out' | 'settled'
  | 'cancelled' | 'failed' | 'refund_pending' | 'refunded'
  | 'settlement_pending';

export interface BookingDetail extends BookingSummary {
  gross_amount: string;
  gst_amount: string;
  refund_amount: string;
  settlement_status: string;
  guest_name: string;
  guest_email: string;
  guest_phone: string;
  hold_expires_at: string | null;
  hold_minutes_remaining: number | null;
  rooms: {
    room_type_id: number;
    room_type_name: string;
    quantity: number;
  }[];
  price_breakdown: {
    base_amount: string;
    meal_amount: string;
    service_fee: string;
    gst: string;
    promo_discount: string;
    total_amount: string;
  } | null;
}

// ---- Wallet ----

export interface WalletBalance {
  balance: string;
  locked_balance: string;
  total_balance: string;
  currency: string;
  is_active: boolean;
  updated_at: string;
}

export interface WalletTransaction {
  id: number;
  uid?: string;
  transaction_type: string;   // 'credit' | 'debit'
  txn_type?: string;          // legacy alias
  amount: string;
  amount_display: string;
  balance_after: string;
  reference?: string;
  description: string;
  note?: string;              // legacy alias for description
  is_reversed: boolean;
  created_at: string;
}

export interface OwnerWallet {
  balance: string;
  pending_balance: string;
  total_earned: string;
  currency: string;
  is_verified: boolean;
  bank_name: string;
  upi_id: string;
  updated_at: string;
}

// ---- Search Params ----

export interface HotelSearchParams {
  location?: string;
  checkin?: string;
  checkout?: string;
  adults?: number;
  children?: number;
  rooms?: number;
  min_price?: number;
  max_price?: number;
  sort?: 'popular' | 'price_asc' | 'price_desc' | 'rating' | 'newest' | 'best_reviewed';
  amenity?: string[];
  room_amenity?: string[];       // Phase 4: room-level amenity filter
  property_type?: string;
  free_cancellation?: boolean;
  breakfast_included?: boolean;  // S6: filter for room_only=false meal plans
  pay_at_hotel?: boolean;        // Phase 4: no upfront payment required
  stars?: number;                // S6: star category filter (1–5)
  user_rating?: number;          // Phase 4: review score threshold (3, 3.5, 4, 4.5)
  page?: number;
  page_size?: number;
}

// ---- Pricing Intelligence (Competitor Benchmarking) ----

export interface CompetitorPrice {
  name: string;
  source: string;
  price_per_night: number;
  date: string;
  is_available: boolean;
  fetched_at: string;
  price_delta: number;
  price_delta_pct: number;
  notes: string;
}

export interface PricingIntelligence {
  property_uuid: string;
  property_name: string;
  our_min_price: number;
  competitors: CompetitorPrice[];
  summary: {
    total_competitors: number;
    avg_competitor_price: number;
    min_competitor_price: number;
    max_competitor_price: number;
    our_advantage_pct: number;
    is_cheapest: boolean | null;
  };
}

// ---- Promo Code ----

export interface PromoResult {
  valid: boolean;
  promo_code?: string;
  discount_type?: 'percent' | 'amount';
  discount_value?: string;
  discount_amount?: string;
  updated_breakdown?: {
    base_amount: string;
    meal_amount: string;
    service_fee: string;
    gst_percentage: string;
    gst_amount: string;
    promo_discount: string;
    total_amount: string;
  };
  new_total?: string;
}

// ---- Payment Gateway Types ----

export type PaymentGatewayName = 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi';

export interface PaymentGateway {
  name: PaymentGatewayName;
  display_name: string;
  available: boolean;
  wallet_balance?: string;
  sufficient_balance?: boolean;
}

export interface PaymentTransaction {
  transaction_id: string;
  gateway: PaymentGatewayName;
  amount: string;
  status: 'initiated' | 'pending' | 'success' | 'failed' | 'cancelled' | 'refunded';
  booking_uuid: string;
  booking_status: string | null;
  created_at: string;
  updated_at: string;
}

