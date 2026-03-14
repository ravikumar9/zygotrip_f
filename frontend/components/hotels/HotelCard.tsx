'use client';
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { MapPin, Tag, Zap, Star, Heart, Check, Coffee, Navigation } from 'lucide-react';
import { clsx } from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import RatingStars from '@/components/ui/RatingStars';
import AmenityBadge from '@/components/ui/AmenityBadge';
import { analytics, bookingFunnel } from '@/lib/analytics';
import type { Property } from '@/types';

interface HotelCardProps {
  hotel: Property;
  position?: number;
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
 * HotelCard — Goibibo-style horizontal OTA card component.
 *
 * Three-column layout:
 *   LEFT:   Hotel image with overlay badges
 *   MIDDLE: Name, rating, location, amenities, trust signals
 *   RIGHT:  Discount badge, price, crossed original, urgency, View Rooms CTA
 */
export default function HotelCard({ hotel, position, checkin, checkout, adults, rooms, location }: HotelCardProps) {
  const { formatPrice } = useFormatPrice();
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
  const strikeThroughPrice = hotel.rack_rate && hotel.rack_rate > hotel.min_price
    ? hotel.rack_rate
    : null;
  const computedDiscountBadge = strikeThroughPrice
    ? `${Math.round(((strikeThroughPrice - hotel.min_price) / strikeThroughPrice) * 100)}% OFF`
    : null;
  const discountBadge = hotel.discount_badge || computedDiscountBadge;
  const recentBookings = hotel.recent_bookings ?? hotel.bookings_today;

  const trackHotelClick = () => {
    const payload = JSON.stringify({
      property_id: hotel.id,
      source: 'hotel_listing_card',
      position,
      query_id: [location || 'all', checkin || 'any', checkout || 'any'].join(':'),
    });

    analytics.track('hotel_card_clicked', {
      property_id: hotel.id,
      property_name: hotel.name,
      position,
      location,
    });
    bookingFunnel.enter('hotel_page_viewed', {
      property_id: hotel.id,
      property_name: hotel.name,
      source: 'hotel_listing_card',
    });

    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        navigator.sendBeacon('/search/api/track-click/', new Blob([payload], { type: 'application/json' }));
        return;
      }
      void fetch('/search/api/track-click/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      });
    } catch {
      // Click tracking is best-effort and must never block navigation.
    }
  };

  return (
    <Link href={href} className="group block" onClick={trackHotelClick}>
      <article className={clsx(
        'bg-white rounded-2xl overflow-hidden transition-all duration-200',
        'hover:shadow-card-hover border border-neutral-100 shadow-card',
        'flex flex-col sm:flex-row'
      )}>
        {/* ── LEFT COLUMN: Image ────────────────────────────── */}
        <div className="relative sm:w-[200px] lg:w-[220px] xl:w-[200px] h-48 sm:h-auto sm:min-h-[190px] shrink-0 overflow-hidden">
          {hotel.primary_image && !imgError ? (
            <Image
              src={hotel.primary_image}
              alt={hotel.name}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 640px) 100vw, 240px"
              loading="lazy"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="h-full bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center">
              <span className="text-5xl">🏨</span>
            </div>
          )}

          <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent" />

          {/* Deal badge - top left */}
          {dealBadge && (
            <span className={`absolute top-3 left-3 flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full shadow-md ${dealBadge.cls}`}>
              {dealBadge.icon}
              {dealBadge.label}
            </span>
          )}

