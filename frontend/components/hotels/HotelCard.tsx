'use client';
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { MapPin, TrendingUp, Map, Tag, Zap, Star, Heart, Check } from 'lucide-react';
import { clsx } from 'clsx';
import { formatPrice } from '@/lib/formatPrice';
import RatingStars from '@/components/ui/RatingStars';
import AmenityBadge from '@/components/ui/AmenityBadge';
import type { Property } from '@/types';

interface HotelCardProps {
  hotel: Property;
  checkin?: string;
  checkout?: string;
  adults?: string | number;
  rooms?: string | number;
  location?: string;
}

/** Data-driven deal badge — only based on real property fields, no ID hacks */
function getDealBadge(hotel: Property): { label: string; icon: React.ReactNode; cls: string } | null {
  const rating = parseFloat(hotel.rating || '0');
  if (hotel.is_trending) return { label: 'Trending Deal', icon: <Zap size={9} />, cls: 'bg-red-600 text-white' };
  if (rating >= 4.5) return { label: 'Top Rated', icon: <Star size={9} fill="white" stroke="none" />, cls: 'bg-amber-500 text-white' };
  if (hotel.has_free_cancellation) return { label: 'Free Cancellation', icon: <Tag size={9} />, cls: 'bg-green-600 text-white' };
  return null;
}

/**
 * HotelCard — unified OTA-grade hotel card component.
 *
 * Merges features from:
 *   - Original HotelCard.tsx (deal badges, map button, amenities)
 *   - PropertyCard.tsx (wishlist, gradient overlay, rating badge)
 *   - PropertyCard.jsx (trust signals, social proof)
 *
 * Includes:
 *   - Hotel photo with lazy loading
 *   - Hotel name + star rating
 *   - Guest rating score + tier badge
 *   - Location with map link
 *   - Amenity preview (top 5)
 *   - Strikethrough price + discounted price
 *   - Trust signals: "Only X rooms left", "Booked N times today", "Free cancellation"
 *   - Wishlist button
 *   - stopPropagation on image/map/wishlist clicks (Phase 5 fix)
 */
