'use client';

/**
 * High-Conversion Hotel Card — Goibibo/MakeMyTrip parity.
 *
 * Conversion signals:
 *   - "Only X rooms left" urgency badge
 *   - "Y bookings today" social proof
 *   - Discount percentage + strikethrough price
 *   - Deal score badge
 *   - "Free breakfast" tag
 *   - "Free cancellation" tag
 *   - Cashback amount
 *   - Star rating + review count
 *   - Distance to center / landmark
 *   - Wishlist (favourite) toggle
 *   - Blur-hash image placeholder + lazy loading
 *   - Skeleton loading variant
 *   - Click analytics (booking funnel tracking)
 */
import Image from 'next/image';
import Link from 'next/link';
import { useCallback, useState } from 'react';
import { bookingFunnel } from '@/lib/analytics';
import { useFormatPrice } from '@/hooks/useFormatPrice';

export interface HotelCardConversionProps {
  id: number;
  slug: string;
  name: string;
  city: string;
  area: string;
  rating: string | number;
  reviewCount: number;
  starCategory: number;
  minPrice: number;
  rackPrice?: number;
  primaryImage?: string;
  amenities?: string[];
  hasFreeCancellation?: boolean;
  payAtHotel?: boolean;
  isTrending?: boolean;

  // Conversion signals
  roomsLeft?: number;
  recentBookings?: number;
  discountPercentage?: number;
  dealScore?: number;
  hasBreakfast?: boolean;
  cashbackAmount?: number;

  // Location & distance
  distanceToCenter?: number; // km
  nearestLandmark?: string;
  landmarkDistance?: number; // km

  // Wishlist
  isWishlisted?: boolean;
  onToggleWishlist?: (hotelId: number) => void;

  // Position in list (for analytics)
  listPosition?: number;
}

/* ── Skeleton / Loading State ─────────────────────────────────── */

