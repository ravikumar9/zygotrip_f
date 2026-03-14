import { useQuery } from '@tanstack/react-query';
import {
  getOwnerSummary, getInventoryCalendar, getBookingAnalytics,
  getRevenueBreakdown, getBusOperatorDashboard, getCabFleetDashboard,
  getPackageProviderDashboard,
} from '@/services/dashboard';

export function useOwnerSummary(propertyId: number | null, days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'owner', 'summary', propertyId, days],
    queryFn: () => getOwnerSummary(propertyId, days),
    staleTime: 5 * 60_000,
  });
}

export function useInventoryCalendar(propertyId: number | null, month: string) {
  return useQuery({
    queryKey: ['dashboard', 'owner', 'calendar', propertyId, month],
    queryFn: () => getInventoryCalendar(propertyId, month),
    enabled: !!month,
    staleTime: 2 * 60_000,
  });
}

export function useBookingAnalytics(propertyId: number | null, days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'owner', 'analytics', propertyId, days],
    queryFn: () => getBookingAnalytics(propertyId, days),
    staleTime: 5 * 60_000,
  });
}

export function useRevenueBreakdown(propertyId: number | null, days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'owner', 'revenue', propertyId, days],
    queryFn: () => getRevenueBreakdown(propertyId, days),
    staleTime: 5 * 60_000,
  });
}

export function useBusOperatorDashboard(days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'bus', days],
    queryFn: () => getBusOperatorDashboard(days),
    staleTime: 5 * 60_000,
  });
}

export function useCabFleetDashboard(days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'cab', days],
    queryFn: () => getCabFleetDashboard(days),
    staleTime: 5 * 60_000,
  });
}

export function usePackageProviderDashboard(days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'package', days],
    queryFn: () => getPackageProviderDashboard(days),
    staleTime: 5 * 60_000,
  });
}
