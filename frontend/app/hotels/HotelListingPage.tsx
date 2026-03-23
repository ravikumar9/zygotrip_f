'use client';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import GlobalSearchBar from '@/components/search/GlobalSearchBar';
import HotelCard from '@/components/hotels/HotelCard';
import { SlidersHorizontal, X, ChevronLeft, ChevronRight, MapPin, Loader2 } from 'lucide-react';
import { useHotels, useInfiniteHotels } from '@/hooks/useHotels';
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll';
import { useState, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { listHotels } from '@/services/hotels';
import { clsx } from 'clsx';
import type { HotelSearchParams } from '@/types';
import type { FilterCounts, PopularArea } from '@/services/hotels';
import { analytics } from '@/lib/analytics';
import ApiErrorState from '@/components/ui/ApiErrorState';

const SORT_OPTIONS = [
  { value: 'popular',       label: 'Recommended' },
  { value: 'price_asc',     label: 'Price: Low → High' },
  { value: 'price_desc',    label: 'Price: High → Low' },
  { value: 'rating',        label: 'Highest Rated' },
  { value: 'best_reviewed', label: 'Best Reviewed' },
  { value: 'newest',        label: 'Newest First' },
];

const AMENITIES  = ['WiFi', 'Pool', 'Parking', 'Gym', 'Spa', 'Restaurant', 'AC', 'Breakfast'];
const PROP_TYPES = ['Hotel', 'Resort', 'Villa', 'Hostel', 'Apartment'];
const STAR_OPTS  = [5, 4, 3, 2];

// Goibibo-style predefined price buckets
const PRICE_BUCKETS = [
  { label: '₹0 – ₹1,000',    min: '',     max: '1000'  },
  { label: '₹1k – ₹2k',      min: '1000', max: '2000'  },
  { label: '₹2k – ₹3k',      min: '2000', max: '3000'  },
  { label: '₹3k – ₹5k',      min: '3000', max: '5000'  },
  { label: '₹5k – ₹10k',     min: '5000', max: '10000' },
  { label: '₹10,000+',        min: '10000', max: ''     },
];

// ── Skeleton for loading state ──────────────────────────────────────
function HotelCardSkeleton() {
  return (
    <div className="bg-white/80 rounded-2xl overflow-hidden shadow-card border border-neutral-100 flex flex-col sm:flex-row">
      <div className="skeleton sm:w-[240px] h-52 sm:h-auto sm:min-h-[210px] shrink-0" />
      <div className="flex-1 p-4 space-y-3">
        <div className="skeleton h-3 w-20 rounded" />
        <div className="skeleton h-5 w-3/4 rounded" />
        <div className="skeleton h-3 w-1/2 rounded" />
        <div className="flex gap-1">
          <div className="skeleton h-5 w-12 rounded-full" />
          <div className="skeleton h-5 w-12 rounded-full" />
          <div className="skeleton h-5 w-16 rounded-full" />
        </div>
      </div>
      <div className="sm:w-[180px] shrink-0 p-4 space-y-2 flex flex-col items-end justify-center">
        <div className="skeleton h-4 w-16 rounded" />
        <div className="skeleton h-6 w-20 rounded" />
        <div className="skeleton h-9 w-28 rounded-xl" />
      </div>
    </div>
  );
}

// Filter count badge
function CountBadge({ count }: { count?: number }) {
  if (count == null) return null;
  return (
    <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">{count}</span>
  );
}

export default function HotelListingPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [showMap, setShowMap] = useState(false);

  // Support both ?location= and ?city= query params (city used in footer/API, location in search bar)
  const location  = searchParams.get('location') || searchParams.get('city') || '';
  const checkin   = searchParams.get('checkin') || undefined;
  const checkout  = searchParams.get('checkout') || undefined;
  const adults    = searchParams.get('adults') || undefined;
  const children  = searchParams.get('children') || undefined;
  const rooms     = searchParams.get('rooms') || undefined;
  const currentSort = searchParams.get('sort') || 'popular';

  // Params WITHOUT page — infinite scroll handles pagination
  const params: Omit<HotelSearchParams, 'page'> = {
    location:            location || undefined,
    checkin,
    checkout,
    adults:              searchParams.get('adults')    ? Number(searchParams.get('adults'))    : undefined,
    min_price:           searchParams.get('min_price') ? Number(searchParams.get('min_price')) : undefined,
    max_price:           searchParams.get('max_price') ? Number(searchParams.get('max_price')) : undefined,
    sort:                (currentSort as HotelSearchParams['sort']),
    free_cancellation:   searchParams.get('free_cancellation') === 'true' || undefined,
    breakfast_included:  searchParams.get('breakfast_included') === 'true' || undefined,
    pay_at_hotel:        searchParams.get('pay_at_hotel') === 'true' || undefined,
    stars:               searchParams.get('stars') ? Number(searchParams.get('stars')) : undefined,
    user_rating:         searchParams.get('user_rating') ? Number(searchParams.get('user_rating')) : undefined,
    property_type:       searchParams.get('property_type') || undefined,
    amenity:             searchParams.getAll('amenity').length ? searchParams.getAll('amenity') : undefined,
    page_size:           20,
  };

  const {
    data,
    error,
    isLoading,
    isError,
    isFetching,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteHotels(params);

  // Flatten all pages into a single array of hotels
  const allHotels = useMemo(
    () => data?.pages.flatMap((page) => page.results) ?? [],
    [data]
  );

  // First page metadata for filter counts, popular areas, total count
  const firstPage = data?.pages[0];
  const fc = firstPage?.filter_counts as FilterCounts | undefined;
  const popularAreas = firstPage?.popular_areas as PopularArea[] | undefined;
  const totalCount = firstPage?.pagination?.count;

  // Infinite scroll sentinel
  const sentinelRef = useInfiniteScroll({
    onIntersect: () => fetchNextPage(),
    enabled: !!hasNextPage && !isFetchingNextPage,
  });

  // Track filter/sort changes
  useEffect(() => {
    if (currentSort !== 'popular') {
      analytics.track('sort_changed', { sort: currentSort, location });
    }
  }, [currentSort, location]);

  const queryClient = useQueryClient();

  const updateParam = (key: string, value: string | boolean | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value === null || value === '' || value === false) p.delete(key);
    else p.set(key, String(value));
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
    analytics.track('filter_applied', { filter: key, value: String(value ?? ''), location });
  };

  const toggleAmenity = (amenity: string) => {
    const p = new URLSearchParams(searchParams.toString());
    const all = p.getAll('amenity');
    p.delete('amenity');
    if (all.includes(amenity)) {
      all.filter((a) => a !== amenity).forEach((a) => p.append('amenity', a));
    } else {
      [...all, amenity].forEach((a) => p.append('amenity', a));
    }
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  const clearFilters = () => {
    const p = new URLSearchParams();
    if (location)  p.set('location', location);
    if (checkin)   p.set('checkin', checkin);
    if (checkout)  p.set('checkout', checkout);
    // Always preserve guest/room counts — they are search context, not filters
    if (adults)    p.set('adults', adults);
    if (children)  p.set('children', children);
    if (rooms)     p.set('rooms', rooms);
    router.push(`${pathname}?${p.toString()}`);
  };

  // Set a price bucket (replaces any existing min_price/max_price)
  const applyPriceBucket = (min: string, max: string) => {
    const p = new URLSearchParams(searchParams.toString());
    if (min) p.set('min_price', min); else p.delete('min_price');
    if (max) p.set('max_price', max); else p.delete('max_price');
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  const activeBucket = PRICE_BUCKETS.find(
    (b) => (b.min || '') === (searchParams.get('min_price') || '') &&
           (b.max || '') === (searchParams.get('max_price') || '')
  );

  const hasActiveFilters =
    searchParams.get('min_price') ||
    searchParams.get('max_price') ||
    searchParams.get('free_cancellation') ||
    searchParams.get('breakfast_included') ||
    searchParams.get('pay_at_hotel') ||
    searchParams.get('user_rating') ||
    searchParams.get('stars') ||
    searchParams.get('amenity') ||
    searchParams.get('property_type');

  return (
    <div className="page-listing-bg">

      {/* ── Vibrant navy search hero band (Goibibo-parity) ───── */}
      <div className="search-hero-band">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <GlobalSearchBar
            variant="inline"
            initialLocation={location}
            initialCheckin={checkin}
            initialCheckout={checkout}
            initialGuests={adults ? Number(adults) : 2}
          />
        </div>
      </div>

      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-5">

        {/* ── Page title ────────────────────────────────────────── */}
        {location && (
          <div className="mb-3">
            <h1 className="text-2xl font-black text-neutral-900 font-heading">
              Hotels in <span className="text-primary-600">{location}</span>
            </h1>
            {totalCount !== undefined && (
              <p className="text-sm text-neutral-500 mt-0.5">
                {totalCount.toLocaleString()} properties found
                {checkin && checkout ? ` · ${checkin} → ${checkout}` : ''}
              </p>
            )}
          </div>
        )}

        {/* ── Popular Locations chips (Goibibo-parity) ─────────── */}
        {popularAreas && popularAreas.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <MapPin size={11} />
              Popular Locations{location ? ` in ${location}` : ''}
            </p>
            <div className="flex flex-wrap gap-2">
              {popularAreas.map((area) => {
                const isActive = searchParams.get('location') === area.area;
                return (
                  <button
                    key={area.area}
                    onClick={() => updateParam('location', isActive ? (location || null) : area.area)}
                    className={clsx(
                      'text-xs rounded-xl px-3 py-1.5 font-semibold border transition-all',
                      isActive
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white/80 text-neutral-700 border-neutral-200 hover:border-primary-400 hover:text-primary-700'
                    )}
                  >
                    {area.area}
                    <span className={clsx('ml-1', isActive ? 'text-primary-100' : 'text-neutral-400')}>
                      {area.count} stays
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex gap-6">
          {/* ── Left sidebar (Filters) ─────────────────────────── */}
          <aside className="w-64 shrink-0 hidden lg:block">
            <div className="bg-white/80 rounded-2xl shadow-card p-5 sticky top-24">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-neutral-900 text-sm">Filters</h3>
                {hasActiveFilters && (
                  <button onClick={clearFilters} className="text-xs text-red-500 hover:text-red-700 font-medium flex items-center gap-1">
                    <X size={11} /> Clear all
                  </button>
                )}
              </div>

              {/* ── Price Buckets (Goibibo-style ranges) ─────────── */}
              <div className="mb-5 pb-5 border-b border-neutral-100">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Price per night</h4>
                <div className="space-y-1.5">
                  {PRICE_BUCKETS.map((bucket) => {
                    const active = activeBucket?.label === bucket.label;
                    return (
                      <label key={bucket.label} className="flex items-center gap-2.5 cursor-pointer group">
                        <input
                          type="radio"
                          name="price_bucket"
                          checked={active}
                          onChange={() => active
                            ? (() => { updateParam('min_price', null); updateParam('max_price', null); })()
                            : applyPriceBucket(bucket.min, bucket.max)
                          }
                          className="accent-primary-600"
                        />
                        <span className={clsx('text-sm flex-1', active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900')}>
                          {bucket.label}
                        </span>
                      </label>
                    );
                  })}
                </div>
                {/* Still allow custom range */}
                <div className="flex items-center gap-2 mt-3">
                  <input
                    type="number"
                    placeholder="Min ₹"
                    value={searchParams.get('min_price') || ''}
                    onChange={(e) => updateParam('min_price', e.target.value)}
                    className="w-full text-xs border border-neutral-200 rounded-lg px-2 py-1.5 outline-none focus:border-primary-400"
                  />
                  <span className="text-neutral-400 text-xs">—</span>
                  <input
                    type="number"
                    placeholder="Max ₹"
                    value={searchParams.get('max_price') || ''}
                    onChange={(e) => updateParam('max_price', e.target.value)}
                    className="w-full text-xs border border-neutral-200 rounded-lg px-2 py-1.5 outline-none focus:border-primary-400"
                  />
                </div>
              </div>

              {/* ── Property Type ─────────────────────────────────── */}
              <div className="mb-5 pb-5 border-b border-neutral-100">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Property Type</h4>
                <div className="space-y-2">
                  {PROP_TYPES.map((type) => {
                    const active = searchParams.get('property_type') === type;
                    const cnt = fc?.property_types?.[type] ?? fc?.property_types?.[type.toLowerCase()];
                    return (
                      <label key={type} className="flex items-center gap-2.5 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => updateParam('property_type', active ? null : type)}
                          className="rounded border-neutral-300 text-primary-600 accent-primary-600"
                        />
                        <span className={clsx('text-sm flex-1', active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900')}>
                          {type}
                        </span>
                        <CountBadge count={cnt} />
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* ── Amenities ─────────────────────────────────────── */}
              <div className="mb-5 pb-5 border-b border-neutral-100">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Amenities</h4>
                <div className="space-y-2">
                  {AMENITIES.map((amenity) => {
                    const active = searchParams.getAll('amenity').includes(amenity);
                    const cnt = fc?.amenities?.[amenity] ?? fc?.amenities?.[amenity.toLowerCase()];
                    return (
                      <label key={amenity} className="flex items-center gap-2.5 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => toggleAmenity(amenity)}
                          className="rounded border-neutral-300 text-primary-600 accent-primary-600"
                        />
                        <span className={clsx('text-sm flex-1', active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900')}>
                          {amenity}
                        </span>
                        <CountBadge count={cnt} />
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* ── Star Rating ───────────────────────────────────── */}
              <div className="mb-5 pb-5 border-b border-neutral-100">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Star Rating</h4>
                <div className="space-y-2">
                  {STAR_OPTS.map((stars) => {
                    const active = searchParams.get('stars') === String(stars);
                    const countKey = stars === 5 ? 'rating_5' : `rating_${stars}plus`;
                    const cnt = fc?.ratings?.[countKey];
                    return (
                      <label key={stars} className="flex items-center gap-2.5 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => updateParam('stars', active ? null : String(stars))}
                          className="rounded border-neutral-300 accent-primary-600"
                        />
                        <span className="text-sm text-neutral-700 flex-1">
                          {'★'.repeat(stars)}{stars === 5 ? ' Luxury' : ''}
                        </span>
                        <CountBadge count={cnt} />
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* ── Guest Rating ──────────────────────────────────── */}
              <div className="mb-5 pb-5 border-b border-neutral-100">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Guest Rating</h4>
                <div className="space-y-2">
                  {[
                    { value: '4.5', label: '4.5+ Exceptional', countKey: 'rating_4_5plus' },
                    { value: '4',   label: '4.0+ Very Good',   countKey: 'rating_4_0plus' },
                    { value: '3.5', label: '3.5+ Good',         countKey: 'rating_3_5plus' },
                  ].map(({ value, label, countKey }) => {
                    const active = searchParams.get('user_rating') === value;
                    const cnt = fc?.user_ratings?.[countKey];
                    return (
                      <label key={value} className="flex items-center gap-2.5 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => updateParam('user_rating', active ? null : value)}
                          className="rounded border-neutral-300 accent-primary-600"
                        />
                        <span className={clsx('text-sm flex-1', active ? 'text-primary-700 font-semibold' : 'text-neutral-700')}>
                          {label}
                        </span>
                        <CountBadge count={cnt} />
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* ── Popular Filters ───────────────────────────────── */}
              <div className="space-y-2.5">
                <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">Popular Filters</h4>
                <label className="flex items-center gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={searchParams.get('free_cancellation') === 'true'}
                    onChange={(e) => updateParam('free_cancellation', e.target.checked ? 'true' : null)}
                    className="rounded border-neutral-300 accent-primary-600"
                  />
                  <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">Free Cancellation</span>
                  <CountBadge count={fc?.free_cancellation} />
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={searchParams.get('breakfast_included') === 'true'}
                    onChange={(e) => updateParam('breakfast_included', e.target.checked ? 'true' : null)}
                    className="rounded border-neutral-300 accent-primary-600"
                  />
                  <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">Breakfast Included</span>
                  <CountBadge count={fc?.breakfast} />
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={searchParams.get('pay_at_hotel') === 'true'}
                    onChange={(e) => updateParam('pay_at_hotel', e.target.checked ? 'true' : null)}
                    className="rounded border-neutral-300 accent-primary-600"
                  />
                  <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">Pay at Hotel</span>
                  <CountBadge count={fc?.pay_at_hotel} />
                </label>
              </div>
            </div>
          </aside>

          {/* ── Main content ────────────────────────────────────── */}
          <div className="flex-1 min-w-0">

            {/* ── Sort pills + mobile filters ─────────────────── */}
            <div className="mb-4">
              {/* Desktop: horizontal pill row */}
              <div className="hidden lg:flex items-center gap-2 flex-wrap">
                <span className="text-xs font-bold text-neutral-500 shrink-0 mr-1">Sort:</span>
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => updateParam('sort', opt.value)}
                    className={clsx(
                      'text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap',
                      currentSort === opt.value
                        ? 'bg-primary-600 text-white border-primary-600 shadow-sm'
                        : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400 hover:text-primary-600'
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
                {totalCount !== undefined && (
                  <span className="ml-auto text-sm text-neutral-400 font-medium shrink-0 mr-2">
                    {totalCount.toLocaleString()} results
                  </span>
                )}
                <button
                  onClick={() => setShowMap(!showMap)}
                  className={clsx(
                    'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-semibold transition-all whitespace-nowrap',
                    showMap
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400 hover:text-primary-600'
                  )}
                >
                  <MapPin size={12} />
                  {showMap ? 'Hide Map' : 'Map'}
                </button>
              </div>

              {/* Mobile: filter toggle + select dropdown */}
              <div className="flex lg:hidden items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setFiltersOpen(!filtersOpen)}
                    className={clsx(
                      'flex items-center gap-1.5 text-sm border rounded-xl px-3 py-1.5 transition-colors',
                      filtersOpen
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white/80 text-neutral-700 border-neutral-200'
                    )}
                  >
                    <SlidersHorizontal size={14} />
                    Filters
                    {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
                  </button>
                  {hasActiveFilters && (
                    <button onClick={clearFilters} className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1">
                      <X size={11} /> Clear
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {totalCount !== undefined && (
                    <span className="text-sm text-neutral-500 hidden sm:block">
                      {totalCount.toLocaleString()} results
                    </span>
                  )}
                  <select
                    value={currentSort}
                    onChange={(e) => updateParam('sort', e.target.value)}
                    className="text-sm border border-neutral-200 rounded-xl px-3 py-1.5 bg-white/80 text-neutral-700 outline-none focus:border-primary-400"
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Mobile filter bottom sheet */}
            {filtersOpen && (
              <>
                {/* Backdrop */}
                <div
                  className="lg:hidden fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
                  onClick={() => setFiltersOpen(false)}
                />
                {/* Bottom sheet panel */}
                <div className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white/80 rounded-t-3xl shadow-2xl max-h-[85vh] overflow-y-auto animate-slide-up">
                  <div className="sticky top-0 bg-white/80 z-10 px-5 pt-4 pb-3 border-b border-neutral-100 flex items-center justify-between">
                    <h3 className="font-bold text-neutral-900 text-base font-heading flex items-center gap-2">
                      <SlidersHorizontal size={16} /> Filters
                    </h3>
                    <div className="flex items-center gap-3">
                      {hasActiveFilters && (
                        <button onClick={clearFilters} className="text-xs text-red-500 font-semibold">
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
                  <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Price</p>
                  <div className="flex flex-wrap gap-1.5">
                    {PRICE_BUCKETS.map((bucket) => {
                      const active = activeBucket?.label === bucket.label;
                      return (
                        <button key={bucket.label}
                          onClick={() => active
                            ? (() => { updateParam('min_price', null); updateParam('max_price', null); })()
                            : applyPriceBucket(bucket.min, bucket.max)
                          }
                          className={clsx('text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px]',
                            active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200')}>
                          {bucket.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Property Type</p>
                  <div className="flex flex-wrap gap-1.5">
                    {PROP_TYPES.map((type) => {
                      const active = searchParams.get('property_type') === type;
                      return (
                        <button key={type} onClick={() => updateParam('property_type', active ? null : type)}
                          className={clsx('text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px]', active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200')}>
                          {type}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Amenities</p>
                  <div className="flex flex-wrap gap-1.5">
                    {AMENITIES.map((amenity) => {
                      const active = searchParams.getAll('amenity').includes(amenity);
                      return (
                        <button key={amenity} onClick={() => toggleAmenity(amenity)}
                          className={clsx('text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px]', active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200')}>
                          {amenity}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
                    <input type="checkbox" checked={searchParams.get('free_cancellation') === 'true'}
                      onChange={(e) => updateParam('free_cancellation', e.target.checked ? 'true' : null)}
                      className="rounded border-neutral-300 accent-primary-600 w-5 h-5" />
                    <span className="text-sm text-neutral-700 font-medium">Free Cancellation</span>
                    {fc?.free_cancellation != null && <span className="text-xs text-neutral-400 ml-auto">{fc.free_cancellation}</span>}
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
                    <input type="checkbox" checked={searchParams.get('breakfast_included') === 'true'}
                      onChange={(e) => updateParam('breakfast_included', e.target.checked ? 'true' : null)}
                      className="rounded border-neutral-300 accent-primary-600 w-5 h-5" />
                    <span className="text-sm text-neutral-700 font-medium">Breakfast Included</span>
                    {fc?.breakfast != null && <span className="text-xs text-neutral-400 ml-auto">{fc.breakfast}</span>}
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
                    <input type="checkbox" checked={searchParams.get('pay_at_hotel') === 'true'}
                      onChange={(e) => updateParam('pay_at_hotel', e.target.checked ? 'true' : null)}
                      className="rounded border-neutral-300 accent-primary-600 w-5 h-5" />
                    <span className="text-sm text-neutral-700 font-medium">Pay at Hotel</span>
                  </label>
                </div>
                <div>
                  <p className="text-xs font-bold text-neutral-500 uppercase mb-2">Guest Rating</p>
                  <div className="flex flex-wrap gap-1.5">
                    {[{ v: '4.5', l: '4.5+' }, { v: '4', l: '4.0+' }, { v: '3.5', l: '3.5+' }].map(({ v, l }) => {
                      const active = searchParams.get('user_rating') === v;
                      return (
                        <button key={v} onClick={() => updateParam('user_rating', active ? null : v)}
                          className={clsx('text-sm px-3 py-2 rounded-xl border transition-colors min-h-[40px]', active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white/80 text-neutral-700 border-neutral-200')}>
                          {l}
                        </button>
                      );
                    })}
                  </div>
                </div>
                  </div>
                  {/* Sticky apply button */}
                  <div className="sticky bottom-0 bg-white/80 border-t border-neutral-100 px-5 py-3">
                    <button
                      onClick={() => setFiltersOpen(false)}
                      className="btn-primary w-full py-3 text-sm"
                    >
                      Show {totalCount?.toLocaleString() ?? ''} Results
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* ── Loading state ──────────────────────────────────── */}
            {isLoading && (
              <div className="grid grid-cols-1 gap-4">
                {Array.from({ length: 6 }).map((_, i) => <HotelCardSkeleton key={i} />)}
              </div>
            )}

            {/* ── Error state with auto-retry ───────────────────── */}
            {isError && (
              <div className="bg-white/80 rounded-2xl shadow-card p-6">
                <ApiErrorState
                  error={error instanceof Error ? error : null}
                  onRetry={() => refetch()}
                  autoRetrySeconds={15}
                />
              </div>
            )}

            {/* ── Results grid — infinite scroll ───────────────────── */}
            {!isLoading && !isError && data && (
              <>
                {allHotels.length === 0 ? (
                  <div className="text-center py-16 bg-white/80 rounded-2xl shadow-card">
                    <p className="text-5xl mb-4">🔍</p>
                    <h2 className="text-xl font-semibold text-neutral-900 mb-2">No hotels found</h2>
                    <p className="text-neutral-500 mb-5">
                      Try different dates, adjust your budget, or search another city.
                    </p>
                    <button onClick={clearFilters} className="btn-secondary">
                      Clear all filters
                    </button>
                  </div>
                ) : (
                  <>
                    {isFetching && !isFetchingNextPage && (
                      <div className="text-center py-2 text-xs text-neutral-400 mb-2">
                        Updating results...
                      </div>
                    )}

                    <div className="grid grid-cols-1 gap-4">
                      {allHotels.map((hotel, index) => (
                        <div key={hotel.id} style={{ contentVisibility: 'auto', containIntrinsicSize: '0 220px' }}>
                          <HotelCard
                            hotel={hotel}
                            position={index + 1}
                            checkin={checkin}
                            checkout={checkout}
                            adults={adults}
                            rooms={rooms}
                            location={location}
                          />
                        </div>
                      ))}
                    </div>

                    {/* Infinite scroll sentinel + loading indicator */}
                    <div ref={sentinelRef} className="h-4" />
                    {isFetchingNextPage && (
                      <div className="flex items-center justify-center gap-2 py-6">
                        <Loader2 size={18} className="animate-spin text-primary-500" />
                        <span className="text-sm text-neutral-500">Loading more hotels…</span>
                      </div>
                    )}
                    {!hasNextPage && allHotels.length > 0 && (
                      <p className="text-center text-xs text-neutral-400 py-6">
                        You&apos;ve seen all {totalCount?.toLocaleString()} hotels
                      </p>
                    )}
                  </>
                )}
              </>
            )}
          </div>

          {/* ── Right panel: Map (toggleable 3rd zone) ─────────── */}
          {showMap && (
            <aside className="w-80 shrink-0 hidden xl:block">
              <div className="bg-white/80 rounded-2xl shadow-card sticky top-24 overflow-hidden" style={{ height: 'calc(100vh - 120px)' }}>
                <div className="p-4 border-b border-neutral-100">
                  <h3 className="text-sm font-bold text-neutral-900 flex items-center gap-2">
                    <MapPin size={14} className="text-primary-500" />
                    Hotels on Map
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">{allHotels.length} properties</p>
                </div>
                <div className="h-full bg-page flex flex-col items-center justify-center p-6 text-center">
                  <div className="w-16 h-16 rounded-full bg-primary-50 flex items-center justify-center mb-3">
                    <MapPin size={24} className="text-primary-500" />
                  </div>
                  <p className="text-sm font-semibold text-neutral-700 mb-1">Map View</p>
                  <p className="text-xs text-neutral-400 leading-relaxed">
                    Interactive map with hotel pins coming soon.
                    {location && <> Currently showing hotels in <strong>{location}</strong>.</>}
                  </p>
                  {allHotels.length > 0 && (
                    <div className="mt-4 w-full space-y-2 max-h-[50vh] overflow-y-auto">
                      {allHotels.slice(0, 10).map((h) => (
                        <div key={h.id} className="flex items-center gap-2 text-left bg-white/80 rounded-lg p-2 border border-neutral-100">
                          <div className="w-6 h-6 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
                            <span className="text-[10px] font-bold text-primary-600">📍</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-neutral-800 truncate">{h.name}</p>
                            <p className="text-[10px] text-neutral-400">{h.area || h.city_name}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}