export function HotelCardSkeleton() {
  return (
    <div className="block bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden animate-pulse">
      <div className="flex flex-col sm:flex-row">
        <div className="w-full sm:w-64 h-48 sm:h-52 bg-gray-200 flex-shrink-0" />
        <div className="flex-1 p-4 space-y-3">
          <div className="flex justify-between">
            <div className="space-y-2 flex-1">
              <div className="h-5 bg-gray-200 rounded w-3/4" />
              <div className="h-3 bg-gray-200 rounded w-1/2" />
            </div>
            <div className="h-8 w-12 bg-gray-200 rounded-lg" />
          </div>
          <div className="flex gap-2">
            <div className="h-5 w-24 bg-gray-200 rounded" />
            <div className="h-5 w-28 bg-gray-200 rounded" />
          </div>
          <div className="h-3 bg-gray-200 rounded w-2/3" />
          <div className="flex justify-between items-end pt-3 border-t border-gray-100">
            <div className="h-4 w-20 bg-gray-200 rounded" />
            <div className="space-y-1 text-right">
              <div className="h-3 w-16 bg-gray-200 rounded ml-auto" />
              <div className="h-7 w-24 bg-gray-200 rounded ml-auto" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main Card ────────────────────────────────────────────────── */

export default function HotelCardConversion({
  id,
  slug,
  name,
  city,
  area,
  rating,
  reviewCount,
  starCategory,
  minPrice,
  rackPrice,
  primaryImage,
  amenities = [],
  hasFreeCancellation = false,
  payAtHotel = false,
  isTrending = false,
  roomsLeft,
  recentBookings,
  discountPercentage,
  dealScore,
  hasBreakfast = false,
  cashbackAmount,
  distanceToCenter,
  nearestLandmark,
  landmarkDistance,
  isWishlisted = false,
  onToggleWishlist,
  listPosition,
}: HotelCardConversionProps) {
  const { formatPrice } = useFormatPrice();
  const numRating = typeof rating === 'string' ? parseFloat(rating) : rating;
  const ratingTier = numRating >= 4.5 ? 'Excellent' : numRating >= 4.0 ? 'Very Good' : numRating >= 3.5 ? 'Good' : 'Average';
  const hasDiscount = discountPercentage && discountPercentage > 0 && rackPrice && rackPrice > minPrice;

  const [imageLoaded, setImageLoaded] = useState(false);

  /* Analytics: track hotel card click → hotel_page_viewed funnel stage */
  const handleCardClick = useCallback(() => {
    bookingFunnel.enter('hotel_page_viewed', {
      hotel_id: id,
      hotel_name: name,
      city,
      price: minPrice,
      position: listPosition ?? 0,
      has_discount: !!hasDiscount,
      rating: numRating,
    });
  }, [id, name, city, minPrice, listPosition, hasDiscount, numRating]);

  /* Wishlist toggle (stop event propagation so Link doesn't fire) */
  const handleWishlistClick = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      onToggleWishlist?.(id);
    },
    [id, onToggleWishlist],
  );

  return (
    <Link
      href={`/hotels/${slug}`}
      onClick={handleCardClick}
      className="group block bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-lg hover:border-gray-200 transition-all duration-200 overflow-hidden"
    >
      <div className="flex flex-col sm:flex-row">
        {/* Image section */}
        <div className="relative w-full sm:w-64 h-48 sm:h-auto flex-shrink-0">
          {/* Blur placeholder behind image */}
          {!imageLoaded && (
            <div className="absolute inset-0 bg-gradient-to-br from-gray-200 to-gray-300 animate-pulse" />
          )}
          <Image
            src={primaryImage || '/img/placeholder-hotel.jpg'}
            alt={name}
            fill
            className={`object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            sizes="(max-width: 640px) 100vw, 256px"
            loading="lazy"
            onLoad={() => setImageLoaded(true)}
          />

          {/* Badges overlay */}
          <div className="absolute top-2 left-2 flex flex-col gap-1.5">
            {isTrending && (
              <span className="px-2.5 py-1 bg-orange-500 text-white text-xs font-bold rounded-lg shadow-sm">
                🔥 Trending
              </span>
            )}
            {dealScore && dealScore >= 80 && (
              <span className="px-2.5 py-1 bg-green-600 text-white text-xs font-bold rounded-lg shadow-sm">
                Great Deal
              </span>
            )}
            {hasDiscount && (
              <span className="px-2.5 py-1 bg-red-500 text-white text-xs font-bold rounded-lg shadow-sm">
                {Math.round(discountPercentage)}% OFF
              </span>
            )}
          </div>

          {/* Wishlist / Favourite button */}
          {onToggleWishlist && (
            <button
              onClick={handleWishlistClick}
              aria-label={isWishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
              className="absolute top-2 right-2 p-1.5 bg-white/80 hover:bg-white rounded-full shadow-sm backdrop-blur-sm transition"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                className={`w-5 h-5 transition ${isWishlisted ? 'fill-red-500 text-red-500' : 'fill-none text-gray-600 hover:text-red-400'}`}
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"
                />
              </svg>
            </button>
          )}

          {/* Urgency badge */}
          {roomsLeft !== undefined && roomsLeft > 0 && roomsLeft <= 5 && (
            <div className="absolute bottom-2 left-2 px-2.5 py-1 bg-red-600/90 text-white text-xs font-bold rounded-lg backdrop-blur-sm">
              Only {roomsLeft} room{roomsLeft > 1 ? 's' : ''} left!
            </div>
          )}
        </div>

        {/* Content section */}
        <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
          <div>
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-gray-900 truncate group-hover:text-blue-600 transition">
                  {name}
                </h3>
                <p className="text-sm text-gray-500 truncate">
                  {area && `${area}, `}{city}
                  {starCategory > 0 && (
                    <span className="ml-2">
                      {'★'.repeat(starCategory)}
                    </span>
                  )}
                </p>

                {/* Distance / Landmark info */}
                {(distanceToCenter || nearestLandmark) && (
                  <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                    </svg>
                    {distanceToCenter !== undefined && (
                      <span>{distanceToCenter < 1 ? `${Math.round(distanceToCenter * 1000)}m` : `${distanceToCenter.toFixed(1)} km`} from center</span>
                    )}
                    {nearestLandmark && landmarkDistance !== undefined && (
                      <span className="ml-1">· {landmarkDistance < 1 ? `${Math.round(landmarkDistance * 1000)}m` : `${landmarkDistance.toFixed(1)} km`} to {nearestLandmark}</span>
                    )}
                  </p>
                )}
              </div>

              {/* Rating badge */}
              {numRating > 0 && (
                <div className="flex-shrink-0 text-right">
                  <div className={`
                    inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-bold text-white
                    ${numRating >= 4.5 ? 'bg-green-600' : numRating >= 4.0 ? 'bg-green-500' : numRating >= 3.5 ? 'bg-yellow-500' : 'bg-gray-400'}
                  `}>
                    {numRating.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {ratingTier} · {reviewCount} reviews
                  </div>
                </div>
              )}
            </div>

            {/* Tags row */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {hasBreakfast && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 text-xs font-medium rounded-md border border-green-200">
                  🍳 Free Breakfast
                </span>
              )}
              {hasFreeCancellation && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-medium rounded-md border border-blue-200">
                  ✓ Free Cancellation
                </span>
              )}
              {payAtHotel && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 text-xs font-medium rounded-md border border-purple-200">
                  🏨 Pay at Hotel
                </span>
              )}
              {amenities.slice(0, 3).map((a) => (
                <span key={a} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-md">
                  {a}
                </span>
              ))}
            </div>

            {/* Social proof */}
            {recentBookings && recentBookings > 0 && (
              <p className="text-xs text-orange-600 font-medium mb-2">
                🔥 {recentBookings} booking{recentBookings > 1 ? 's' : ''} in last 24 hours
              </p>
            )}
          </div>

          {/* Price section */}
          <div className="flex items-end justify-between mt-auto pt-3 border-t border-gray-100">
            <div>
              {cashbackAmount && cashbackAmount > 0 && (
                <span className="inline-block px-2 py-0.5 bg-amber-50 text-amber-700 text-xs font-semibold rounded-md border border-amber-200 mb-1">
                  {formatPrice(cashbackAmount)} Cashback
                </span>
              )}
            </div>

            <div className="text-right">
              {hasDiscount && rackPrice && (
                <div className="text-sm text-gray-400 line-through">
                  {formatPrice(rackPrice)}
                </div>
              )}
              <div className="text-2xl font-bold text-gray-900">
                {formatPrice(minPrice)}
              </div>
              <div className="text-xs text-gray-500">per night + taxes</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
