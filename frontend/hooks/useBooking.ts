'use client';
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';

export function useBookingContext(contextId: string | undefined) {
  // Accept UUID string (preferred) or numeric ID (legacy)
  return useQuery({
    queryKey: ['booking-context', contextId],
    queryFn: () => bookingsService.getContext(contextId!),
    enabled: !!contextId,
    refetchInterval: 60_000, // refresh to check expiry
  });
}

export function useMyBookings() {
  return useInfiniteQuery({
    queryKey: ['my-bookings'],
    queryFn: ({ pageParam = 1 }) => bookingsService.getMyBookings(pageParam as number),
    initialPageParam: 1,
    getNextPageParam: (lastPage: any, pages) => {
      const total = lastPage.pagination?.total ?? 0;
      const perPage = lastPage.pagination?.per_page ?? 10;
      return pages.length * perPage < total ? pages.length + 1 : undefined;
    },
    staleTime: 30_000,
  });
}

export function useBookingDetail(uuid: string | undefined) {
  return useQuery({
    queryKey: ['booking', uuid],
    queryFn: () => bookingsService.getBooking(uuid!),
    enabled: !!uuid,
  });
}

export function useCreateBookingContext() {
  return useMutation({
    mutationFn: (payload: Parameters<typeof bookingsService.createContext>[0]) =>
      bookingsService.createContext(payload),
  });
}

export function useCreateBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      context_uuid?: string;
      context_id?: string;
      guest_name: string;
      guest_email: string;
      guest_phone: string;
      payment_method?: 'wallet' | 'gateway';
      promo_code?: string;
    }) => bookingsService.confirmBooking({
      ...(payload.context_uuid
        ? { context_uuid: payload.context_uuid }
        : { context_id: payload.context_id }
      ),
      payment_method: payload.payment_method ?? 'wallet',
      guest_name: payload.guest_name,
      guest_email: payload.guest_email,
      guest_phone: payload.guest_phone,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-bookings'] });
    },
  });
}

export function useCancelBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (uuid: string) => bookingsService.cancelBooking(uuid),
    onSuccess: (_data, uuid) => {
      queryClient.invalidateQueries({ queryKey: ['booking', uuid] });
      queryClient.invalidateQueries({ queryKey: ['my-bookings'] });
    },
  });
}
