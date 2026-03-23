'use client';
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { MapPin, Star, Heart, Check, Coffee, Wifi, Car, Zap, Navigation, UtensilsCrossed } from 'lucide-react';
import { clsx } from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { analytics, bookingFunnel } from '@/lib/analytics';
import type { Property } from '@/types';

function getDealBadge(hotel: Property) {
  const r = parseFloat(hotel.rating || '0');
  if (hotel.is_trending) return { label: '🔥 Trending', cls: 'bg-red-600 text-white' };
  if (r >= 4.5) return { label: '⭐ Top Rated', cls: 'bg-amber-500 text-white' };
  if (hotel.has_free_cancellation) return { label: '✓ Free Cancel', cls: 'bg-green-600 text-white' };
  return null;
}

function getRatingLabel(r: number) {
  if (r >= 4.5) return 'Excellent';
  if (r >= 4.0) return 'Very Good';
  if (r >= 3.5) return 'Good';
  if (r >= 3.0) return 'Average';
  return '';
}

function getRatingColor(r: number) {
  if (r >= 4.5) return 'bg-green-600';
  if (r >= 4.0) return 'bg-green-500';
  if (r >= 3.5) return 'bg-amber-500';
  return 'bg-orange-500';
}

const AMENITY_ICONS: Record<string, React.ReactNode> = {
  'WiFi': <Wifi size={11} />, 'Free WiFi': <Wifi size={11} />,
  'Parking': <Car size={11} />, 'Restaurant': <UtensilsCrossed size={11} />,
  'Breakfast': <Coffee size={11} />,
};

