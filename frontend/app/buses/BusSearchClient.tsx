'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search, ArrowRight, MapPin, Users, Loader2, SlidersHorizontal, X } from 'lucide-react';
import { searchBuses, getPopularRoutes } from '@/services/buses';
import CityAutocomplete from '@/components/search/CityAutocomplete';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type { Bus, BusSearchParams, BusSearchResult, BusRoute } from '@/types/buses';

const BUS_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'AC_SEATER', label: 'AC Seater' },
  { value: 'AC_SLEEPER', label: 'AC Sleeper' },
  { value: 'NON_AC_SEATER', label: 'Non-AC Seater' },
  { value: 'NON_AC_SLEEPER', label: 'Non-AC Sleeper' },
  { value: 'VOLVO', label: 'Volvo' },
  { value: 'LUXURY', label: 'Luxury' },
];

const SORT_OPTIONS = [
  { value: 'departure', label: 'Departure Time' },
  { value: 'price', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'duration', label: 'Duration' },
  { value: 'rating', label: 'Highest Rated' },
];

const TIME_SLOTS = [
  { value: '', label: 'Any Time' },
  { value: 'morning', label: '🌅 Morning', desc: '6 AM - 12 PM' },
  { value: 'afternoon', label: '☀️ Afternoon', desc: '12 PM - 6 PM' },
  { value: 'evening', label: '🌆 Evening', desc: '6 PM - 10 PM' },
  { value: 'night', label: '🌙 Night', desc: '10 PM - 6 AM' },
];

function formatTime(time: string) {
  if (!time) return '--:--';
  const [h, m] = time.split(':');
  const hour = parseInt(h, 10);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const h12 = hour % 12 || 12;
  return `${h12}:${m} ${ampm}`;
}

function getJourneyDuration(dep: string, arr: string): string {
  if (!dep || !arr) return '';
  try {
    const [dh, dm] = dep.split(':').map(Number);
    const [ah, am] = arr.split(':').map(Number);
    let mins = (ah * 60 + am) - (dh * 60 + dm);
    if (mins < 0) mins += 24 * 60; // overnight
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h > 0 ? `${h}h ${m > 0 ? m + 'm' : ''}` : `${m}m`;
  } catch { return ''; }
}

/* ── Skeleton ── */
function BusCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-5 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="h-4 bg-neutral-100 rounded w-1/3" />
          <div className="h-5 bg-neutral-100 rounded w-2/3" />
          <div className="flex gap-2">
            <div className="h-5 w-16 bg-neutral-100 rounded-full" />
            <div className="h-5 w-16 bg-neutral-100 rounded-full" />
          </div>
        </div>
        <div className="text-right space-y-2">
          <div className="h-6 w-20 bg-neutral-100 rounded" />
          <div className="h-9 w-28 bg-neutral-100 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

