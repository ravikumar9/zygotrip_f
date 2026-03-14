import { useQuery } from '@tanstack/react-query';
import { searchActivities, getActivityDetail, getActivityTimeSlots, getPopularActivities } from '@/services/activities';
import type { ActivitySearchParams } from '@/types/activities';

export function useActivitySearch(params: ActivitySearchParams | null) {
  return useQuery({
    queryKey: ['activities', 'search', params],
    queryFn: () => searchActivities(params!),
    enabled: !!params,
    staleTime: 2 * 60_000,
  });
}

export function useActivityDetail(slug: string | null) {
  return useQuery({
    queryKey: ['activities', 'detail', slug],
    queryFn: () => getActivityDetail(slug!),
    enabled: !!slug,
    staleTime: 5 * 60_000,
  });
}

export function useActivityTimeSlots(activityId: number | null, date: string | null) {
  return useQuery({
    queryKey: ['activities', 'time-slots', activityId, date],
    queryFn: () => getActivityTimeSlots(activityId!, date!),
    enabled: !!activityId && !!date,
    staleTime: 60_000,
  });
}

export function usePopularActivities(city?: string) {
  return useQuery({
    queryKey: ['activities', 'popular', city],
    queryFn: () => getPopularActivities(city),
    staleTime: 15 * 60_000,
  });
}
