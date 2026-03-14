/* Package types for the Next.js frontend */

export interface TravelPackage {
  id: number;
  slug: string;
  name: string;
  destination: string;
  description: string;
  duration_days: number;
  duration_nights?: number;
  base_price: number;
  price_adult: number;
  price_child: number;
  rating: number;
  review_count: number;
  image_url: string;
  difficulty_level: 'easy' | 'moderate' | 'challenging';
  max_group_size: number;
  category: string;
  category_slug: string;
  tags: string[];
  highlights?: string[];
  inclusions_summary: string[];
  /* Detail-only fields */
  inclusions?: string[];
  exclusions?: string[];
  images?: PackageImage[];
  itinerary?: PackageItineraryDay[];
  addons?: PackageAddon[];
  departures?: PackageDeparture[];
}

export interface PackageImage {
  url: string;
  is_featured: boolean;
}

export interface PackageItineraryDay {
  day: number;
  title: string;
  description: string;
  accommodation?: string;
  meals_included?: string;
  location?: string;
  activities?: { name: string; description?: string; time?: string; type?: string }[];
  meals?: string[];
  hotel?: string;
}

export interface PackageAddon {
  id: number;
  addon_type: string;
  name: string;
  description: string;
  price: number;
  pricing_type: string;
  max_quantity: number;
  is_popular: boolean;
  bundle_discount_pct: number;
}

export interface PackageDeparture {
  id: number;
  departure_date: string;
  return_date: string;
  available_slots: number;
  is_guaranteed: boolean;
  is_sold_out: boolean;
}

export interface PackageSearchParams {
  destination?: string;
  category?: string;
  duration?: string;
  budget?: string;
  difficulty?: string;
  sort?: 'price' | 'price_desc' | 'rating' | 'duration' | 'popular';
  page?: number;
  per_page?: number;
}

export interface PackageSearchResult {
  packages: TravelPackage[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  filters: {
    destinations: string[];
    categories: { name: string; slug: string }[];
    durations: string[];
    difficulties: string[];
  };
}

export interface PackageCategory {
  name: string;
  slug: string;
  description: string;
}

export interface PackageDestination {
  destination: string;
  avg_price: number;
  avg_rating: number;
}
