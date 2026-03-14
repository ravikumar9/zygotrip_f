// ============================================================
// ZygoTrip — Activity Types
// ============================================================

export interface Activity {
  id: number;
  slug: string;
  name: string;
  category: string;
  city: string;
  country?: string;
  description: string;
  short_description: string;
  primary_image?: string;
  images: { url: string; caption: string }[];
  duration_hours?: number;
  duration_display: string;
  price_adult: number;
  price_child?: number;
  currency?: string;
  rating: number;
  review_count: number;
  max_participants?: number;
  is_instant_confirm: boolean;
  is_free_cancellation: boolean;
  cancellation_hours: number;
  highlights: string[];
  inclusions: string[];
  exclusions: string[];
  meeting_point?: string;
  latitude?: string;
  longitude?: string;
  available_languages?: string[];
  supplier?: string;
}

export interface ActivitySearchParams {
  city?: string;
  category?: string;
  date?: string;
  adults?: number;
  children?: number;
  min_price?: number;
  max_price?: number;
  sort?: 'popular' | 'price_asc' | 'price_desc' | 'rating' | 'duration';
  page?: number;
}

export interface ActivitySearchResult {
  results: Activity[];
  filters: {
    categories: { value: string; count: number }[];
    price_range: { min: number; max: number };
    durations: { slot: string; count: number }[];
  };
  total: number;
  page: number;
  total_pages: number;
}

export interface ActivityTimeSlot {
  id: number;
  start_time: string;
  end_time: string;
  remaining_seats: number;
  price_adult: number;
  price_child: number;
}

export interface ActivityBookingRequest {
  activity_id: number;
  time_slot_id: number;
  date: string;
  adults: number;
  children: number;
  participants: ActivityParticipant[];
  contact_email: string;
  contact_phone: string;
}

export interface ActivityParticipant {
  name: string;
  age: number;
  type: 'adult' | 'child';
}