export default function HotelCard({ hotel, checkin, checkout, adults, rooms, location }: HotelCardProps) {
  const [wishlisted, setWishlisted] = useState(false);
  const [imgError, setImgError] = useState(false);

  const searchParams = new URLSearchParams();
  if (checkin)  searchParams.set('checkin', checkin);
  if (checkout) searchParams.set('checkout', checkout);
  if (adults)   searchParams.set('adults', String(adults));
  if (rooms)    searchParams.set('rooms', String(rooms));
  if (location) searchParams.set('location', location);
  const href = `/hotels/${hotel.slug}${searchParams.size ? '?' + searchParams.toString() : ''}`;
  const dealBadge = getDealBadge(hotel);

  const ratingNum = parseFloat(hotel.rating || '0');
  // Show strikethrough only when the API provides an actual original price (rack_rate)
  const strikeThroughPrice = hotel.rack_rate && hotel.rack_rate > hotel.min_price
    ? hotel.rack_rate
    : null;

  return (
    <Link href={href} className="group block">
      <article className={clsx(
        'bg-white rounded-2xl overflow-hidden transition-all duration-200',
        'hover:shadow-card-hover border border-neutral-100 shadow-card'
      )}>
        {/* Image */}
        <div className="relative h-52 overflow-hidden">
          {hotel.primary_image && !imgError ? (
            <Image
              src={hotel.primary_image}
              alt={hotel.name}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
              loading="lazy"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="h-full bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center">
              <span className="text-5xl">🏨</span>
            </div>
          )}

          {/* Gradient overlay for text readability */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent" />

          {/* Badges overlay — top left */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5">
            {dealBadge && (
              <span className={`flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full shadow-md ${dealBadge.cls}`}>
                {dealBadge.icon && dealBadge.icon}
                {dealBadge.label}
              </span>
            )}
            {hotel.is_trending && !dealBadge && (
              <span className="flex items-center gap-1 bg-amber-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full shadow-sm">
                <TrendingUp size={10} /> Trending
              </span>
            )}
          </div>

          {/* Wishlist button — top right (Phase 5: stopPropagation) */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); setWishlisted(!wishlisted); }}
            className="absolute top-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all z-10"
            style={{ background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)' }}
            aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
          >
            <Heart
              size={16}
              fill={wishlisted ? '#eb5757' : 'none'}
              stroke={wishlisted ? '#eb5757' : '#374151'}
            />
          </button>

          {/* Star category badge — bottom left */}
          <div className="absolute bottom-3 left-3 bg-black/50 backdrop-blur-sm text-white text-xs font-bold px-2 py-0.5 rounded-full">
            {hotel.star_category}★
          </div>

          {/* Free cancellation badge — bottom right */}
          {hotel.has_free_cancellation && (
            <div className="absolute bottom-3 right-3 px-2 py-1 rounded-lg text-xs font-semibold text-white"
              style={{ background: 'rgba(16,185,129,0.9)', backdropFilter: 'blur(4px)' }}>
              <Check size={10} className="inline mr-0.5" strokeWidth={3} />
              Free Cancellation
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4">
          {/* Type + Rating row */}
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-primary-600 font-medium uppercase tracking-wide">
              {hotel.property_type}
            </span>
            {ratingNum > 0 && (
              <div className="rating-badge flex-shrink-0">
                <Star size={11} fill="white" stroke="none" />{ratingNum.toFixed(1)}
              </div>
            )}
          </div>

          {/* Name */}
          <h3 className="font-bold text-neutral-900 text-base leading-snug mb-1.5 line-clamp-2 group-hover:text-primary-600 transition-colors font-heading">
            {hotel.name}
          </h3>

          {/* Star category visual */}
          {hotel.star_category > 0 && (
            <div className="flex items-center gap-0.5 mb-1">
              {Array.from({ length: hotel.star_category }).map((_, i) => (
                <Star key={i} size={10} fill="#f59e0b" stroke="none" />
              ))}
            </div>
          )}

          {/* Location + Map */}
          <div className="flex items-center justify-between mb-3">
            <p className="flex items-center gap-1 text-xs text-neutral-500 min-w-0">
              <MapPin size={12} className="shrink-0" />
              <span className="truncate">
                {hotel.area || hotel.landmark
                  ? `${hotel.area || hotel.landmark}, ${hotel.city_name}`
                  : hotel.city_name}
              </span>
            </p>
            {hotel.latitude && hotel.longitude &&
              parseFloat(String(hotel.latitude)) !== 0 &&
              parseFloat(String(hotel.longitude)) !== 0 && (
              <button
                type="button"
                aria-label="View on map"
                onClick={e => {
                  e.stopPropagation();
                  e.preventDefault();
                  window.open(
                    `https://www.openstreetmap.org/?mlat=${hotel.latitude}&mlon=${hotel.longitude}&zoom=16`,
                    '_blank',
                    'noopener,noreferrer',
                  );
                }}
                className="shrink-0 flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-lg transition-colors ml-2"
                style={{ color: 'var(--primary)', background: '#fff0f0' }}
              >
                <Map size={10} />
                Map
              </button>
            )}
          </div>

          {/* Rating + Reviews (Booking.com style) */}
          <div className="flex items-center gap-2 mb-3">
            <RatingStars
              rating={ratingNum}
              reviewCount={hotel.review_count}
              tier={hotel.rating_tier}
              showCount
              size="sm"
            />
          </div>

          {/* Amenities — top 5 */}
          {hotel.amenity_names && hotel.amenity_names.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {hotel.amenity_names.slice(0, 5).map((name) => (
                <AmenityBadge key={name} name={name} />
              ))}
            </div>
          )}

          {/* Price + CTA */}
          <div className="flex items-end justify-between pt-3 border-t border-neutral-100">
            <div>
              {hotel.min_price > 0 ? (
                <>
                  <p className="text-xs text-neutral-400">Starting from</p>
                  <div className="flex items-baseline gap-2">
                    {strikeThroughPrice && (
                      <span className="text-sm text-neutral-400 line-through">
                        {formatPrice(strikeThroughPrice)}
                      </span>
                    )}
                    <p className="text-xl font-black text-neutral-900 font-heading">
                      {formatPrice(hotel.min_price)}
                    </p>
                  </div>
                  <p className="text-xs text-neutral-400">per night + taxes</p>
                </>
              ) : (
                <p className="text-sm text-neutral-500">Contact for price</p>
              )}
            </div>
            <span className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-bold px-4 py-2 rounded-xl transition-colors">
              View Rooms
            </span>
          </div>

          {/* Trust signals */}
          <div className="flex flex-wrap gap-2 mt-3">
            {hotel.bookings_today > 0 && (
              <span className="scarcity-badge">
                🔥 Booked {hotel.bookings_today} times today
              </span>
            )}
            {hotel.pay_at_hotel && (
              <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                Pay at Hotel
              </span>
            )}
          </div>
        </div>
      </article>
    </Link>
  );
}
