'use client';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { SlidersHorizontal, X } from 'lucide-react';
import { clsx } from 'clsx';
import PriceFilter from './PriceFilter';
import RatingFilter from './RatingFilter';
import AmenityFilter from './AmenityFilter';

const PROPERTY_TYPES = ['Hotel', 'Resort', 'Villa', 'Hostel', 'Apartment'];

interface FilterCounts {
  property_types?: Record<string, number>;
  amenities?: Record<string, number>;
  ratings?: Record<string, number>;
  user_ratings?: Record<string, number>;
  free_cancellation?: number;
  breakfast?: number;
  pay_at_hotel?: number;
}

interface FilterSidebarProps {
  filterCounts?: FilterCounts;
  className?: string;
}

/**
 * FilterSidebar — complete OTA-grade sidebar filter panel.
 * Composes PriceFilter, RatingFilter, AmenityFilter into a sticky sidebar.
 * URL-driven — all state lives in searchParams.
 */
export default function FilterSidebar({ filterCounts, className }: FilterSidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const updateParam = (key: string, value: string | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value === null || value === '') p.delete(key);
    else p.set(key, value);
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  const clearFilters = () => {
    const p = new URLSearchParams();
    // Preserve search context — not filters
    const keep = ['location', 'checkin', 'checkout', 'adults', 'children', 'rooms'];
    keep.forEach((k) => {
      const v = searchParams.get(k);
      if (v) p.set(k, v);
    });
    router.push(`${pathname}?${p.toString()}`);
  };

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
    <div className={clsx('bg-white rounded-2xl shadow-card p-5 sticky top-24', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-neutral-900 text-sm flex items-center gap-2">
          <SlidersHorizontal size={14} />
          Filters
        </h3>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-red-500 hover:text-red-700 font-medium flex items-center gap-1"
          >
            <X size={11} /> Clear all
          </button>
        )}
      </div>

      {/* Price */}
      <PriceFilter filterCounts={filterCounts?.property_types} />

      {/* Property Type */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Property Type
        </h4>
        <div className="space-y-2">
          {PROPERTY_TYPES.map((type) => {
            const active = searchParams.get('property_type') === type;
            const cnt = filterCounts?.property_types?.[type] ?? filterCounts?.property_types?.[type.toLowerCase()];
            return (
              <label key={type} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => updateParam('property_type', active ? null : type)}
                  className="rounded border-neutral-300 text-primary-600 accent-primary-600"
                />
                <span className={clsx(
                  'text-sm flex-1',
                  active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900'
                )}>
                  {type}
                </span>
                {cnt != null && (
                  <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">{cnt}</span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* Amenities */}
      <AmenityFilter filterCounts={filterCounts?.amenities} />

      {/* Star & Guest Rating */}
      <RatingFilter filterCounts={{
        ratings: filterCounts?.ratings,
        user_ratings: filterCounts?.user_ratings,
      }} />

      {/* Popular Filters */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Popular Filters
        </h4>
        <label className="flex items-center gap-2.5 cursor-pointer group">
          <input
            type="checkbox"
            checked={searchParams.get('free_cancellation') === 'true'}
            onChange={(e) => updateParam('free_cancellation', e.target.checked ? 'true' : null)}
            className="rounded border-neutral-300 accent-primary-600"
          />
          <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">
            Free Cancellation
          </span>
          {filterCounts?.free_cancellation != null && (
            <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">
              {filterCounts.free_cancellation}
            </span>
          )}
        </label>
        <label className="flex items-center gap-2.5 cursor-pointer group">
          <input
            type="checkbox"
            checked={searchParams.get('breakfast_included') === 'true'}
            onChange={(e) => updateParam('breakfast_included', e.target.checked ? 'true' : null)}
            className="rounded border-neutral-300 accent-primary-600"
          />
          <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">
            Breakfast Included
          </span>
          {filterCounts?.breakfast != null && (
            <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">
              {filterCounts.breakfast}
            </span>
          )}
        </label>
        <label className="flex items-center gap-2.5 cursor-pointer group">
          <input
            type="checkbox"
            checked={searchParams.get('pay_at_hotel') === 'true'}
            onChange={(e) => updateParam('pay_at_hotel', e.target.checked ? 'true' : null)}
            className="rounded border-neutral-300 accent-primary-600"
          />
          <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 flex-1">
            Pay at Hotel
          </span>
          {filterCounts?.pay_at_hotel != null && (
            <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">
              {filterCounts.pay_at_hotel}
            </span>
          )}
        </label>
      </div>
    </div>
  );
}
