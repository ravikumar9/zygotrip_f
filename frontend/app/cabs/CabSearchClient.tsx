'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search, MapPin, Car, Users, ArrowRight, Loader2, IndianRupee, ChevronDown, ChevronUp, SlidersHorizontal, X } from 'lucide-react';
import { searchCabs, getAvailableCities } from '@/services/cabs';
import CityAutocomplete from '@/components/search/CityAutocomplete';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type { Cab, CabSearchParams, CabSearchResult, CityOption } from '@/types/cabs';

const CATEGORIES = [
  { value: '', label: 'All Vehicles' },
  { value: 'hatchback', label: 'Hatchback' },
  { value: 'sedan', label: 'Sedan' },
  { value: 'suv', label: 'SUV' },
  { value: 'luxury', label: 'Luxury' },
];

const SORT_OPTIONS = [
  { value: 'price', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'seats', label: 'Most Seats' },
  { value: 'name', label: 'Name' },
];

/* ── Skeleton ── */
function CabCardSkeleton() {
  return (
    <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm overflow-hidden animate-pulse">
      <div className="h-48 bg-neutral-100" />
      <div className="p-4 space-y-3">
        <div className="h-4 bg-neutral-100 rounded w-1/3" />
        <div className="h-5 bg-neutral-100 rounded w-2/3" />
        <div className="h-3 bg-neutral-100 rounded w-1/2" />
        <div className="flex justify-between items-end">
          <div className="h-6 bg-neutral-100 rounded w-20" />
          <div className="h-9 bg-neutral-100 rounded-xl w-24" />
        </div>
      </div>
    </div>
  );
}

