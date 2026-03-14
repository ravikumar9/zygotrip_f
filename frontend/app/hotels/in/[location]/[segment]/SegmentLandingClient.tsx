'use client';

import { useRouter } from 'next/navigation';
import HotelCard from '@/components/hotels/HotelCard';
import GlobalSearchBar from '@/components/search/GlobalSearchBar';
import { useHotels } from '@/hooks/useHotels';
import { useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { clsx } from 'clsx';

const SORT_OPTIONS = [
  { value: 'popular', label: 'Recommended' },
  { value: 'price_asc', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating', label: 'Highest Rated' },
];

interface SegmentLandingClientProps {
  location: string;
  cityName: string;
  segmentSlug: string;
  segmentLabel: string;
  segmentFilter: Record<string, string | number | boolean>;
}

export default function SegmentLandingClient({
  location,
  cityName,
  segmentSlug,
  segmentLabel,
  segmentFilter,
}: SegmentLandingClientProps) {
  const router = useRouter();
  const defaultSort = (segmentFilter.sort as string) || 'popular';
  const [sort, setSort] = useState(defaultSort);

  const { data, isLoading, isError } = useHotels({
    location: cityName,
    sort: sort as 'popular' | 'price_asc' | 'price_desc' | 'rating',
    page_size: 12,
    // Pass segment-specific filters
    ...(segmentFilter.max_price && { max_price: segmentFilter.max_price as number }),
    ...(segmentFilter.min_price && { min_price: segmentFilter.min_price as number }),
    ...(segmentFilter.star_rating && { star_rating: segmentFilter.star_rating as number }),
    ...(segmentFilter.amenities && { amenities: segmentFilter.amenities as string }),
    ...(segmentFilter.free_cancellation && { free_cancellation: true }),
    ...(segmentFilter.near && { near: segmentFilter.near as string }),
  });

  return (
    <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
      {/* Compact search bar */}
      <div className="mb-6 bg-gradient-to-r from-primary-700 to-primary-900 rounded-2xl p-4">
        <GlobalSearchBar variant="inline" initialLocation={cityName} />
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
                'text-xs px-3 py-1.5 rounded-full border transition-colors',
                sort === opt.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'text-neutral-500 border-neutral-200 hover:border-primary-300',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {data?.pagination?.count != null && (
          <span className="text-xs text-neutral-400 font-medium">
            {data.pagination.count.toLocaleString()} {segmentLabel.toLowerCase()} found
          </span>
        )}
      </div>

      {/* Error state */}
      {isError && (
        <div className="text-center py-16">
          <p className="text-neutral-500">
            Unable to load {segmentLabel.toLowerCase()}. Please try again.
          </p>
        </div>
      )}

      {/* Hotel grid — horizontal cards need ≥540px, so max 2-col */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 pb-10">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl overflow-hidden shadow-sm border flex h-[160px]">
                <div className="w-[200px] shrink-0 bg-neutral-100 animate-pulse" />
                <div className="flex-1 p-4 space-y-2">
                  <div className="h-4 bg-neutral-100 rounded animate-pulse w-2/3" />
                  <div className="h-3 bg-neutral-100 rounded animate-pulse w-1/2" />
                  <div className="h-3 bg-neutral-100 rounded animate-pulse w-3/4 mt-4" />
                </div>
              </div>
            ))
          : data?.results?.map((hotel: any) => (
              <HotelCard
                key={hotel.id}
                hotel={hotel}
                location={cityName}
              />
            ))}
      </div>

      {/* No results */}
      {!isLoading && data?.results?.length === 0 && (
        <div className="text-center py-16">
          <p className="text-lg font-semibold text-neutral-700">
            No {segmentLabel.toLowerCase()} found in {cityName}
          </p>
          <p className="text-neutral-400 mt-2">Try adjusting your dates or filters.</p>
          <button
            onClick={() => router.push(`/hotels/in/${location}`)}
            className="mt-4 text-sm text-primary-600 hover:underline"
          >
            View all hotels in {cityName} →
          </button>
        </div>
      )}
    </div>
  );
}
