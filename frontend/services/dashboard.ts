import api from './api';
import type {
  DashboardSummary, InventoryCalendarDay, RevenueBreakdown,
  BookingAnalytics, BusOperatorDashboard, CabFleetDashboard,
  PackageProviderDashboard,
} from '@/types/dashboard';

const BASE = '/dashboard/owner';

function toNumber(value: unknown): number {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') return Number(value) || 0;
  return 0;
}

function normalizeOwnerSummary(data: Record<string, unknown>): DashboardSummary {
  const trend = Array.isArray(data.trend) ? data.trend : Array.isArray(data.revenue_trend) ? data.revenue_trend : [];
  return {
    total_bookings: toNumber(data.total_bookings),
    confirmed_bookings: toNumber(data.confirmed_bookings),
    total_revenue: toNumber(data.total_revenue ?? data.revenue),
    avg_occupancy: toNumber(data.avg_occupancy ?? data.occupancy_rate),
    trend: trend.map((row: any) => ({
      date: String(row.date ?? ''),
      bookings: toNumber(row.bookings),
      revenue: toNumber(row.revenue),
    })),
  };
}

function normalizeInventoryCalendar(data: Record<string, unknown>): InventoryCalendarDay[] {
  if (Array.isArray(data.inventory)) {
    return data.inventory.map((row: any) => ({
      date: String(row.date),
      room_type: String(row.room_type ?? ''),
      total: toNumber(row.total),
      available: toNumber(row.available),
      booked: toNumber(row.booked),
      held: toNumber(row.held),
      price: toNumber(row.price),
    }));
  }

  const calendar = data.calendar as Record<string, any[]> | undefined;
  if (!calendar) return [];
  return Object.entries(calendar).flatMap(([date, rows]) =>
    rows.map((row) => ({
      date,
      room_type: String(row.room_type ?? ''),
      total: toNumber(row.total),
      available: toNumber(row.available),
      booked: toNumber(row.booked),
      held: toNumber(row.held),
      price: toNumber(row.price),
    })),
  );
}

function normalizeBookingAnalytics(data: Record<string, unknown>): BookingAnalytics {
  const rawStatuses = Array.isArray(data.status_breakdown) ? data.status_breakdown : [];
  const rawTopRooms = Array.isArray(data.top_rooms) ? data.top_rooms : Array.isArray(data.top_room_types) ? data.top_room_types : [];
  const monthlyTrend = Array.isArray(data.monthly_trend) ? data.monthly_trend : [];
  return {
    status_breakdown: rawStatuses.map((row: any) => ({
      status: String(row.status ?? ''),
      count: toNumber(row.count),
    })),
    top_rooms: rawTopRooms.map((row: any) => ({
      room: String(row.room ?? row.room_type__name ?? ''),
      bookings: toNumber(row.bookings ?? row.count),
      revenue: toNumber(row.revenue),
    })),
    repeat_rate: toNumber(data.repeat_rate),
    avg_lead_time_days: toNumber(data.avg_lead_time_days),
    monthly_trend: monthlyTrend.map((row: any) => ({
      month: String(row.month ?? row.date ?? ''),
      bookings: toNumber(row.bookings),
      revenue: toNumber(row.revenue),
    })),
  };
}

function normalizeRevenueBreakdown(data: Record<string, unknown>): RevenueBreakdown {
  return {
    gross_revenue: toNumber(data.gross_revenue),
    commission: toNumber(data.commission ?? data.commission_paid),
    commission_rate: toNumber(data.commission_rate),
    gst_on_commission: toNumber(data.gst_on_commission ?? data.gst_collected),
    gateway_fees: toNumber(data.gateway_fees),
    net_payout: toNumber(data.net_payout ?? data.net_payable),
    pending_settlement: toNumber(data.pending_settlement),
    last_settlement_date: typeof data.last_settlement_date === 'string' ? data.last_settlement_date : null,
  };
}