          {/* Wishlist */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); setWishlisted(!wishlisted); }}
            className="absolute top-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all z-10"
            style={{ background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)' }}
            aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
          >
            <Heart size={16} fill={wishlisted ? '#eb5757' : 'none'} stroke={wishlisted ? '#eb5757' : '#374151'} />
          </button>

          {/* Star badge */}
          <div className="absolute bottom-3 left-3 bg-black/50 backdrop-blur-sm text-white text-xs font-bold px-2 py-0.5 rounded-full">
            {hotel.star_category}★
          </div>
        </div>

        {/* ── MIDDLE COLUMN: Details ────────────────────────── */}
        <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
          <div>
            {/* Name + Type */}
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="min-w-0">
                <span className="text-2xs text-primary-600 font-medium uppercase tracking-wide">
                  {hotel.property_type}
                </span>
                <h3 className="font-bold text-neutral-900 text-[15px] leading-snug line-clamp-1 group-hover:text-primary-600 transition-colors font-heading">
                  {hotel.name}
                </h3>
              </div>
              {ratingNum > 0 && (
                <div className="rating-badge flex-shrink-0">
                  <Star size={11} fill="white" stroke="none" />{ratingNum.toFixed(1)}
                </div>
              )}
            </div>

            {/* Rating + Reviews */}
            <div className="flex items-center gap-2 mb-1.5">
              <RatingStars rating={ratingNum} reviewCount={hotel.review_count} tier={hotel.rating_tier} showCount size="sm" />
            </div>

            {/* Location + Distance */}
            <p className="flex items-center gap-1 text-xs text-neutral-500 mb-2">
              <MapPin size={12} className="shrink-0" />
              <span className="truncate">
                {hotel.area || hotel.landmark
                  ? `${hotel.area || hotel.landmark}, ${hotel.city_name}`
                  : hotel.city_name}
              </span>
              {hotel.distance_km != null && hotel.distance_km > 0 && (
                <span className="inline-flex items-center gap-0.5 text-neutral-400 ml-1 shrink-0">
                  <Navigation size={10} />
                  {hotel.distance_km < 1
                    ? `${Math.round(hotel.distance_km * 1000)}m`
                    : `${hotel.distance_km.toFixed(1)} km`}
                </span>
              )}
            </p>

            {hotel.landmark_distance && (
              <p className="text-2xs text-neutral-400 mb-2 line-clamp-1">
                {hotel.landmark_distance}
              </p>
            )}

            {hotel.trust_badges && hotel.trust_badges.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {hotel.trust_badges.slice(0, 2).map((badge) => (
                  <span
                    key={badge}
                    className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-2xs font-semibold text-sky-700"
                  >
                    {badge}
                  </span>
                ))}
              </div>
            )}

            {/* Amenities — top 5 */}
            {hotel.amenity_names && hotel.amenity_names.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {hotel.amenity_names.slice(0, 5).map((name) => (
                  <AmenityBadge key={name} name={name} />
                ))}
              </div>
            )}
          </div>

          {/* Trust signals row */}
          <div className="flex flex-wrap gap-1.5 mt-auto">
            {hotel.has_breakfast && (
              <span className="inline-flex items-center gap-1 text-2xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                <Coffee size={10} strokeWidth={2.5} /> Breakfast Included
              </span>
            )}
            {hotel.has_free_cancellation && (
              <span className="inline-flex items-center gap-1 text-2xs font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded-full">
                <Check size={10} strokeWidth={3} /> Free Cancellation
              </span>
            )}
            {hotel.pay_at_hotel && (
              <span className="text-2xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                Pay at Hotel
              </span>
            )}
            {recentBookings > 0 && (
              <span className="scarcity-badge">
                🔥 {recentBookings} bookings in last 24h
              </span>
            )}
          </div>
        </div>

        {/* ── RIGHT COLUMN: Price + CTA ─────────────────────── */}
        <div className="sm:w-[160px] lg:w-[170px] shrink-0 p-3 sm:p-4 sm:border-l border-t sm:border-t-0 border-neutral-100 flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 bg-neutral-50/50">
          {/* Discount badge */}
          {discountBadge && (
            <span className="text-xs font-bold text-green-700 bg-green-100 px-2.5 py-1 rounded-lg mb-1">
              {discountBadge}
            </span>
          )}

          {hotel.min_price > 0 ? (
            <div className="text-right">
              {strikeThroughPrice && (
                <p className="text-sm text-neutral-400 line-through">
                  {formatPrice(strikeThroughPrice)}
                </p>
              )}
              <p className="text-xl font-black text-neutral-900 font-heading">
                {formatPrice(hotel.min_price)}
              </p>
              <p className="text-2xs text-neutral-400">per night + taxes</p>
            </div>
          ) : (
            <p className="text-sm text-neutral-500">Contact for price</p>
          )}

          {/* Urgency */}
          {hotel.available_rooms != null && hotel.available_rooms > 0 && hotel.available_rooms <= 5 && (
            <span className="text-2xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-full border border-red-200 animate-pulse-soft whitespace-nowrap">
              ⚡ Only {hotel.available_rooms} left
            </span>
          )}

          {/* CTA */}
          <span className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-colors mt-2 whitespace-nowrap">
            VIEW ROOMS
          </span>

          {/* Cashback */}
          {hotel.cashback_amount && hotel.cashback_amount > 0 && (
            <span className="text-2xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full mt-1">
              🎁 {formatPrice(hotel.cashback_amount)} cashback
            </span>
          )}
        </div>
      </article>
    </Link>
  );
}
