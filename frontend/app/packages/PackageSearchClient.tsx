'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search, MapPin, Clock, Star, ArrowRight, Loader2, Users, SlidersHorizontal, X } from 'lucide-react';
import { searchPackages, getPopularDestinations, getPackageCategories } from '@/services/packages';
import CityAutocomplete from '@/components/search/CityAutocomplete';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type {
  TravelPackage, PackageSearchParams, PackageSearchResult,
  PackageCategory, PackageDestination,
} from '@/types/packages';

const DURATION_OPTIONS = [
  { value: '', label: 'Any Duration' },
  { value: '1-3', label: '1-3 Days' },
  { value: '4-6', label: '4-6 Days' },
  { value: '7-10', label: '7-10 Days' },
  { value: '10-30', label: '10+ Days' },
];

const BUDGET_OPTIONS = [
  { value: '', label: 'Any Budget' },
  { value: '0-10000', label: 'Under ₹10,000' },
  { value: '10000-25000', label: '₹10,000 – ₹25,000' },
  { value: '25000-50000', label: '₹25,000 – ₹50,000' },
  { value: '50000-500000', label: '₹50,000+' },
];

const DIFFICULTY_OPTIONS = [
  { value: '', label: 'All Levels' },
  { value: 'easy', label: 'Easy' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'challenging', label: 'Challenging' },
];

