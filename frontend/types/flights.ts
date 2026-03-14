// ============================================================
// ZygoTrip — Flight Types
// ============================================================

export interface Airport {
  code: string;
  name: string;
  city: string;
  country: string;
}

export interface FlightSegment {
  id: number;
  airline: string;
  airline_code: string;
  airline_logo?: string;
  flight_number: string;
  departure_airport: Airport;
  arrival_airport: Airport;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  cabin_class: 'economy' | 'premium_economy' | 'business' | 'first';
  aircraft_type?: string;
  operating_carrier?: string;
}

export interface FlightResult {
  id: number;
  supplier: string;
  segments: FlightSegment[];
  total_duration_minutes: number;
  stops: number;
  price_adult: number;
  price_child: number;
  price_infant: number;
  currency: string;
  fare_class: string;
  refundable: boolean;
  baggage_included: string;
  meal_included: boolean;
  seats_available: number;
}

export interface FlightSearchParams {
  origin: string;
  destination: string;
  departure_date: string;
  return_date?: string;
  adults: number;
  children: number;
  infants: number;
  cabin_class: 'economy' | 'premium_economy' | 'business' | 'first';
  trip_type: 'one_way' | 'round_trip';
  sort?: 'price' | 'duration' | 'departure' | 'arrival';
  max_stops?: number;
  airlines?: string[];
  max_price?: number;
}

export interface FlightSearchResult {
  results: FlightResult[];
  filters: {
    airlines: { code: string; name: string; count: number }[];
    stops: { value: number; count: number }[];
    price_range: { min: number; max: number };
    departure_times: { slot: string; count: number }[];
  };
  total: number;
}

export interface FlightBookingRequest {
  flight_id: number;
  passengers: FlightPassenger[];
  contact_email: string;
  contact_phone: string;
}

export interface FlightPassenger {
  type: 'adult' | 'child' | 'infant';
  title: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  passport_number?: string;
  nationality?: string;
}
