'use client';
import { useState } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { SlidersHorizontal, X } from 'lucide-react';
import { clsx } from 'clsx';

const SORT_OPTIONS = [
  { value: 'popular', label: 'Popular' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'rating', label: 'Highest Rated' },
  { value: 'newest', label: 'Newest' },
];

const AMENITIES = ['WiFi', 'Pool', 'Parking', 'Gym', 'Spa', 'Restaurant', 'AC', 'Breakfast'];

const PROPERTY_TYPES = ['Hotel', 'Resort', 'Villa', 'Hostel', 'Apartment'];

interface FilterPanelProps {
  totalCount?: number;
}

export default function FilterPanel({ totalCount }: FilterPanelProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);

  const currentSort = searchParams.get('sort') || 'popular';
  const minPrice = searchParams.get('min_price') || '';
  const maxPrice = searchParams.get('max_price') || '';
  const freeCancellation = searchParams.get('free_cancellation') === 'true';

  const updateFilter = (key: string, value: string | boolean | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === null || value === '' || value === false) {
      params.delete(key);
    } else {
      params.set(key, String(value));
    }
    params.delete('page'); // reset pagination
    router.push(`${pathname}?${params.toString()}`);
  };

  const clearAllFilters = () => {
    const params = new URLSearchParams();
    const location = searchParams.get('location');
    const checkin = searchParams.get('checkin');
    const checkout = searchParams.get('checkout');
    if (location) params.set('location', location);
    if (checkin) params.set('checkin', checkin);
    if (checkout) params.set('checkout', checkout);
    router.push(`${pathname}?${params.toString()}`);
  };

  const hasActiveFilters = minPrice || maxPrice || freeCancellation ||
    searchParams.get('amenity') || searchParams.get('property_type');

  return (
    <div className="mb-4">
      {/* Sort bar + filter toggle */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          {totalCount !== undefined && (
            <span className="text-sm text-neutral-600 font-medium">
              {totalCount.toLocaleString()} properties found
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Sort selector */}
          <select
            value={currentSort}
            onChange={e => updateFilter('sort', e.target.value)}
            className="text-sm border border-neutral-200 rounded-lg px-3 py-1.5 bg-white text-neutral-700 outline-none focus:border-primary-400"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          {/* Filter toggle */}
          <button
            onClick={() => setOpen(!open)}
            className={clsx(
              'flex items-center gap-1.5 text-sm border rounded-lg px-3 py-1.5 transition-colors',
              open ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-neutral-700 border-neutral-200 hover:border-primary-300'
            )}
          >
            <SlidersHorizontal size={14} />
            Filters
            {hasActiveFilters && (
              <span className={clsx('w-2 h-2 rounded-full', open ? 'bg-white' : 'bg-primary-600')} />
            )}
          </button>

          {hasActiveFilters && (
            <button onClick={clearAllFilters} className="text-xs text-neutral-500 hover:text-neutral-800 flex items-center gap-1">
              <X size={12} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Expanded filter panel */}
      {open && (
        <div className="mt-3 bg-white rounded-xl border border-neutral-200 p-4 shadow-sm grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Price range */}
          <div>
            <p className="text-xs font-semibold text-neutral-600 uppercase mb-2">Price per night</p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Min"
                value={minPrice}
                onChange={e => updateFilter('min_price', e.target.value)}
                className="w-full text-sm border border-neutral-200 rounded-lg px-2 py-1.5 outline-none"
              />
              <span className="text-neutral-400 text-sm">–</span>
              <input
                type="number"
                placeholder="Max"
                value={maxPrice}
                onChange={e => updateFilter('max_price', e.target.value)}
                className="w-full text-sm border border-neutral-200 rounded-lg px-2 py-1.5 outline-none"
              />
            </div>
          </div>

          {/* Property type */}
          <div>
            <p className="text-xs font-semibold text-neutral-600 uppercase mb-2">Property type</p>
            <div className="flex flex-wrap gap-1.5">
              {PROPERTY_TYPES.map(type => {
                const active = searchParams.get('property_type') === type;
                return (
                  <button
                    key={type}
                    onClick={() => updateFilter('property_type', active ? null : type)}
                    className={clsx(
                      'text-xs px-2.5 py-1 rounded-full border transition-colors',
                      active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-neutral-700 border-neutral-200 hover:border-primary-300'
                    )}
                  >
                    {type}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Amenities */}
          <div>
            <p className="text-xs font-semibold text-neutral-600 uppercase mb-2">Amenities</p>
            <div className="flex flex-wrap gap-1.5">
              {AMENITIES.map(amenity => {
                const current = searchParams.getAll('amenity');
                const active = current.includes(amenity);
                return (
                  <button
                    key={amenity}
                    onClick={() => {
                      const params = new URLSearchParams(searchParams.toString());
                      const existing = params.getAll('amenity').filter(a => a !== amenity);
                      params.delete('amenity');
                      if (!active) existing.push(amenity);
                      existing.forEach(a => params.append('amenity', a));
                      router.push(`${pathname}?${params.toString()}`);
                    }}
                    className={clsx(
                      'text-xs px-2.5 py-1 rounded-full border transition-colors',
                      active ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-neutral-700 border-neutral-200 hover:border-primary-300'
                    )}
                  >
                    {amenity}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Cancellation */}
          <div>
            <p className="text-xs font-semibold text-neutral-600 uppercase mb-2">Cancellation</p>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={freeCancellation}
                onChange={e => updateFilter('free_cancellation', e.target.checked || null)}
                className="rounded border-neutral-300 text-primary-600"
              />
              <span className="text-sm text-neutral-700">Free cancellation only</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
