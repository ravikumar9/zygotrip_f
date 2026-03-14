'use client';

import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { SlidersHorizontal, X, Plane, Clock, IndianRupee } from 'lucide-react';
import { clsx } from 'clsx';

const STOPS_OPTIONS = [
  { value: '0', label: 'Non-stop' },
  { value: '1', label: '1 Stop' },
  { value: '2', label: '2+ Stops' },
];

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];

const DEPARTURE_TIMES = [
  { value: 'early_morning', label: 'Early Morning', range: '00:00 - 06:00' },
  { value: 'morning', label: 'Morning', range: '06:00 - 12:00' },
  { value: 'afternoon', label: 'Afternoon', range: '12:00 - 18:00' },
  { value: 'evening', label: 'Evening', range: '18:00 - 00:00' },
];

const PRICE_RANGES = [
  { value: '0-3000', label: 'Under ₹3,000' },
  { value: '3000-5000', label: '₹3,000 - ₹5,000' },
  { value: '5000-8000', label: '₹5,000 - ₹8,000' },
  { value: '8000-15000', label: '₹8,000 - ₹15,000' },
  { value: '15000-999999', label: '₹15,000+' },
];

interface FlightFilterCounts {
  airlines?: Record<string, number>;
  stops?: Record<string, number>;
}

interface FlightFilterSidebarProps {
  airlines?: string[];
  filterCounts?: FlightFilterCounts;
  className?: string;
}

export default function FlightFilterSidebar({
  airlines = [],
  filterCounts,
  className,
}: FlightFilterSidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const updateParam = (key: string, value: string | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value === null || value === '') p.delete(key);
    else p.set(key, value);
    router.push(`${pathname}?${p.toString()}`);
  };

  const toggleMultiParam = (key: string, value: string) => {
    const p = new URLSearchParams(searchParams.toString());
    const current = p.get(key)?.split(',').filter(Boolean) || [];
    const idx = current.indexOf(value);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(value);
    if (current.length === 0) p.delete(key);
    else p.set(key, current.join(','));
    router.push(`${pathname}?${p.toString()}`);
  };

  const isInMultiParam = (key: string, value: string) => {
    return (searchParams.get(key)?.split(',') || []).includes(value);
  };

  const clearFilters = () => {
    const p = new URLSearchParams();
    ['origin', 'destination', 'departure_date', 'return_date', 'adults', 'trip_type'].forEach((k) => {
      const v = searchParams.get(k);
      if (v) p.set(k, v);
    });
    router.push(`${pathname}?${p.toString()}`);
  };

  const hasActiveFilters =
    searchParams.get('max_stops') ||
    searchParams.get('airlines') ||
    searchParams.get('departure_time') ||
    searchParams.get('price_range') ||
    searchParams.get('cabin_class');

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

      {/* Stops */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Stops
        </h4>
        <div className="space-y-2">
          {STOPS_OPTIONS.map(({ value, label }) => {
            const active = searchParams.get('max_stops') === value;
            const cnt = filterCounts?.stops?.[value];
            return (
              <label key={value} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="radio"
                  name="stops"
                  checked={active}
                  onChange={() => updateParam('max_stops', active ? null : value)}
                  className="accent-primary-600"
                />
                <span className={clsx(
                  'text-sm flex-1',
                  active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900'
                )}>
                  {label}
                </span>
                {cnt != null && (
                  <span className="text-xs text-neutral-400 tabular-nums">{cnt}</span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* Price Range */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3 flex items-center gap-1">
          <IndianRupee size={11} /> Price Range
        </h4>
        <div className="space-y-2">
          {PRICE_RANGES.map(({ value, label }) => {
            const active = searchParams.get('price_range') === value;
            return (
              <label key={value} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="radio"
                  name="price_range"
                  checked={active}
                  onChange={() => updateParam('price_range', active ? null : value)}
                  className="accent-primary-600"
                />
                <span className={clsx(
                  'text-sm flex-1',
                  active ? 'text-primary-700 font-semibold' : 'text-neutral-700'
                )}>
                  {label}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Departure Time */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3 flex items-center gap-1">
          <Clock size={11} /> Departure Time
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {DEPARTURE_TIMES.map(({ value, label, range }) => {
            const active = isInMultiParam('departure_time', value);
            return (
              <button
                key={value}
                onClick={() => toggleMultiParam('departure_time', value)}
                className={clsx(
                  'text-center p-2 rounded-lg border text-xs transition-colors',
                  active
                    ? 'border-primary-500 bg-primary-50 text-primary-700 font-semibold'
                    : 'border-neutral-200 text-neutral-600 hover:border-neutral-300'
                )}
              >
                <div className="font-medium">{label}</div>
                <div className="text-[10px] text-neutral-400 mt-0.5">{range}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Airlines */}
      {airlines.length > 0 && (
        <div className="mb-5 pb-5 border-b border-neutral-100">
          <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3 flex items-center gap-1">
            <Plane size={11} /> Airlines
          </h4>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {airlines.map((airline) => {
              const active = isInMultiParam('airlines', airline);
              const cnt = filterCounts?.airlines?.[airline];
              return (
                <label key={airline} className="flex items-center gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => toggleMultiParam('airlines', airline)}
                    className="rounded border-neutral-300 accent-primary-600"
                  />
                  <span className={clsx(
                    'text-sm flex-1',
                    active ? 'text-primary-700 font-semibold' : 'text-neutral-700'
                  )}>
                    {airline}
                  </span>
                  {cnt != null && (
                    <span className="text-xs text-neutral-400 tabular-nums">{cnt}</span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Cabin Class */}
      <div>
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Cabin Class
        </h4>
        <div className="space-y-2">
          {CABIN_CLASSES.map((cabin) => {
            const active = searchParams.get('cabin_class') === cabin;
            const label = cabin.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
            return (
              <label key={cabin} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="radio"
                  name="cabin_class"
                  checked={active}
                  onChange={() => updateParam('cabin_class', active ? null : cabin)}
                  className="accent-primary-600"
                />
                <span className={clsx(
                  'text-sm flex-1',
                  active ? 'text-primary-700 font-semibold' : 'text-neutral-700'
                )}>
                  {label}
                </span>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
