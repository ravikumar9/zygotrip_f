import api from './api';
import type { FlightSearchParams, FlightSearchResult, FlightResult } from '@/types/flights';

export async function searchFlights(params: FlightSearchParams): Promise<FlightSearchResult> {
  const { data } = await api.get('/flights/search/', {
    params: {
      origin: params.origin,
      destination: params.destination,
      departure_date: params.departure_date,
      return_date: params.return_date,
      adults: params.adults,
      children: params.children,
      infants: params.infants,
      cabin_type: params.cabin_class,
      sort_by: params.sort,
    },
  });

  const outbound = data.outbound || data.results || [];
  const results: FlightResult[] = outbound.map((item: any) => ({
    id: item.flight_id,
    supplier: item.supplier || item.airline?.name || 'internal',
    segments: [
      {
        id: item.flight_id,
        airline: item.airline?.name || '',
        airline_code: item.airline?.code || '',
        airline_logo: item.airline?.logo_url || undefined,
        flight_number: item.flight_number,
        departure_airport: {
          code: item.origin?.code || '',
          name: item.origin?.name || '',
          city: item.origin?.city || '',
          country: item.origin?.country || '',
        },
        arrival_airport: {
          code: item.destination?.code || '',
          name: item.destination?.name || '',
          city: item.destination?.city || '',
          country: item.destination?.country || '',
        },
        departure_time: item.departure,
        arrival_time: item.arrival,
        duration_minutes: item.duration_minutes,
        cabin_class: item.fare_class?.cabin || params.cabin_class,
        aircraft_type: item.aircraft,
      },
    ],
    total_duration_minutes: item.duration_minutes,
    stops: item.stops,
    price_adult: item.price_per_adult || item.total_price,
    price_child: item.price_per_child || 0,
    price_infant: item.price_infant || 0,
    currency: item.currency || 'INR',
    fare_class: item.fare_class?.code || '',
    refundable: !!item.fare_class?.is_refundable,
    baggage_included: item.fare_class?.baggage_kg ? `${item.fare_class.baggage_kg}kg` : '',
    meal_included: !!item.fare_class?.meal_included,
    seats_available: item.fare_class?.available_seats || 0,
  }));

  return {
    results,
    filters: {
      airlines: [],
      stops: [],
      price_range: {
        min: results.length ? Math.min(...results.map((result) => result.price_adult)) : 0,
        max: results.length ? Math.max(...results.map((result) => result.price_adult)) : 0,
      },
      departure_times: [],
    },
    total: results.length,
  };
}

export async function getFlightDetail(id: number): Promise<FlightResult> {
  const { data } = await api.get(`/flights/booking/${id}/`);
  return data;
}

export async function getFlightFareRules(id: number): Promise<{ rules: string; baggage: string; cancellation: string }> {
  const { data } = await api.get(`/flights/fare-calendar/`, { params: { flight_id: id } });
  return data;
}

export async function getPopularRoutes(): Promise<{ origin: string; destination: string; min_price: number }[]> {
  return [];
}

export async function getAirportSuggestions(query: string): Promise<{ code: string; name: string; city: string }[]> {
  const { data } = await api.get('/flights/airports/', { params: { q: query } });
  return data.results || [];
}
