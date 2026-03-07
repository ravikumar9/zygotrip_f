'use client';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { listHotels, searchHotels } from '@/services/hotels';
import type { HotelSearchParams } from '@/types';

export function useHotels(params: HotelSearchParams = {}) {
  return useQuery({
    queryKey: ['hotels', params],
    queryFn: () => listHotels(params),
    placeholderData: keepPreviousData,
    staleTime: 60_000, // 1 minute
  });
}

export function useHotelSearch(query: string, params: HotelSearchParams = {}) {
  return useQuery({
    queryKey: ['hotel-search', query, params],
    queryFn: () => searchHotels(query, params),
    enabled: !!query,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
