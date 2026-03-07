'use client';
import { useQuery } from '@tanstack/react-query';
import { getHotel, checkAvailability } from '@/services/hotels';

export function useHotelDetail(slug: string) {
  return useQuery({
    queryKey: ['hotel', slug],
    queryFn: () => getHotel(slug),
    enabled: !!slug,
    staleTime: 5 * 60_000, // 5 minutes
  });
}

export function useAvailability(
  propertyId: number | undefined,
  checkin: string | undefined,
  checkout: string | undefined,
  rooms: number = 1
) {
  return useQuery({
    queryKey: ['availability', propertyId, checkin, checkout, rooms],
    queryFn: () => checkAvailability(propertyId!, checkin!, checkout!, rooms),
    enabled: !!(propertyId && checkin && checkout),
    staleTime: 60_000,
    retry: 1,
  });
}