export default function HotelCard({ hotel, position, checkin, checkout, adults, rooms, location }: {
  hotel: Property; position?: number; checkin?: string; checkout?: string;
  adults?: string | number; rooms?: string | number; location?: string;
}) {
  const { formatPrice } = useFormatPrice();
  const [wishlisted, setWishlisted] = useState(false);
  const [imgError, setImgError] = useState(false);

  const params = new URLSearchParams();
  if (checkin) params.set('checkin', checkin);
  if (checkout) params.set('checkout', checkout);
  if (adults) params.set('adults', String(adults));
  if (rooms) params.set('rooms', String(rooms));
  if (location) params.set('location', location);
  const href = `/hotels/${hotel.slug}${params.size ? '?' + params.toString() : ''}`;

  const ratingNum = parseFloat(hotel.rating || '0');
  const rack = hotel.rack_rate && hotel.rack_rate > hotel.min_price ? hotel.rack_rate : null;
  const discPct = rack ? Math.round(((rack - hotel.min_price) / rack) * 100) : null;
  const discountBadge = hotel.discount_badge || (discPct ? `${discPct}% OFF` : null);
  const dealBadge = getDealBadge(hotel);
  const recentBookings = hotel.recent_bookings ?? hotel.bookings_today;

  const track = () => {
    analytics.track('hotel_card_clicked', { property_id: hotel.id, property_name: hotel.name, position, location });
    bookingFunnel.enter('hotel_page_viewed', { property_id: hotel.id, property_name: hotel.name, source: 'hotel_listing_card' });
    try {
      navigator.sendBeacon?.('/search/api/track-click/', new Blob([JSON.stringify({ property_id: hotel.id, position })], { type: 'application/json' }));
    } catch {}
  };

  return (
    <Link href={href} className="group block" onClick={track}>
      <article className="bg-white rounded-xl border border-neutral-200 overflow-hidden hover:shadow-lg transition-all duration-200 flex flex-col sm:flex-row">

        {/* IMAGE */}
        <div className="relative sm:w-[240px] lg:w-[260px] h-52 sm:h-auto shrink-0 overflow-hidden bg-neutral-100">
          {hotel.primary_image && !imgError ? (
            <Image src={hotel.primary_image} alt={hotel.name} fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 640px) 100vw, 280px" loading="lazy"
              onError={() => setImgError(true)} />
          ) : (
            <div className="h-full bg-gradient-to-br from-neutral-200 to-neutral-300 flex items-center justify-center">
              <span className="text-6xl opacity-50">🏨</span>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />
          {dealBadge && (
            <span className={`absolute top-2 left-2 text-xs font-bold px-2 py-0.5 rounded ${dealBadge.cls}`}>
              {dealBadge.label}
            </span>
          )}
          {discountBadge && (
            <span className="absolute top-2 right-10 bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded">
              {discountBadge}
            </span>
          )}
          <button type="button" onClick={e => { e.preventDefault(); e.stopPropagation(); setWishlisted(!wishlisted); }}
            className="absolute top-2 right-2 w-8 h-8 rounded-full bg-white/90 flex items-center justify-center shadow-sm z-10">
            <Heart size={15} fill={wishlisted ? '#e11d48' : 'none'} stroke={wishlisted ? '#e11d48' : '#6b7280'} />
          </button>
          <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs font-bold px-1.5 py-0.5 rounded">
            {hotel.star_category}★
          </div>
          {hotel.image_count > 1 && (
            <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
              +{hotel.image_count} photos
            </div>
          )}
        </div>

        {/* MIDDLE: Details */}
        <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
          <div>
            <div className="text-xs text-neutral-500 font-medium uppercase tracking-wide mb-0.5">
              {hotel.property_type} · {hotel.star_category} Star
            </div>
            <h3 className="font-bold text-neutral-900 text-base leading-snug line-clamp-1 group-hover:text-primary-600 transition-colors mb-1">
              {hotel.name}
            </h3>

            {/* Rating badge */}
            {ratingNum > 0 && (
              <div className="flex items-center gap-2 mb-2">
                <span className={clsx('text-white text-xs font-bold px-1.5 py-0.5 rounded', getRatingColor(ratingNum))}>
                  {ratingNum.toFixed(1)}
                </span>
                <span className="text-xs font-semibold text-neutral-700">{getRatingLabel(ratingNum)}</span>
                {hotel.review_count > 0 && (
                  <span className="text-xs text-neutral-400">({hotel.review_count.toLocaleString('en-IN')} reviews)</span>
                )}
              </div>
            )}

            {/* Location */}
            <p className="flex items-center gap-1 text-xs text-neutral-500 mb-2">
              <MapPin size={11} className="shrink-0 text-primary-500" />
              <span className="truncate">
                {hotel.area || hotel.landmark ? `${hotel.area || hotel.landmark}, ` : ''}{hotel.city_name}
              </span>
              {hotel.distance_km > 0 && (
                <span className="text-neutral-400 ml-1 shrink-0 flex items-center gap-0.5">
                  <Navigation size={9} />
                  {hotel.distance_km < 1 ? `${Math.round(hotel.distance_km * 1000)}m` : `${hotel.distance_km.toFixed(1)}km`} from centre
                </span>
              )}
            </p>

            {/* Amenities */}
            {hotel.amenity_names?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {hotel.amenity_names.slice(0, 6).map(name => (
                  <span key={name} className="inline-flex items-center gap-1 text-xs text-neutral-600 bg-neutral-50 border border-neutral-200 px-2 py-0.5 rounded">
                    {AMENITY_ICONS[name] || <Check size={10} />} {name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Trust signals */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {hotel.has_breakfast && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
                <Coffee size={10} /> Breakfast included
              </span>
            )}
            {hotel.has_free_cancellation && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded">
                <Check size={10} /> Free cancellation
              </span>
            )}
            {hotel.pay_at_hotel && (
              <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded">Pay at hotel</span>
            )}
            {recentBookings > 0 && (
              <span className="text-xs font-medium text-orange-700 bg-orange-50 px-2 py-0.5 rounded">
                🔥 {recentBookings} booked today
              </span>
            )}
          </div>
        </div>

        {/* RIGHT: Price + CTA */}
        <div className="sm:w-[180px] shrink-0 p-4 sm:border-l border-t sm:border-t-0 border-neutral-100 flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-3 bg-neutral-50/50">
          <div className="text-right">
            {rack && (
              <p className="text-sm text-neutral-400 line-through">
                {formatPrice(Math.round(rack))}
              </p>
            )}
            <p className="text-2xl font-black text-neutral-900 leading-none">
              {formatPrice(Math.round(hotel.min_price))}
            </p>
            <p className="text-xs text-neutral-500 mt-0.5">per night</p>
            <p className="text-xs text-neutral-400">+ taxes & fees</p>
          </div>

          {hotel.available_rooms > 0 && hotel.available_rooms <= 5 && (
            <p className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded whitespace-nowrap">
              Only {hotel.available_rooms} left!
            </p>
          )}

          <span className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-bold px-5 py-2.5 rounded-lg transition-colors whitespace-nowrap w-full sm:w-auto text-center">
            View Rooms
          </span>

          {hotel.cashback_amount > 0 && (
            <p className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-right">
              🎁 {formatPrice(Math.round(hotel.cashback_amount))} cashback
            </p>
          )}
        </div>
      </article>
    </Link>
  );
}
