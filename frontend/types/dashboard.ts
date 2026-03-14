// ============================================================
// ZygoTrip — Dashboard Types (Owner/Operator panels)
// ============================================================

export interface DashboardSummary {
  total_bookings: number;
  confirmed_bookings: number;
  total_revenue: number;
  avg_occupancy: number;
  trend: { date: string; bookings: number; revenue: number }[];
}

export interface InventoryCalendarDay {
  date: string;
  room_type: string;
  total: number;
  available: number;
  booked: number;
  held: number;
  price: number;
}

export interface RevenueBreakdown {
  gross_revenue: number;
  commission: number;
  commission_rate: number;
  gst_on_commission: number;
  gateway_fees: number;
  net_payout: number;
  pending_settlement: number;
  last_settlement_date: string | null;
}

export interface BookingAnalytics {
  status_breakdown: { status: string; count: number }[];
  top_rooms: { room: string; bookings: number; revenue: number }[];
  repeat_rate: number;
  avg_lead_time_days: number;
  monthly_trend: { month: string; bookings: number; revenue: number }[];
}

export interface BusOperatorDashboard {
  total_buses: number;
  active_schedules: number;
  total_bookings: number;
  total_revenue: number;
  occupancy_rate: number;
  routes: { route: string; bookings: number; revenue: number; occupancy: number }[];
}

export interface CabFleetDashboard {
  total_vehicles: number;
  active_drivers: number;
  total_trips: number;
  total_revenue: number;
  avg_rating: number;
  drivers: { name: string; trips: number; rating: number; earnings: number }[];
}

export interface PackageProviderDashboard {
  total_packages: number;
  active_departures: number;
  total_bookings: number;
  total_revenue: number;
  popular_packages: { name: string; bookings: number; revenue: number }[];
}
