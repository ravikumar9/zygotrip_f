'use client';
import { useQuery, useInfiniteQuery, keepPreviousData } from '@tanstack/react-query';
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

/**
 * Infinite scroll variant — used for listing pages that load more results
 * as the user scrolls down instead of traditional page-based pagination.
 */
export function useInfiniteHotels(params: Omit<HotelSearchParams, 'page'>) {
  return useInfiniteQuery({
    queryKey: ['hotels-infinite', params],
    queryFn: ({ pageParam = 1 }) => listHotels({ ...params, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const current = lastPage.pagination?.current_page ?? 1;
      const total = lastPage.pagination?.total_pages ?? 1;
      return current < total ? current + 1 : undefined;
    },
    staleTime: 60_000,
  });
}