const SORT_OPTIONS = [
  { value: 'popular', label: 'Most Popular' },
  { value: 'price', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating', label: 'Highest Rated' },
  { value: 'duration', label: 'Shortest First' },
];

const difficultyColor: Record<string, string> = {
  easy: 'bg-green-50 text-green-600',
  moderate: 'bg-amber-50 text-amber-600',
  challenging: 'bg-red-50 text-red-600',
};

/* ── Skeleton ── */
function PackageCardSkeleton() {
  return (
    <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm overflow-hidden animate-pulse">
      <div className="h-52 bg-neutral-100" />
      <div className="p-4 space-y-3">
        <div className="h-4 bg-neutral-100 rounded w-1/3" />
        <div className="h-5 bg-neutral-100 rounded w-3/4" />
        <div className="h-3 bg-neutral-100 rounded w-1/2" />
        <div className="flex justify-between items-end">
          <div className="h-6 bg-neutral-100 rounded w-24" />
          <div className="h-9 bg-neutral-100 rounded-xl w-24" />
        </div>
      </div>
    </div>
  );
}

/* ── Package Card ── */
function PackageCard({ pkg }: { pkg: TravelPackage }) {
  const { formatPrice } = useFormatPrice();
  return (
    <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow overflow-hidden group">
      {/* Image */}
      <div className="relative h-52 bg-neutral-100 overflow-hidden">
        {pkg.image_url ? (
          <img
            src={pkg.image_url}
            alt={pkg.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl">🌴</div>
        )}
        {/* Duration badge */}
        <span className="absolute top-3 left-3 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-white/80/90 backdrop-blur-sm text-neutral-700 shadow-sm inline-flex items-center gap-1">
          <Clock size={10} /> {pkg.duration_days} Day{pkg.duration_days !== 1 ? 's' : ''}
        </span>
        {/* Difficulty badge */}
        {pkg.difficulty_level && (
          <span className={`absolute top-3 right-3 text-[10px] font-bold px-2.5 py-1 rounded-full ${difficultyColor[pkg.difficulty_level] || 'bg-neutral-100 text-neutral-600'}`}>
            {pkg.difficulty_level.charAt(0).toUpperCase() + pkg.difficulty_level.slice(1)}
          </span>
        )}
      </div>

      <div className="p-4">
        {/* Category + Destination */}
        <div className="flex items-center gap-2 mb-1">
          {pkg.category && (
            <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">{pkg.category}</span>
          )}
          <span className="text-[10px] text-neutral-300">·</span>
          <span className="text-[10px] font-medium text-neutral-400 inline-flex items-center gap-0.5">
            <MapPin size={10} /> {pkg.destination}
          </span>
        </div>

        {/* Name */}
        <h3 className="font-bold text-neutral-900 text-sm leading-tight mb-2 line-clamp-2">{pkg.name}</h3>

        {/* Rating */}
        <div className="flex items-center gap-2 mb-2">
          {pkg.rating > 0 && (
            <span className="inline-flex items-center gap-0.5 text-xs font-bold text-amber-600">
              <Star size={12} fill="currentColor" /> {pkg.rating.toFixed(1)}
            </span>
          )}
          {pkg.review_count > 0 && (
            <span className="text-[10px] text-neutral-400">({pkg.review_count} reviews)</span>
          )}
          {pkg.max_group_size > 0 && (
            <span className="inline-flex items-center gap-0.5 text-[10px] text-neutral-400 ml-auto">
              <Users size={10} /> Max {pkg.max_group_size}
            </span>
          )}
        </div>

        {/* Inclusions */}
        {pkg.inclusions_summary && pkg.inclusions_summary.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {pkg.inclusions_summary.slice(0, 4).map((inc) => (
              <span key={inc} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">
                {inc}
              </span>
            ))}
          </div>
        )}

        {/* Price + CTA */}
        <div className="flex items-end justify-between pt-2 border-t border-neutral-100">
          <div>
            <p className="text-xl font-black text-neutral-900">{formatPrice(pkg.base_price)}</p>
            <p className="text-[10px] text-neutral-400">per person</p>
          </div>
          <Link
            href={`/packages/${pkg.slug}`}
            className="inline-flex items-center gap-1 px-4 py-2 rounded-xl text-white text-sm font-bold transition-opacity hover:opacity-90"
            style={{ background: 'var(--primary)' }}
          >
            View <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Destination Card ── */
function DestinationCard({ dest, onSelect }: { dest: PackageDestination; onSelect: (destination: string) => void }) {
  const { formatPrice } = useFormatPrice();
  return (
    <button
      type="button"
      onClick={() => onSelect(dest.destination)}
      className="bg-white/80 rounded-xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow p-4 flex items-center gap-3 text-left w-full"
    >
      <div className="shrink-0 w-10 h-10 rounded-full bg-purple-50 flex items-center justify-center">
        <MapPin size={18} className="text-purple-500" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-bold text-sm text-neutral-900">{dest.destination}</p>
        <p className="text-xs text-neutral-400">
          from {formatPrice(dest.avg_price)} · ★ {dest.avg_rating.toFixed(1)}
        </p>
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN SEARCH PAGE
═══════════════════════════════════════════════════════════════ */
export default function PackageSearchClient() {
  const searchParams = useSearchParams();
  const router = useRouter();

  type PackageSearchOverrides = Partial<Pick<PackageSearchParams, 'destination' | 'category' | 'duration' | 'budget' | 'difficulty' | 'sort'>>;

  const [destination, setDestination] = useState(searchParams.get('destination') || '');
  const [categorySlug, setCategorySlug] = useState(searchParams.get('category') || '');
  const [duration, setDuration] = useState(searchParams.get('duration') || '');
  const [budget, setBudget] = useState(searchParams.get('budget') || '');
  const [difficulty, setDifficulty] = useState(searchParams.get('difficulty') || '');
  const [sort, setSort] = useState(searchParams.get('sort') || 'popular');
  const [page, setPage] = useState(1);

  const [results, setResults] = useState<PackageSearchResult | null>(null);
  const [destinations, setDestinations] = useState<PackageDestination[]>([]);
  const [categories, setCategories] = useState<PackageCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const hasActiveFilters = !!(duration || budget || difficulty || categorySlug);
  const hasSearched = !!(destination || categorySlug || duration || budget || difficulty);

  // Load destinations + categories on mount
  useEffect(() => {
    Promise.allSettled([
      getPopularDestinations().then((r) => setDestinations(Array.isArray(r) ? r : [])),
      getPackageCategories().then((r) => setCategories(Array.isArray(r) ? r : [])),
    ]);
  }, []);

  const doSearch = useCallback(async (p = 1, overrides: PackageSearchOverrides = {}) => {
    setLoading(true);
    setError('');
    try {
      const nextDestination = overrides.destination ?? (destination || undefined);
      const nextCategory = overrides.category ?? (categorySlug || undefined);
      const nextDuration = overrides.duration ?? (duration || undefined);
      const nextBudget = overrides.budget ?? (budget || undefined);
      const nextDifficulty = overrides.difficulty ?? (difficulty || undefined);
      const nextSort = (overrides.sort ?? sort) as PackageSearchParams['sort'];

      const params: PackageSearchParams = {
        destination: nextDestination,
        category: nextCategory,
        duration: nextDuration,
        budget: nextBudget,
        difficulty: nextDifficulty,
        sort: nextSort,
        page: p,
        per_page: 12,
      };
      const data = await searchPackages(params);
      setResults(data);
      setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to search packages. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [destination, categorySlug, duration, budget, difficulty, sort]);

  useEffect(() => {
    if (hasSearched) doSearch(1);
  }, [sort]);

  useEffect(() => {
    if (searchParams.get('destination') || searchParams.get('category')) {
      doSearch(1);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (destination) params.set('destination', destination);
    if (categorySlug) params.set('category', categorySlug);
    if (duration) params.set('duration', duration);
    if (budget) params.set('budget', budget);
    if (difficulty) params.set('difficulty', difficulty);
    if (sort) params.set('sort', sort);
    router.push(`/packages?${params.toString()}`);
    doSearch(1);
  };

  const totalPages = results ? results.total_pages : 0;
  const categoryOptions = [{ value: '', label: 'All Categories' }, ...categories.map((c) => ({ value: c.slug, label: c.name }))];

  return (
    <div className="min-h-screen page-listing-bg">
      {/* ── Hero / Search Bar ── */}
      <section
        className="relative pt-24 pb-8"
        style={{ background: 'linear-gradient(135deg, #16213e 0%, #1a1a2e 40%, #0f3460 100%)' }}
      >
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse 70% 60% at 50% 110%, rgba(168,85,247,0.25) 0%, transparent 65%)',
            }}
          />
        </div>

        <div className="relative max-w-5xl mx-auto px-4">
          <h1 className="text-3xl sm:text-4xl font-black text-white mb-1 font-heading tracking-tight">
            Holiday Packages
          </h1>
          <p className="text-sm text-white/50 mb-6">
            Curated travel packages — hotels, transport & experiences included
          </p>

          <form
            onSubmit={handleSearch}
            className="bg-white/80 rounded-2xl shadow-xl p-4 sm:p-5"
          >
            {/* Primary row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Destination</label>
                <CityAutocomplete
                  value={destination}
                  onChange={setDestination}
                  placeholder="Where do you want to go?"
                  citiesOnly={false}
                  icon={<MapPin size={16} />}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Category</label>
                <select
                  value={categorySlug}
                  onChange={(e) => setCategorySlug(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 bg-white/80"
                >
                  {categoryOptions.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Duration</label>
                <select
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 bg-white/80"
                >
                  {DURATION_OPTIONS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <button
                  type="submit"
                  className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-white font-bold text-sm transition-opacity hover:opacity-90"
                  style={{ background: 'var(--primary)' }}
                >
                  <Search size={16} /> Search Packages
                </button>
              </div>
            </div>

            {/* Toggle filter row */}
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="text-xs font-bold text-neutral-400 hover:text-neutral-600 transition-colors"
            >
              {showFilters ? '− Hide Filters' : '+ More Filters'}
            </button>

            {showFilters && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-neutral-100">
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Budget</label>
                  <select
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 bg-white/80"
                  >
                    {BUDGET_OPTIONS.map((b) => (
                      <option key={b.value} value={b.value}>{b.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 mb-1 block">Difficulty</label>
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-neutral-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 bg-white/80"
                  >
                    {DIFFICULTY_OPTIONS.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </form>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* ── No search: Destinations + Categories ── */}
        {!hasSearched && !loading && (
          <>
            {/* Categories */}
            {categories.length > 0 && (
              <section className="mb-10">
                <h2 className="text-lg font-black text-neutral-900 mb-4 font-heading">Browse by Category</h2>
                <div className="flex flex-wrap gap-2">
                  {categories.map((cat) => (
                    <button
                      key={cat.slug}
                      onClick={() => { setCategorySlug(cat.slug); doSearch(1, { category: cat.slug }); }}
                      className="px-4 py-2 rounded-full border border-neutral-200 text-sm font-medium text-neutral-700 hover:border-purple-300 hover:text-purple-600 hover:bg-purple-50 transition-colors"
                    >
                      {cat.name}
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* Popular destinations */}
            {destinations.length > 0 && (
              <section>
                <h2 className="text-lg font-black text-neutral-900 mb-4 font-heading">Popular Destinations</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {destinations.map((d, i) => (
                    <DestinationCard key={i} dest={d} onSelect={(dest) => {
                      setDestination(dest);
                      const params = new URLSearchParams();
                      params.set('destination', dest);
                      if (sort) params.set('sort', sort);
                      router.push(`/packages?${params.toString()}`);
                      doSearch(1, { destination: dest, sort: sort as PackageSearchParams['sort'] });
                    }} />
                  ))}
                </div>
              </section>
            )}

            {destinations.length === 0 && categories.length === 0 && (
              <div className="text-center py-16">
                <div className="text-6xl mb-4">🌴</div>
                <h2 className="text-xl font-black text-neutral-900 mb-2">Explore Holiday Packages</h2>
                <p className="text-neutral-400 text-sm max-w-md mx-auto">
                  Search by destination, category, or budget above to find your perfect trip.
                </p>
              </div>
            )}
          </>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div>
            <div className="flex items-center gap-2 text-neutral-500 text-sm mb-4">
              <Loader2 size={16} className="animate-spin" /> Searching packages...
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <PackageCardSkeleton key={i} />)}
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
                <span className="font-bold text-neutral-900">{results.total}</span> package{results.total !== 1 ? 's' : ''} found
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setMobileFiltersOpen(true)}
                  className="flex lg:hidden items-center gap-1.5 text-sm border rounded-xl px-3 py-1.5 bg-white/80 text-neutral-700 border-neutral-200 hover:border-neutral-400 transition-colors"
                >
                  <SlidersHorizontal size={14} />
                  Filters
                  {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />}
                </button>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-neutral-200 text-sm font-medium bg-white/80 focus:outline-none focus:ring-2 focus:ring-purple-500/30"
                >
                  {SORT_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Mobile filter bottom sheet */}
            {mobileFiltersOpen && (
              <>
                <div
                  className="lg:hidden fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
                  onClick={() => setMobileFiltersOpen(false)}
                />
                <div className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white/80 rounded-t-3xl shadow-2xl max-h-[85vh] overflow-y-auto animate-slide-up">
                  <div className="sticky top-0 bg-white/80 z-10 px-5 pt-4 pb-3 border-b border-neutral-100 flex items-center justify-between">
                    <h3 className="font-bold text-neutral-900 text-base font-heading flex items-center gap-2">
                      <SlidersHorizontal size={16} /> Filters
                    </h3>
                    <div className="flex items-center gap-3">
                      {hasActiveFilters && (
                        <button onClick={() => { setDuration(''); setBudget(''); setDifficulty(''); setCategorySlug(''); }} className="text-xs text-red-500 font-semibold">
                          Clear All
                        </button>
                      )}
                      <button
                        onClick={() => setMobileFiltersOpen(false)}
                        className="w-8 h-8 flex items-center justify-center rounded-full bg-neutral-100 hover:bg-neutral-200 transition-colors"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="p-5 space-y-5">
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Duration</p>
                      <div className="flex flex-wrap gap-1.5">
                        {DURATION_OPTIONS.filter(d => d.value).map((d) => (
                          <button key={d.value} onClick={() => setDuration(duration === d.value ? '' : d.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              duration === d.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{d.label}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Budget</p>
                      <div className="flex flex-wrap gap-1.5">
                        {BUDGET_OPTIONS.filter(b => b.value).map((b) => (
                          <button key={b.value} onClick={() => setBudget(budget === b.value ? '' : b.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              budget === b.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{b.label}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Difficulty</p>
                      <div className="flex flex-wrap gap-1.5">
                        {DIFFICULTY_OPTIONS.filter(d => d.value).map((d) => (
                          <button key={d.value} onClick={() => setDifficulty(difficulty === d.value ? '' : d.value)}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              difficulty === d.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{d.label}</button>
                        ))}
                      </div>
                    </div>
                    {categories.length > 0 && (
                      <div>
                        <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Category</p>
                        <div className="flex flex-wrap gap-1.5">
                          {categories.map((cat) => (
                            <button key={cat.slug} onClick={() => setCategorySlug(categorySlug === cat.slug ? '' : cat.slug)}
                              className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                                categorySlug === cat.slug ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                              }`}>{cat.name}</button>
                          ))}
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Sort By</p>
                      <div className="flex flex-wrap gap-1.5">
                        {SORT_OPTIONS.map((s) => (
                          <button key={s.value} onClick={() => { setSort(s.value); setMobileFiltersOpen(false); doSearch(1, { sort: s.value as PackageSearchParams['sort'] }); }}
                            className={`text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px] ${
                              sort === s.value ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200'
                            }`}>{s.label}</button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="sticky bottom-0 px-5 py-4 border-t border-neutral-100 bg-white/80">
                    <button
                      onClick={() => { setMobileFiltersOpen(false); doSearch(1); }}
                      className="w-full py-3 rounded-xl font-bold text-white text-sm"
                      style={{ background: 'var(--primary)' }}
                    >
                      Show Results
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* Desktop: Quick filter chips: duration + budget */}
            <div className="hidden lg:flex items-center gap-2 mb-5 flex-wrap">
              <span className="text-xs font-bold text-neutral-400 shrink-0">Duration:</span>
              {DURATION_OPTIONS.filter(d => d.value).map((d) => (
                <button key={d.value} onClick={() => {
                  const nextDuration = duration === d.value ? '' : d.value;
                  setDuration(nextDuration);
                  doSearch(1, { duration: nextDuration || undefined });
                }}
                  className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap ${
                    duration === d.value
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400'
                  }`}>{d.label}</button>
              ))}
              <span className="text-neutral-200 mx-1">|</span>
              <span className="text-xs font-bold text-neutral-400 shrink-0">Budget:</span>
              {BUDGET_OPTIONS.filter(b => b.value).map((b) => (
                <button key={b.value} onClick={() => {
                  const nextBudget = budget === b.value ? '' : b.value;
                  setBudget(nextBudget);
                  doSearch(1, { budget: nextBudget || undefined });
                }}
                  className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap ${
                    budget === b.value
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400'
                  }`}>{b.label}</button>
              ))}
            </div>

            {/* Package Cards */}
            {results.packages.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.packages.map((pkg) => (
                  <PackageCard key={pkg.id} pkg={pkg} />
                ))}
              </div>
            ) : (
              <div className="text-center py-16">
                <div className="text-5xl mb-4">🔍</div>
                <h3 className="text-lg font-bold text-neutral-900 mb-1">No packages found</h3>
                <p className="text-neutral-400 text-sm">Try different filters or destination.</p>
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
