'use client';

import { useRouter } from 'next/navigation';
import HotelCard from '@/components/hotels/HotelCard';
import GlobalSearchBar from '@/components/search/GlobalSearchBar';
import { useHotels } from '@/hooks/useHotels';
import { useState } from 'react';
import { SlidersHorizontal, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';

const SORT_OPTIONS = [
  { value: 'popular', label: 'Recommended' },
  { value: 'price_asc', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating', label: 'Highest Rated' },
];

interface CityLandingClientProps {
  location: string;
  cityName: string;
}

export default function CityLandingClient({ location, cityName }: CityLandingClientProps) {
  const router = useRouter();
  const [sort, setSort] = useState('popular');

  const { data, isLoading, isError } = useHotels({
    location: cityName,
    sort: sort as 'popular' | 'price_asc' | 'price_desc' | 'rating',
    page_size: 12,
  });

  return (
    <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
      {/* Compact search bar for refinement */}
      <div className="mb-6 bg-gradient-to-r from-primary-700 to-primary-900 rounded-2xl p-4">
        <GlobalSearchBar
          variant="inline"
          initialLocation={cityName}
        />
      </div>

      {/* Sort bar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-neutral-400" />
          <span className="text-xs font-bold text-neutral-500">Sort:</span>
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSort(opt.value)}
              className={clsx(
                'text-xs px-3 py-1.5 rounded-full border font-semibold transition-all',
                sort === opt.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-400'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {data?.pagination?.count != null && (
          <span className="text-sm text-neutral-400">
            {data.pagination.count.toLocaleString()} hotels
          </span>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-2xl overflow-hidden shadow-sm border flex h-[160px]">
              <div className="w-[200px] shrink-0 bg-neutral-100 animate-pulse" />
              <div className="flex-1 p-4 space-y-2">
                <div className="h-4 bg-neutral-100 rounded animate-pulse w-2/3" />
                <div className="h-3 bg-neutral-100 rounded animate-pulse w-1/2" />
                <div className="h-3 bg-neutral-100 rounded animate-pulse w-3/4 mt-4" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="text-center py-16 bg-white rounded-2xl shadow-card">
          <p className="text-4xl mb-4">⚠️</p>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">Failed to load hotels</h2>
          <button onClick={() => window.location.reload()} className="btn-primary mt-4">
            Try Again
          </button>
        </div>
      )}

      {/* Results */}
      {!isLoading && !isError && data && (
        <>
          {data.results.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl shadow-card">
              <p className="text-5xl mb-4">🔍</p>
              <h2 className="text-xl font-semibold text-neutral-900 mb-2">
                No hotels found in {cityName}
              </h2>
              <p className="text-neutral-500 mb-5">Try searching a different destination.</p>
            </div>
          ) : (
            <>
              {/* Horizontal cards need ≥540px — use 1-col / 2-col max */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {data.results.map((hotel) => (
                  <HotelCard key={hotel.id} hotel={hotel} location={cityName} />
                ))}
              </div>

              {/* View all link */}
              {(data.pagination?.count ?? 0) > 12 && (
                <div className="text-center mt-8">
                  <button
                    onClick={() => router.push(`/hotels?location=${encodeURIComponent(cityName)}`)}
                    className="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold text-primary-600 border border-primary-200 rounded-xl hover:bg-primary-50 transition-colors"
                  >
                    View all {data.pagination?.count?.toLocaleString()} hotels in {cityName}
                    <ChevronRight size={16} />
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
