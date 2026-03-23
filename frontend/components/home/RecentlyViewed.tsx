'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Clock, Star, ChevronRight, X } from 'lucide-react';
import { personalization, type RecentlyViewedHotel } from '@/lib/personalization';
import { useFormatPrice } from '@/hooks/useFormatPrice';

/**
 * RecentlyViewed — displays recently viewed hotels.
 * Data comes from localStorage via personalization engine.
 * Shows nothing for first-time visitors (no history).
 */
export default function RecentlyViewed() {
  const { formatPrice } = useFormatPrice();
  const [hotels, setHotels] = useState<RecentlyViewedHotel[]>([]);

  useEffect(() => {
    const recent = personalization.getRecentlyViewed();
    if (recent.length > 0) setHotels(recent);
  }, []);

  if (hotels.length === 0) return null;

  return (
    <section className="py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-primary-500" />
            <h2 className="text-lg font-bold text-neutral-900">Recently Viewed</h2>
          </div>
          <button
            onClick={() => {
              personalization.clearRecentlyViewed();
              setHotels([]);
            }}
            className="text-xs text-neutral-400 hover:text-red-500 flex items-center gap-1 transition-colors"
          >
            <X size={12} /> Clear
          </button>
        </div>

        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
          {hotels.slice(0, 6).map((hotel) => (
            <Link
              key={hotel.id}
              href={`/hotels/${hotel.slug}`}
              className="flex-shrink-0 w-48 bg-white/80 rounded-xl border border-neutral-100 overflow-hidden hover:shadow-md transition-shadow group"
            >
              <div className="relative h-28 bg-neutral-100">
                {hotel.image ? (
                  <Image
                    src={hotel.image}
                    alt={hotel.name}
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-300"
                    sizes="192px"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-2xl">🏨</div>
                )}
              </div>
              <div className="p-2.5">
                <p className="text-xs font-bold text-neutral-900 truncate">{hotel.name}</p>
                <p className="text-2xs text-neutral-400 truncate">{hotel.city}</p>
                <div className="flex items-center justify-between mt-1.5">
                  {hotel.rating && (
                    <div className="flex items-center gap-0.5 text-2xs text-amber-600">
                      <Star size={10} fill="currentColor" />
                      {hotel.rating}
                    </div>
                  )}
                  {hotel.price && (
                    <span className="text-xs font-bold text-primary-600">
                      {formatPrice(hotel.price)}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}

          {/* View all link */}
          {hotels.length > 6 && (
            <div className="flex-shrink-0 w-32 flex items-center justify-center">
              <span className="text-xs text-primary-600 font-semibold flex items-center gap-1">
                +{hotels.length - 6} more
                <ChevronRight size={12} />
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