function normalizeBusDashboard(data: Record<string, unknown>): BusOperatorDashboard {
  const routes = Array.isArray(data.routes) ? data.routes : Array.isArray(data.route_stats) ? data.route_stats : [];
  return {
    total_buses: toNumber(data.total_buses),
    active_schedules: toNumber(data.active_schedules ?? data.active_buses),
    total_bookings: toNumber(data.total_bookings),
    total_revenue: toNumber(data.total_revenue ?? data.revenue),
    occupancy_rate: toNumber(data.occupancy_rate),
    routes: routes.map((row: any) => ({
      route: String(row.route ?? `${row.bus__from_city ?? ''} → ${row.bus__to_city ?? ''}`),
      bookings: toNumber(row.bookings),
      revenue: toNumber(row.revenue),
      occupancy: toNumber(row.occupancy),
    })),
  };
}

function normalizeCabDashboard(data: Record<string, unknown>): CabFleetDashboard {
  const driverStats = (data.driver_stats ?? {}) as Record<string, unknown>;
  return {
    total_vehicles: toNumber(data.total_vehicles),
    active_drivers: toNumber(data.active_drivers ?? driverStats.active_drivers),
    total_trips: toNumber(data.total_trips),
    total_revenue: toNumber(data.total_revenue ?? data.revenue),
    avg_rating: toNumber(data.avg_rating ?? driverStats.avg_rating),
    drivers: Array.isArray(data.drivers) ? data.drivers.map((row: any) => ({
      name: String(row.name ?? ''),
      trips: toNumber(row.trips),
      rating: toNumber(row.rating),
      earnings: toNumber(row.earnings),
    })) : [],
  };
}

function normalizePackageDashboard(data: Record<string, unknown>): PackageProviderDashboard {
  return {
    total_packages: toNumber(data.total_packages),
    active_departures: toNumber(data.active_departures),
    total_bookings: toNumber(data.total_bookings),
    total_revenue: toNumber(data.total_revenue ?? data.revenue),
    popular_packages: Array.isArray(data.popular_packages) ? data.popular_packages.map((row: any) => ({
      name: String(row.name ?? row.package__name ?? ''),
      bookings: toNumber(row.bookings),
      revenue: toNumber(row.revenue),
    })) : [],
  };
}

// ── Hotel Owner ────────────────────────────────────────────
export async function getOwnerSummary(propertyId?: number | null, days = 30): Promise<DashboardSummary> {
  const { data } = await api.get(`${BASE}/summary/`, { params: { property_id: propertyId, days } });
  return normalizeOwnerSummary(data);
}

export async function getInventoryCalendar(propertyId: number | null | undefined, month: string): Promise<InventoryCalendarDay[]> {
  const { data } = await api.get(`${BASE}/inventory/`, { params: { property_id: propertyId, month, limit: 20 } });
  return normalizeInventoryCalendar(data);
}

export async function bulkUpdatePrices(updates: { room_type_id: number; date_from: string; date_to: string; price: number }[]): Promise<{ updated: number }> {
  const { data } = await api.post(`${BASE}/bulk-price/`, { updates });
  return { updated: toNumber(data.updated ?? data.updated_dates) };
}

export async function getBookingAnalytics(propertyId?: number | null, days = 30): Promise<BookingAnalytics> {
  const { data } = await api.get(`${BASE}/analytics/`, { params: { property_id: propertyId, days } });
  return normalizeBookingAnalytics(data);
}

export async function getRevenueBreakdown(propertyId?: number | null, days = 30): Promise<RevenueBreakdown> {
  const { data } = await api.get(`${BASE}/revenue/`, { params: { property_id: propertyId, days } });
  return normalizeRevenueBreakdown(data);
}

// ── Bus Operator ───────────────────────────────────────────
export async function getBusOperatorDashboard(days = 30): Promise<BusOperatorDashboard> {
  const { data } = await api.get(`${BASE}/bus/dashboard/`, { params: { days } });
  return normalizeBusDashboard(data);
}

// ── Cab Fleet ──────────────────────────────────────────────
export async function getCabFleetDashboard(days = 30): Promise<CabFleetDashboard> {
  const { data } = await api.get(`${BASE}/cab/dashboard/`, { params: { days } });
  return normalizeCabDashboard(data);
}

// ── Package Provider ───────────────────────────────────────
export async function getPackageProviderDashboard(days = 30): Promise<PackageProviderDashboard> {
  const { data } = await api.get(`${BASE}/package/dashboard/`, { params: { days } });
  return normalizePackageDashboard(data);
}
