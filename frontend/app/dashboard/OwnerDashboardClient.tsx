'use client';

import { useState } from 'react';
import {
  Building2, TrendingUp, Calendar, BarChart3, IndianRupee,
  Bus, Car, Package, ChevronRight, Users, ArrowUp, ArrowDown,
  Loader2, AlertCircle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import {
  useOwnerSummary, useInventoryCalendar, useBookingAnalytics,
  useRevenueBreakdown, useBusOperatorDashboard, useCabFleetDashboard,
  usePackageProviderDashboard,
} from '@/hooks/useDashboard';
import { format, startOfMonth } from 'date-fns';

function MetricCard({ label, value, icon: Icon, trend, color = 'text-neutral-900' }: {
  label: string; value: string; icon: React.ElementType; trend?: number; color?: string;
}) {
  return (
    <div className="bg-white/80 rounded-xl p-4 border border-neutral-100 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-neutral-500">{label}</span>
        <Icon size={16} className="text-neutral-300" />
      </div>
      <p className={`text-xl font-black ${color}`}>{value}</p>
      {trend != null && (
        <div className={`flex items-center gap-1 mt-1 text-xs font-semibold ${trend >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {trend >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
          {Math.abs(trend).toFixed(1)}% vs last period
        </div>
      )}
    </div>
  );
}

function SimpleBarChart({ data, labelKey, valueKey, formatVal }: {
  data: Record<string, unknown>[]; labelKey: string; valueKey: string; formatVal?: (v: number) => string;
}) {
  const max = Math.max(...data.map(d => Number(d[valueKey]) || 0), 1);
  return (
    <div className="space-y-2">
      {data.slice(0, 8).map((row, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs text-neutral-500 w-24 truncate shrink-0">{String(row[labelKey])}</span>
          <div className="flex-1 h-5 bg-neutral-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-500 rounded-full transition-all"
              style={{ width: `${(Number(row[valueKey]) / max) * 100}%` }}
            />
          </div>
          <span className="text-xs font-bold text-neutral-700 w-16 text-right shrink-0">
            {formatVal ? formatVal(Number(row[valueKey])) : Number(row[valueKey]).toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Hotel Owner Dashboard ────────────────────────────────────── */
function HotelOwnerDashboard({ propertyId }: { propertyId: number | null }) {
  const { formatPrice } = useFormatPrice();
  const [days] = useState(30);
  const [calMonth] = useState(format(startOfMonth(new Date()), 'yyyy-MM'));

  const { data: summary, isLoading: sumLoading } = useOwnerSummary(propertyId, days);
  const { data: analytics } = useBookingAnalytics(propertyId, days);
  const { data: revenue } = useRevenueBreakdown(propertyId, days);
  const { data: calendar } = useInventoryCalendar(propertyId, calMonth);

  if (sumLoading) return <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-neutral-400" /></div>;

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Total Bookings" value={String(summary?.total_bookings || 0)} icon={Building2} />
        <MetricCard label="Revenue" value={formatPrice(summary?.total_revenue || 0)} icon={IndianRupee} color="text-green-700" />
        <MetricCard label="Occupancy" value={`${(summary?.avg_occupancy || 0).toFixed(0)}%`} icon={BarChart3} color="text-blue-700" />
        <MetricCard label="Confirmed" value={String(summary?.confirmed_bookings || 0)} icon={Users} />
      </div>

      {/* Revenue breakdown */}
      {revenue && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Revenue Breakdown</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-green-50 rounded-lg p-3 border border-green-100">
              <p className="text-xs text-green-600">Gross Revenue</p>
              <p className="text-lg font-black text-green-800">{formatPrice(revenue.gross_revenue)}</p>
            </div>
            <div className="bg-red-50 rounded-lg p-3 border border-red-100">
              <p className="text-xs text-red-600">Commission ({revenue.commission_rate}%)</p>
              <p className="text-lg font-black text-red-800">-{formatPrice(revenue.commission)}</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
              <p className="text-xs text-blue-600">Net Payout</p>
              <p className="text-lg font-black text-blue-800">{formatPrice(revenue.net_payout)}</p>
            </div>
          </div>
          {revenue.pending_settlement > 0 && (
            <div className="mt-3 bg-amber-50 rounded-lg px-3 py-2 border border-amber-200 flex items-center gap-2">
              <AlertCircle size={14} className="text-amber-600" />
              <p className="text-xs text-amber-700">
                <span className="font-semibold">{formatPrice(revenue.pending_settlement)}</span> pending settlement
              </p>
            </div>
          )}
        </div>
      )}

      {/* Top rooms */}
      {analytics && analytics.top_rooms && analytics.top_rooms.length > 0 && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Top Room Types</h3>
          <SimpleBarChart
            data={analytics.top_rooms}
            labelKey="room"
            valueKey="revenue"
            formatVal={(v) => formatPrice(v)}
          />
        </div>
      )}

      {/* Inventory calendar */}
      {calendar && calendar.length > 0 && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Inventory Calendar — {calMonth}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-neutral-400 border-b border-neutral-100">
                  <th className="text-left py-2 pr-3">Date</th>
                  <th className="text-left py-2 pr-3">Room</th>
                  <th className="text-right py-2 pr-3">Total</th>
                  <th className="text-right py-2 pr-3">Available</th>
                  <th className="text-right py-2 pr-3">Booked</th>
                  <th className="text-right py-2">Price</th>
                </tr>
              </thead>
              <tbody>
                {calendar.slice(0, 20).map((row, i) => (
                  <tr key={i} className="border-b border-neutral-50">
                    <td className="py-1.5 pr-3 font-medium text-neutral-700">{row.date}</td>
                    <td className="py-1.5 pr-3 text-neutral-600">{row.room_type}</td>
                    <td className="py-1.5 pr-3 text-right text-neutral-600">{row.total}</td>
                    <td className={`py-1.5 pr-3 text-right font-semibold ${row.available > 0 ? 'text-green-600' : 'text-red-600'}`}>{row.available}</td>
                    <td className="py-1.5 pr-3 text-right text-neutral-600">{row.booked}</td>
                    <td className="py-1.5 text-right font-semibold text-neutral-800">{formatPrice(row.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Bus Operator Dashboard ───────────────────────────────────── */
function BusOperatorDashboardPanel() {
  const { formatPrice } = useFormatPrice();
  const { data, isLoading } = useBusOperatorDashboard();

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-neutral-400" /></div>;
  if (!data) return <p className="text-neutral-400 text-sm text-center py-8">No data available</p>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Total Buses" value={String(data.total_buses)} icon={Bus} />
        <MetricCard label="Active Schedules" value={String(data.active_schedules)} icon={Calendar} />
        <MetricCard label="Revenue" value={formatPrice(data.total_revenue)} icon={IndianRupee} color="text-green-700" />
        <MetricCard label="Occupancy" value={`${(data.occupancy_rate || 0).toFixed(0)}%`} icon={BarChart3} color="text-blue-700" />
      </div>
      {data.routes && data.routes.length > 0 && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Top Routes</h3>
          <SimpleBarChart
            data={data.routes}
            labelKey="route"
            valueKey="revenue"
            formatVal={(v) => formatPrice(v)}
          />
        </div>
      )}
    </div>
  );
}

/* ── Cab Fleet Dashboard ──────────────────────────────────────── */
function CabFleetDashboardPanel() {
  const { formatPrice } = useFormatPrice();
  const { data, isLoading } = useCabFleetDashboard();

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-neutral-400" /></div>;
  if (!data) return <p className="text-neutral-400 text-sm text-center py-8">No data available</p>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Vehicles" value={String(data.total_vehicles)} icon={Car} />
        <MetricCard label="Active Drivers" value={String(data.active_drivers)} icon={Users} />
        <MetricCard label="Revenue" value={formatPrice(data.total_revenue)} icon={IndianRupee} color="text-green-700" />
        <MetricCard label="Avg Rating" value={data.avg_rating?.toFixed(1) || 'N/A'} icon={BarChart3} color="text-amber-700" />
      </div>
      {data.drivers && data.drivers.length > 0 && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Driver Performance</h3>
          <SimpleBarChart
            data={data.drivers}
            labelKey="name"
            valueKey="earnings"
            formatVal={(v) => formatPrice(v)}
          />
        </div>
      )}
    </div>
  );
}

/* ── Package Provider Dashboard ───────────────────────────────── */
function PackageProviderDashboardPanel() {
  const { formatPrice } = useFormatPrice();
  const { data, isLoading } = usePackageProviderDashboard();

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-neutral-400" /></div>;
  if (!data) return <p className="text-neutral-400 text-sm text-center py-8">No data available</p>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Packages" value={String(data.total_packages)} icon={Package} />
        <MetricCard label="Departures" value={String(data.active_departures)} icon={Calendar} />
        <MetricCard label="Revenue" value={formatPrice(data.total_revenue)} icon={IndianRupee} color="text-green-700" />
        <MetricCard label="Bookings" value={String(data.total_bookings)} icon={Users} />
      </div>
      {data.popular_packages && data.popular_packages.length > 0 && (
        <div className="bg-white/80 rounded-xl p-5 border border-neutral-100 shadow-sm">
          <h3 className="font-bold text-neutral-800 text-sm mb-4">Popular Packages</h3>
          <SimpleBarChart
            data={data.popular_packages}
            labelKey="name"
            valueKey="revenue"
            formatVal={(v) => formatPrice(v)}
          />
        </div>
      )}
    </div>
  );
}

/* ═════════════════════════════════════════════════════════════════
   MAIN DASHBOARD PAGE
═════════════════════════════════════════════════════════════════ */

const TABS = [
  { key: 'hotel', label: 'Hotel', icon: Building2, roles: ['property_owner', 'admin'] },
  { key: 'bus', label: 'Bus', icon: Bus, roles: ['bus_operator', 'admin'] },
  { key: 'cab', label: 'Cab Fleet', icon: Car, roles: ['cab_owner', 'admin'] },
  { key: 'package', label: 'Packages', icon: Package, roles: ['package_provider', 'admin'] },
] as const;

type DashboardTab = typeof TABS[number]['key'];

export default function OwnerDashboardClient() {
  const { user } = useAuth();
  const userRole = user?.role || 'traveler';

  // Filter tabs based on role
  const visibleTabs = TABS.filter(t => userRole === 'admin' || (t.roles as readonly string[]).includes(userRole));
  const [activeTab, setActiveTab] = useState<DashboardTab>(visibleTabs[0]?.key || 'hotel');

  const [propertyId] = useState<number | null>(null);

  if (visibleTabs.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Building2 size={40} className="mx-auto text-neutral-300 mb-3" />
          <h2 className="text-lg font-bold text-neutral-700 mb-1">No Dashboard Access</h2>
          <p className="text-sm text-neutral-400">Register as a property owner, bus operator, cab owner, or package provider.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen page-listing-bg">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-black text-neutral-900 font-heading">Owner Dashboard</h1>
          <p className="text-xs text-neutral-400 bg-white/80 px-3 py-1.5 rounded-full border border-neutral-200">
            {user?.full_name || 'Owner'} · {userRole.replace(/_/g, ' ')}
          </p>
        </div>

        {/* Tab navigation */}
        {visibleTabs.length > 1 && (
          <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-1">
            {visibleTabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all shrink-0 ${
                    activeTab === tab.key
                      ? 'bg-primary-600 text-white'
                      : 'bg-white/80 text-neutral-600 border border-neutral-200 hover:border-primary-300'
                  }`}
                >
                  <Icon size={14} /> {tab.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Dashboard content */}
        {activeTab === 'hotel' && <HotelOwnerDashboard propertyId={propertyId} />}
        {activeTab === 'bus' && <BusOperatorDashboardPanel />}
        {activeTab === 'cab' && <CabFleetDashboardPanel />}
        {activeTab === 'package' && <PackageProviderDashboardPanel />}
      </div>
    </div>
  );
}