/* ── Bus Result Card ── */
function BusCard({ bus }: { bus: Bus }) {
  const { formatPrice } = useFormatPrice();
  const availableSeats = bus.available_seats ?? 0;

  return (
    <div className="bg-white rounded-2xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow p-5">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        {/* Left: Operator & Route */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider text-neutral-400">
              {bus.operator_name}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-neutral-100 text-neutral-500">
              {bus.bus_type}
            </span>
          </div>

          <div className="flex items-center gap-3 my-2">
            <div className="text-center">
              <p className="font-black text-lg text-neutral-900">{formatTime(bus.departure_time)}</p>
              <p className="text-xs text-neutral-400 truncate max-w-[100px]">{bus.from_city}</p>
            </div>
            <div className="flex-1 flex flex-col items-center gap-0.5 px-2">
              {getJourneyDuration(bus.departure_time, bus.arrival_time) && (
                <span className="text-[10px] font-bold text-neutral-400">{getJourneyDuration(bus.departure_time, bus.arrival_time)}</span>
              )}
              <div className="flex items-center gap-1 w-full">
                <div className="w-2 h-2 rounded-full border-2 border-green-400" />
                <div className="h-px flex-1 bg-neutral-200" />
                <ArrowRight size={12} className="text-neutral-300 shrink-0" />
                <div className="h-px flex-1 bg-neutral-200" />
                <div className="w-2 h-2 rounded-full border-2 border-red-400" />
              </div>
            </div>
            <div className="text-center">
              <p className="font-black text-lg text-neutral-900">{formatTime(bus.arrival_time)}</p>
              <p className="text-xs text-neutral-400 truncate max-w-[100px]">{bus.to_city}</p>
            </div>
          </div>

          {/* Tags */}
          <div className="flex items-center gap-2 flex-wrap mt-2">
            {bus.amenities && bus.amenities.length > 0 && bus.amenities.slice(0, 3).map((a) => (
              <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">
                {a}
              </span>
            ))}
            {bus.is_ac && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-50 text-green-600 font-medium">AC</span>
            )}
            {bus.is_sleeper && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 font-medium">Sleeper</span>
            )}
          </div>
        </div>

        {/* Right: Price & Book */}
        <div className="sm:text-right shrink-0 flex sm:flex-col items-center sm:items-end gap-3 sm:gap-1">
          <p className="text-2xl font-black text-neutral-900">{formatPrice(bus.price_per_seat)}</p>
          <p className="text-xs text-neutral-400">per seat</p>
          <div className="flex items-center gap-2 mt-1">
            {availableSeats > 0 ? (
              <span className={`text-xs font-bold ${availableSeats <= 5 ? 'text-orange-500' : 'text-green-600'}`}>
                <Users size={12} className="inline mr-0.5" />
                {availableSeats} seat{availableSeats !== 1 ? 's' : ''} left
              </span>
            ) : (
              <span className="text-xs font-bold text-red-500">Sold Out</span>
            )}
          </div>
          <Link
            href={`/buses/${bus.id}`}
            className="mt-2 inline-flex items-center gap-1 px-5 py-2.5 rounded-xl text-white text-sm font-bold transition-opacity hover:opacity-90"
            style={{ background: 'var(--primary)' }}
          >
            Select Seats <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Popular Route Card ── */
function RouteCard({ route, onSelect }: { route: BusRoute; onSelect: (from: string, to: string) => void }) {
  const { formatPrice } = useFormatPrice();
  return (
    <button
      type="button"
      onClick={() => onSelect(route.from_city, route.to_city)}
      className="bg-white rounded-xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow p-4 flex items-center gap-3 text-left w-full"
    >
      <div className="shrink-0 w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
        <MapPin size={18} className="text-blue-500" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-bold text-sm text-neutral-900 truncate">
          {route.from_city} → {route.to_city}
        </p>
        <p className="text-xs text-neutral-400">
          {route.bus_count} bus{route.bus_count !== 1 ? 'es' : ''} · from {formatPrice(route.min_price)}
        </p>
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN SEARCH PAGE
═══════════════════════════════════════════════════════════════ */
export default function BusSearchClient() {
  const searchParams = useSearchParams();
  const router = useRouter();

  type BusSearchOverrides = Partial<Pick<BusSearchParams, 'from' | 'to' | 'date' | 'bus_type' | 'sort'>>;

  const todayStr = new Date().toISOString().split('T')[0];

  const [from, setFrom] = useState(searchParams.get('from') || '');
  const [to, setTo] = useState(searchParams.get('to') || '');
  const [date, setDate] = useState(searchParams.get('date') || todayStr);
  const [busType, setBusType] = useState(searchParams.get('bus_type') || '');
  const [sort, setSort] = useState(searchParams.get('sort') || 'departure');
  const [timeSlot, setTimeSlot] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(1);

  const [results, setResults] = useState<BusSearchResult | null>(null);
  const [routes, setRoutes] = useState<BusRoute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const hasSearched = !!(from && to);

  // Load popular routes on mount
  useEffect(() => {
    getPopularRoutes()
      .then((res) => setRoutes(Array.isArray(res) ? res : []))
      .catch(() => {});
  }, []);

  const doSearch = useCallback(async (p = 1, overrides: BusSearchOverrides = {}) => {
    const nextFrom = overrides.from ?? from;
    const nextTo = overrides.to ?? to;
    const nextDate = overrides.date ?? (date || undefined);
    const nextBusType = overrides.bus_type ?? (busType || undefined);
    const nextSort = (overrides.sort ?? sort) as BusSearchParams['sort'];

    if (!nextFrom || !nextTo) return;
    setLoading(true);
    setError('');
    try {
      const params: BusSearchParams = {
        from: nextFrom,
        to: nextTo,
        date: nextDate,
        bus_type: nextBusType,
        sort: nextSort,
        page: p,
        per_page: 15,
      };
      const data = await searchBuses(params);
      setResults(data);
      setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to search buses. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [from, to, date, busType, sort]);

  // Re-search when sort or bus type changes (if we've already searched)
  useEffect(() => {
    if (hasSearched) doSearch(1);
  }, [sort, busType]);

  // Initial search from URL params
  useEffect(() => {
    if (searchParams.get('from') && searchParams.get('to')) {
      doSearch(1);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // Update URL
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (date) params.set('date', date);
    if (busType) params.set('bus_type', busType);
    if (sort) params.set('sort', sort);
    router.push(`/buses?${params.toString()}`);
    doSearch(1);
  };

  const totalPages = results ? results.total_pages : 0;

  return (
    <div className="min-h-screen page-listing-bg">
      {/* ── Hero / Search Bar ── */}
      <section
        className="relative pt-24 pb-8"
        style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%)' }}
      >
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse 70% 60% at 50% 110%, rgba(59,130,246,0.25) 0%, transparent 65%)',
            }}
          />
        </div>

        <div className="relative max-w-5xl mx-auto px-4">
          <h1 className="text-3xl sm:text-4xl font-black text-white mb-1 font-heading tracking-tight">
            Bus Tickets
          </h1>
          <p className="text-sm text-white/50 mb-6">
            Intercity bus bookings with instant confirmation
          </p>

          <form
            onSubmit={handleSearch}
            className="bg-white rounded-2xl shadow-xl p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3"
          >
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">From</label>
              <CityAutocomplete
                value={from}
                onChange={setFrom}
                placeholder="Departure city"
                icon={<MapPin size={16} />}
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">To</label>
              <CityAutocomplete
                value={to}
                onChange={setTo}
                placeholder="Arrival city"
                icon={<MapPin size={16} />}
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Date</label>
              <input
                type="date"
                value={date}
                min={todayStr}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Bus Type</label>
              <select
                value={busType}
                onChange={(e) => setBusType(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 bg-white"
              >
                {BUS_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={!from || !to}
                className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-white font-bold text-sm transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ background: 'var(--primary)' }}
              >
                <Search size={16} /> Search Buses
              </button>
            </div>
          </form>
        </div>
      </section>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* ── No search yet: Popular Routes ── */}
        {!hasSearched && !loading && (
          <>
            {routes.length > 0 && (
              <section>
                <h2 className="text-lg font-black text-neutral-900 mb-4 font-heading">Popular Routes</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {routes.map((r, i) => (
                    <RouteCard key={i} route={r} onSelect={(f, t) => {
                      setFrom(f);
                      setTo(t);
                      const params = new URLSearchParams();
                      params.set('from', f);
                      params.set('to', t);
                      if (date) params.set('date', date);
                      router.push(`/buses?${params.toString()}`);
                      doSearch(1, { from: f, to: t, date: date || undefined });
                    }} />
                  ))}
                </div>
              </section>
            )}

            {routes.length === 0 && (
              <div className="text-center py-16">
                <div className="text-6xl mb-4">🚌</div>
                <h2 className="text-xl font-black text-neutral-900 mb-2">Search Bus Tickets</h2>
                <p className="text-neutral-400 text-sm max-w-md mx-auto">
                  Enter your departure and arrival cities above to find available buses.
                </p>
              </div>
            )}
          </>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-neutral-500 text-sm mb-4">
              <Loader2 size={16} className="animate-spin" /> Searching buses...
            </div>
            {Array.from({ length: 4 }).map((_, i) => <BusCardSkeleton key={i} />)}
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
            <p className="text-red-600 font-medium text-sm">{error}</p>
            <button
              onClick={() => doSearch(1)}
              className="mt-3 text-sm font-bold underline"
              style={{ color: 'var(--primary)' }}
            >
              Try again
            </button>
          </div>
        )}

        {/* ── Results ── */}
        {!loading && !error && results && (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
              <p className="text-sm text-neutral-500">
                <span className="font-bold text-neutral-900">{results.total}</span> bus{results.total !== 1 ? 'es' : ''} found
                <span className="text-neutral-300 mx-1">·</span>
                {from} → {to}
              </p>
              <div className="flex items-center gap-2">
                {/* Mobile filter toggle */}
                <button
                  onClick={() => setFiltersOpen(true)}
                  className="flex lg:hidden items-center gap-1.5 text-sm border rounded-xl px-3 py-1.5 bg-white text-neutral-700 border-neutral-200 hover:border-neutral-400 transition-colors"
                >
                  <SlidersHorizontal size={14} />
                  Filters
                  {(busType || timeSlot) && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                </button>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-neutral-200 text-sm font-medium bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                >
                  {SORT_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Desktop: Quick filter chips */}
            <div className="hidden lg:flex items-center gap-2 mb-4 flex-wrap">
              {BUS_TYPES.filter(t => t.value).map((t) => (
                <button key={t.value} onClick={() => setBusType(busType === t.value ? '' : t.value)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap ${
                    busType === t.value
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-400'
                  }`}>{t.label}</button>
              ))}
              <span className="w-px h-5 bg-neutral-200 mx-1" />
              {TIME_SLOTS.filter(t => t.value).map((t) => (
                <button key={t.value} onClick={() => setTimeSlot(timeSlot === t.value ? '' : t.value)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap ${
                    timeSlot === t.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-neutral-600 border-neutral-200 hover:border-blue-400'
                  }`}>{t.label}</button>
              ))}
            </div>

            {/* Mobile filter bottom sheet */}
            {filtersOpen && (
              <>
                <div
                  className="lg:hidden fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
                  onClick={() => setFiltersOpen(false)}
                />
                <div className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white rounded-t-3xl shadow-2xl max-h-[85vh] overflow-y-auto animate-slide-up">
                  <div className="sticky top-0 bg-white z-10 px-5 pt-4 pb-3 border-b border-neutral-100 flex items-center justify-between">
                    <h3 className="font-bold text-neutral-900 text-base font-heading flex items-center gap-2">
                      <SlidersHorizontal size={16} /> Filters
                    </h3>
                    <div className="flex items-center gap-3">
                      {(busType || timeSlot) && (
                        <button onClick={() => { setBusType(''); setTimeSlot(''); }} className="text-xs text-red-500 font-semibold">
                          Clear All
                        </button>
                      )}
                      <button
                        onClick={() => setFiltersOpen(false)}
                        className="w-8 h-8 flex items-center justify-center rounded-full bg-neutral-100 hover:bg-neutral-200 transition-colors"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="p-5 space-y-5">
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Bus Type</p>
                      <div className="flex flex-wrap gap-1.5">
                        {BUS_TYPES.filter(t => t.value).map((t) => (
                          <button key={t.value} onClick={() => setBusType(busType === t.value ? '' : t.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              busType === t.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-neutral-700 border-neutral-200'
                            }`}>{t.label}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Departure Time</p>
                      <div className="flex flex-wrap gap-1.5">
                        {TIME_SLOTS.filter(t => t.value).map((t) => (
                          <button key={t.value} onClick={() => setTimeSlot(timeSlot === t.value ? '' : t.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              timeSlot === t.value ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-neutral-700 border-neutral-200'
                            }`}>
                            {t.label}
                            {t.desc && <span className="block text-[10px] opacity-70">{t.desc}</span>}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Sort By</p>
                      <div className="flex flex-wrap gap-1.5">
                        {SORT_OPTIONS.map((s) => (
                          <button key={s.value} onClick={() => { setSort(s.value); setFiltersOpen(false); }}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              sort === s.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-neutral-700 border-neutral-200'
                            }`}>{s.label}</button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="sticky bottom-0 px-5 py-4 border-t border-neutral-100 bg-white">
                    <button
                      onClick={() => setFiltersOpen(false)}
                      className="w-full py-3 rounded-xl font-bold text-white text-sm"
                      style={{ background: 'var(--primary)' }}
                    >
                      Show Results
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* Bus Cards */}
            {(() => {
              // Client-side time filter
              let filteredBuses = results.buses;
              if (timeSlot) {
                filteredBuses = filteredBuses.filter((bus) => {
                  const hour = parseInt(bus.departure_time?.split(':')[0] || '0', 10);
                  switch (timeSlot) {
                    case 'morning': return hour >= 6 && hour < 12;
                    case 'afternoon': return hour >= 12 && hour < 18;
                    case 'evening': return hour >= 18 && hour < 22;
                    case 'night': return hour >= 22 || hour < 6;
                    default: return true;
                  }
                });
              }
              return filteredBuses.length > 0 ? (
                <div className="space-y-3">
                  {filteredBuses.map((bus) => (
                    <BusCard key={bus.id} bus={bus} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-16">
                  <div className="text-5xl mb-4">🔍</div>
                  <h3 className="text-lg font-bold text-neutral-900 mb-1">No buses found</h3>
                  <p className="text-neutral-400 text-sm">
                    {timeSlot ? 'Try a different time slot or ' : 'Try '}changing your dates or route.
                  </p>
                  {timeSlot && (
                    <button onClick={() => setTimeSlot('')} className="mt-2 text-sm font-bold text-blue-500 hover:text-blue-600">
                      Clear time filter
                    </button>
                  )}
                </div>
              );
            })()}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => doSearch(page - 1)}
                  disabled={page <= 1}
                  className="px-4 py-2 rounded-xl border border-neutral-200 text-sm font-bold disabled:opacity-30 hover:bg-neutral-50 transition-colors"
                >
                  ← Prev
                </button>
                <span className="text-sm text-neutral-500 tabular-nums">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => doSearch(page + 1)}
                  disabled={page >= totalPages}
                  className="px-4 py-2 rounded-xl border border-neutral-200 text-sm font-bold disabled:opacity-30 hover:bg-neutral-50 transition-colors"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
