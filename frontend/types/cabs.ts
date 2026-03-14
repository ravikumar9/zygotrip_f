/* Cab types for the Next.js frontend */

export interface Cab {
  id: number;
  uuid: string;
  name: string;
  city: string;
  city_display: string;
  seats: number;
  fuel_type: string;
  base_price_per_km: number;
  price_per_km: number;
  image_url: string;
  category: 'hatchback' | 'sedan' | 'suv' | 'luxury';
  category_label: string;
  category_icon: string;
  is_active: boolean;
  images?: CabImage[];
}

export interface CabImage {
  id: number;
  url: string;
  is_primary: boolean;
}

export interface CabSearchParams {
  city?: string;
  from?: string;
  to?: string;
  date?: string;
  category?: string;
  sort?: 'price' | 'price_desc' | 'seats' | 'name';
  page?: number;
  per_page?: number;
}

export interface CabSearchResult {
  cabs: Cab[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  filters: {
    cities: { value: string; label: string }[];
    categories: { value: string; label: string; icon: string }[];
  };
}

export interface CityOption {
  value: string;
  label: string;
}
