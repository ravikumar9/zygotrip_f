/* Bus types for the Next.js frontend */

export interface Bus {
  id: number;
  uuid: string;
  operator_name: string;
  registration_number: string;
  from_city: string;
  to_city: string;
  departure_time: string;
  arrival_time: string;
  journey_date: string;
  bus_type: string;
  bus_type_code: string;
  amenities: string[];
  price_per_seat: number;
  available_seats: number;
  total_seats: number;
  is_ac: boolean;
  is_sleeper: boolean;
  seat_map?: Record<string, BusSeat[]>;
}

export interface BusSeat {
  id: number;
  seat_number: string;
  row: string;
  column: number;
  is_ladies_seat: boolean;
  state: 'available' | 'booked' | 'ladies' | 'selected';
  is_available: boolean;
}

export interface BusSearchParams {
  from?: string;
  to?: string;
  date?: string;
  bus_type?: string;
  sort?: 'price' | 'price_desc' | 'departure' | 'arrival' | 'seats';
  page?: number;
  per_page?: number;
}

export interface BusSearchResult {
  buses: Bus[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  filters: {
    bus_types: string[];
    from_cities: string[];
    to_cities: string[];
  };
}

export interface BusRoute {
  from_city: string;
  to_city: string;
  bus_count: number;
  min_price: number;
}
