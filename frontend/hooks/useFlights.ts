import { useQuery } from '@tanstack/react-query';
import { searchFlights, getFlightDetail, getPopularRoutes } from '@/services/flights';
import type { FlightSearchParams } from '@/types/flights';

export function useFlightSearch(params: FlightSearchParams | null) {
  return useQuery({
    queryKey: ['flights', 'search', params],
    queryFn: () => searchFlights(params!),
    enabled: !!params?.origin && !!params?.destination && !!params?.departure_date,
    staleTime: 2 * 60_000,
  });
}

export function useFlightDetail(id: number | null) {
  return useQuery({
    queryKey: ['flights', 'detail', id],
    queryFn: () => getFlightDetail(id!),
    enabled: !!id,
    staleTime: 5 * 60_000,
  });
}

export function usePopularFlightRoutes() {
  return useQuery({
    queryKey: ['flights', 'popular-routes'],
    queryFn: getPopularRoutes,
    staleTime: 30 * 60_000,
  });
}