/* ── Cab Result Card ── */
function CabCard({ cab }: { cab: Cab }) {
  const { formatPrice } = useFormatPrice();
  const [showFare, setShowFare] = useState(false);

  // Estimated fare breakdown (base distance: 50km default)
  const estimatedKm = 50;
  const baseFare = cab.price_per_km * estimatedKm;
  const driverAllowance = 200;
  const gstRate = 0.05;
  const gst = Math.round(baseFare * gstRate);
  const totalEstimate = baseFare + driverAllowance + gst;

  return (
    <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow overflow-hidden group">
      {/* Image */}
      <div className="relative h-48 bg-neutral-100 overflow-hidden">
        {cab.image_url ? (
          <img
            src={cab.image_url}
            alt={cab.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl">🚗</div>
        )}
        {/* Category badge */}
        <span className="absolute top-3 left-3 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-white/80/90 backdrop-blur-sm text-neutral-700 shadow-sm">
          {cab.category_label || cab.category}
        </span>
      </div>

      <div className="p-4">
        {/* Name */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="font-bold text-neutral-900 text-sm leading-tight truncate">{cab.name}</h3>
        </div>

        {/* Details */}
        <div className="flex items-center gap-3 text-xs text-neutral-400 mb-3">
          <span className="inline-flex items-center gap-1">
            <Users size={12} /> {cab.seats} seats
          </span>
          <span className="inline-flex items-center gap-1">
            <Car size={12} /> {cab.fuel_type}
          </span>
          {cab.city_display && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={12} /> {cab.city_display}
            </span>
          )}
        </div>

        {/* Price + Fare Breakdown */}
        <div className="pt-2 border-t border-neutral-100">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-xl font-black text-neutral-900">{formatPrice(cab.price_per_km)}</p>
              <p className="text-[10px] text-neutral-400">per km</p>
            </div>
            <Link
              href={`/cabs/${cab.id}`}
              className="inline-flex items-center gap-1 px-4 py-2 rounded-xl text-white text-sm font-bold transition-opacity hover:opacity-90"
              style={{ background: 'var(--primary)' }}
            >
              Book <ArrowRight size={14} />
            </Link>
          </div>

          {/* Estimated Fare Toggle */}
          <button
            onClick={(e) => { e.preventDefault(); setShowFare(!showFare); }}
            className="mt-2 flex items-center gap-1 text-[10px] font-bold text-blue-500 hover:text-blue-600 transition-colors"
          >
            <IndianRupee size={10} />
            {showFare ? 'Hide' : 'Est.'} fare for {estimatedKm}km
            {showFare ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>

          {showFare && (
            <div className="mt-2 bg-page rounded-xl p-3 space-y-1.5 text-xs">
              <div className="flex justify-between text-neutral-500">
                <span>Base fare ({estimatedKm}km × {formatPrice(cab.price_per_km)})</span>
                <span className="font-medium text-neutral-700">{formatPrice(baseFare)}</span>
              </div>
              <div className="flex justify-between text-neutral-500">
                <span>Driver allowance</span>
                <span className="font-medium text-neutral-700">{formatPrice(driverAllowance)}</span>
              </div>
              <div className="flex justify-between text-neutral-500">
                <span>GST (5%)</span>
                <span className="font-medium text-neutral-700">{formatPrice(gst)}</span>
              </div>
              <div className="flex justify-between pt-1.5 border-t border-neutral-200 font-bold text-neutral-900">
                <span>Estimated total</span>
                <span>{formatPrice(totalEstimate)}</span>
              </div>
              <p className="text-[10px] text-neutral-400 mt-1">
                * Toll charges, parking fees extra. Final fare based on actual distance.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── City Card ── */
function CityCard({ city, onSelect }: { city: CityOption; onSelect: (cityValue: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(city.value)}
      className="bg-white/80 rounded-xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow p-4 flex items-center gap-3 text-left w-full"
    >
      <div className="shrink-0 w-10 h-10 rounded-full bg-green-50 flex items-center justify-center">
        <MapPin size={18} className="text-green-500" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-bold text-sm text-neutral-900">{city.label}</p>
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN SEARCH PAGE
═══════════════════════════════════════════════════════════════ */
export default function CabSearchClient() {
  const searchParams = useSearchParams();
  const router = useRouter();

  type CabSearchOverrides = Partial<Pick<CabSearchParams, 'city' | 'from' | 'to' | 'date' | 'category' | 'sort'>>;

  const todayStr = new Date().toISOString().split('T')[0];

  const [from, setFrom] = useState(searchParams.get('from') || '');
  const [to, setTo] = useState(searchParams.get('to') || '');
  const city = from || searchParams.get('city') || ''; // backward compat
  const [date, setDate] = useState(searchParams.get('date') || todayStr);
  const [category, setCategory] = useState(searchParams.get('category') || '');
  const [sort, setSort] = useState(searchParams.get('sort') || 'price');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(1);

  const [results, setResults] = useState<CabSearchResult | null>(null);
  const [cities, setCities] = useState<CityOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const hasSearched = !!city || !!from;

  // Load available cities
  useEffect(() => {
    getAvailableCities()
      .then((res) => setCities(Array.isArray(res) ? res : []))
      .catch(() => {});
  }, []);

  const doSearch = useCallback(async (p = 1, overrides: CabSearchOverrides = {}) => {
    const nextFrom = overrides.from ?? from;
    const nextTo = overrides.to ?? to;
    const nextCity = overrides.city || nextFrom || city;
    const nextDate = overrides.date ?? (date || undefined);
    const nextCategory = overrides.category ?? (category || undefined);
    const nextSort = (overrides.sort ?? sort) as CabSearchParams['sort'];

    if (!nextCity) return;
    setLoading(true);
    setError('');
    try {
      const params: CabSearchParams = {
        city: nextCity,
        from: nextFrom || undefined,
        to: nextTo || undefined,
        date: nextDate,
        category: nextCategory,
        sort: nextSort,
        page: p,
        per_page: 12,
      };
      const data = await searchCabs(params);
      setResults(data);
      setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to search cabs. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [city, from, to, date, category, sort]);

  useEffect(() => {
    if (hasSearched) doSearch(1);
  }, [sort, category]);

  useEffect(() => {
    if (searchParams.get('city') || searchParams.get('from')) doSearch(1);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (city && !from) params.set('city', city);
    if (date) params.set('date', date);
    if (category) params.set('category', category);
    if (sort) params.set('sort', sort);
    router.push(`/cabs?${params.toString()}`);
    doSearch(1);
  };

  const totalPages = results ? results.total_pages : 0;

  return (
    <div className="min-h-screen page-listing-bg">
      {/* ── Hero / Search Bar ── */}
      <section
        className="relative pt-24 pb-8"
        style={{ background: 'linear-gradient(135deg, #0f3460 0%, #1a1a2e 50%, #16213e 100%)' }}
      >
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse 70% 60% at 50% 110%, rgba(16,185,129,0.25) 0%, transparent 65%)',
            }}
          />
        </div>

        <div className="relative max-w-5xl mx-auto px-4">
          <h1 className="text-3xl sm:text-4xl font-black text-white mb-1 font-heading tracking-tight">
            Cab Bookings
          </h1>
          <p className="text-sm text-white/50 mb-6">
            Rent cabs, book airport transfers & outstation trips
          </p>

          <form
            onSubmit={handleSearch}
            className="bg-white/80 rounded-2xl shadow-xl p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3"
          >
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">From</label>
              <CityAutocomplete
                value={from}
                onChange={setFrom}
                placeholder="Pick-up city"
                icon={<MapPin size={16} />}
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">To</label>
              <CityAutocomplete
                value={to}
                onChange={setTo}
                placeholder="Drop-off city"
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
                className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Vehicle Type</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500 bg-white/80"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={!city}
                className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-white font-bold text-sm transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ background: 'var(--primary)' }}
              >
                <Search size={16} /> Search Cabs
              </button>
            </div>
          </form>
        </div>
      </section>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* ── No search: Available Cities ── */}
        {!hasSearched && !loading && (
          <>
            {cities.length > 0 && (
              <section>
                <h2 className="text-lg font-black text-neutral-900 mb-4 font-heading">Available Cities</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {cities.map((c, i) => (
                    <CityCard key={i} city={c} onSelect={(cityValue) => {
                      setFrom(cityValue);
                      const params = new URLSearchParams();
                      params.set('from', cityValue);
                      if (date) params.set('date', date);
                      if (sort) params.set('sort', sort);
                      router.push(`/cabs?${params.toString()}`);
                      doSearch(1, { city: cityValue, from: cityValue, date: date || undefined, sort: sort as CabSearchParams['sort'] });
                    }} />
                  ))}
                </div>
              </section>
            )}

            {cities.length === 0 && (
              <div className="text-center py-16">
                <div className="text-6xl mb-4">🚕</div>
                <h2 className="text-xl font-black text-neutral-900 mb-2">Search Cabs</h2>
                <p className="text-neutral-400 text-sm max-w-md mx-auto">
                  Enter a city above to find available cabs for rent.
                </p>
              </div>
            )}
          </>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div>
            <div className="flex items-center gap-2 text-neutral-500 text-sm mb-4">
              <Loader2 size={16} className="animate-spin" /> Searching cabs...
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <CabCardSkeleton key={i} />)}
            </div>
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
            <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
              <p className="text-sm text-neutral-500">
                <span className="font-bold text-neutral-900">{results.total}</span> cab{results.total !== 1 ? 's' : ''} in <span className="font-medium text-neutral-700">{city}</span>
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setFiltersOpen(true)}
                  className="flex lg:hidden items-center gap-1.5 text-sm border rounded-xl px-3 py-1.5 bg-white/80 text-neutral-700 border-neutral-200 hover:border-neutral-400 transition-colors"
                >
                  <SlidersHorizontal size={14} />
                  Filters
                  {category && <span className="w-1.5 h-1.5 rounded-full bg-green-500" />}
                </button>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-neutral-200 text-sm font-medium bg-white/80 focus:outline-none focus:ring-2 focus:ring-green-500/30"
                >
                  {SORT_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Desktop: Category filter chips */}
            <div className="hidden lg:flex items-center gap-2 mb-5 flex-wrap">
              {CATEGORIES.map((c) => (
                <button key={c.value} onClick={() => setCategory(category === c.value ? '' : c.value)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap ${
                    category === c.value
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400'
                  }`}>{c.label}</button>
              ))}
            </div>

            {/* Mobile filter bottom sheet */}
            {filtersOpen && (
              <>
                <div
                  className="lg:hidden fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
                  onClick={() => setFiltersOpen(false)}
                />
                <div className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white/80 rounded-t-3xl shadow-2xl max-h-[85vh] overflow-y-auto animate-slide-up">
                  <div className="sticky top-0 bg-white/80 z-10 px-5 pt-4 pb-3 border-b border-neutral-100 flex items-center justify-between">
                    <h3 className="font-bold text-neutral-900 text-base font-heading flex items-center gap-2">
                      <SlidersHorizontal size={16} /> Filters
                    </h3>
                    <div className="flex items-center gap-3">
                      {category && (
                        <button onClick={() => setCategory('')} className="text-xs text-red-500 font-semibold">
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
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Vehicle Category</p>
                      <div className="flex flex-wrap gap-1.5">
                        {CATEGORIES.filter(c => c.value).map((c) => (
                          <button key={c.value} onClick={() => setCategory(category === c.value ? '' : c.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              category === c.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{c.label}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Sort By</p>
                      <div className="flex flex-wrap gap-1.5">
                        {SORT_OPTIONS.map((s) => (
                          <button key={s.value} onClick={() => { setSort(s.value); setFiltersOpen(false); }}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              sort === s.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{s.label}</button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="sticky bottom-0 px-5 py-4 border-t border-neutral-100 bg-white/80">
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

            {/* Cab Cards */}
            {results.cabs.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.cabs.map((cab) => (
                  <CabCard key={cab.id} cab={cab} />
                ))}
              </div>
            ) : (
              <div className="text-center py-16">
                <div className="text-5xl mb-4">🔍</div>
                <h3 className="text-lg font-bold text-neutral-900 mb-1">No cabs found</h3>
                <p className="text-neutral-400 text-sm">Try a different city or date.</p>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => doSearch(page - 1)}
                  disabled={page <= 1}
                  className="px-4 py-2 rounded-xl border border-neutral-200 text-sm font-bold disabled:opacity-30 hover:bg-page transition-colors"
                >
                  ← Prev
                </button>
                <span className="text-sm text-neutral-500 tabular-nums">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => doSearch(page + 1)}
                  disabled={page >= totalPages}
                  className="px-4 py-2 rounded-xl border border-neutral-200 text-sm font-bold disabled:opacity-30 hover:bg-page transition-colors"
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
