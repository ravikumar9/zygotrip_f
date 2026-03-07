'use client';

import Link from 'next/link';
import { Star, MapPin, Heart, Wifi, Car, Coffee, Dumbbell, Wind, Waves } from 'lucide-react';
import type { Property } from '@/types';
import { useState } from 'react';

// Map keyword → icon (Lucide components, correctly typed as LucideIcon)
type IconComponent = React.ComponentType<{ size?: number | string; className?: string }>;
const AMENITY_ICONS: Record<string, IconComponent> = {
  wifi:      Wifi,
  parking:   Car,
  breakfast: Coffee,
  gym:       Dumbbell,
  ac:        Wind,
  pool:      Waves,
};

function getAmenityIcon(name: string): IconComponent | null {
  const key = name.toLowerCase();
  for (const [k, Icon] of Object.entries(AMENITY_ICONS)) {
    if (key.includes(k)) return Icon;
  }
  return null;
}

function formatPrice(price: string | number) {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
  }).format(num);
}

interface PropertyCardProps {
  property: Property;
  index?: number;
}

export default function PropertyCard({ property, index = 0 }: PropertyCardProps) {
  const [wishlisted, setWishlisted]   = useState(false);
  const [imgError,   setImgError]     = useState(false);

  // `primary_image` is a single resolved URL on the list endpoint
  const imageUrl = !imgError ? property.primary_image : null;

  // `amenity_names` is a flat string[] from the list endpoint
  const displayedAmenities = (property.amenity_names ?? []).slice(0, 4);

  const ratingNum = parseFloat(String(property.rating ?? '0'));
  const ratingColor =
    ratingNum >= 4.5 ? '#059669' :
    ratingNum >= 3.5 ? '#1a73e8' :
    '#f97316';

  return (
    <Link href={`/hotels/${property.slug}`} className="block group">
      <article
        className="property-card animate-fade-up"
        style={{ animationDelay: `${index * 0.06}s` }}
      >
        {/* ─── Image ───────────────────────────────────────────── */}
        <div className="relative aspect-[4/3] overflow-hidden bg-neutral-100 rounded-t-2xl">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={property.name}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              onError={() => setImgError(true)}
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-100 to-indigo-200">
              <span className="text-5xl">🏨</span>
            </div>
          )}

          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />

          {/* Wishlist button */}
          <button
            onClick={(e) => { e.preventDefault(); setWishlisted(!wishlisted); }}
            className="absolute top-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all"
            style={{ background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)' }}
            aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
          >
            <Heart
              size={16}
              fill={wishlisted ? '#eb5757' : 'none'}
              stroke={wishlisted ? '#eb5757' : '#374151'}
            />
          </button>

          {/* Trending badge */}
          {property.is_trending && (
            <div className="absolute top-3 left-3 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500 text-white">
              🔥 Trending
            </div>
          )}

          {/* Free cancellation badge */}
          {property.has_free_cancellation && (
            <div
              className="absolute bottom-3 left-3 px-2 py-1 rounded-lg text-xs font-semibold text-white"
              style={{ background: 'rgba(16,185,129,0.9)', backdropFilter: 'blur(4px)' }}
            >
              ✓ Free Cancellation
            </div>
          )}
        </div>

        {/* ─── Content ─────────────────────────────────────────── */}
        <div className="p-4">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <h3
              className="font-bold text-neutral-900 text-base leading-tight flex-1 group-hover:text-primary-700 transition-colors font-heading"
            >
              {property.name}
            </h3>
            {ratingNum > 0 && (
              <div
                className="rating-badge flex-shrink-0"
                style={{ background: `linear-gradient(135deg, ${ratingColor}, ${ratingColor}cc)` }}
              >
                <Star size={11} fill="white" stroke="none" />
                {ratingNum.toFixed(1)}
              </div>
            )}
          </div>

          {/* Star category */}
          {property.star_category > 0 && (
            <div className="flex items-center gap-0.5 mb-1.5">
              {Array.from({ length: property.star_category }).map((_, i) => (
                <Star key={i} size={11} fill="#f59e0b" stroke="none" />
              ))}
            </div>
          )}

          {/* Location */}
          <div className="flex items-center gap-1 text-neutral-500 text-sm mb-3">
            <MapPin size={13} className="shrink-0" />
            <span className="truncate">
              {[property.locality_name || property.area, property.city_name].filter(Boolean).join(', ')}
            </span>
          </div>

          {/* Amenity tags */}
          {displayedAmenities.length > 0 && (
            <div className="flex items-center gap-1.5 mb-3 flex-wrap">
              {displayedAmenities.map((amenityName) => {
                const Icon = getAmenityIcon(amenityName);
                return (
                  <div
                    key={amenityName}
                    className="flex items-center gap-1 text-xs text-neutral-500 bg-neutral-50 px-2 py-1 rounded-lg border border-neutral-100"
                    title={amenityName}
                  >
                    {Icon && <Icon size={11} />}
                    <span>{amenityName}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Price + CTA */}
          <div className="flex items-end justify-between mt-auto pt-2.5 border-t border-neutral-100">
            <div>
              <div className="flex items-baseline gap-1">
                <span
                  className="text-xl font-black font-heading"
                  style={{ color: '#1a1a2e' }}
                >
                  {formatPrice(property.min_price)}
                </span>
                <span className="text-xs text-neutral-400">/night</span>
              </div>
              {property.review_count > 0 && (
                <p className="text-xs text-neutral-400 mt-0.5">
                  {property.review_count} review{property.review_count !== 1 ? 's' : ''}
                </p>
              )}
            </div>
            <span
              className="text-xs px-3 py-1.5 rounded-xl font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #eb5757, #c0392b)' }}
            >
              Book Now →
            </span>
          </div>
        </div>
      </article>
    </Link>
  );
}
