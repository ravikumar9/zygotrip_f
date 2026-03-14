'use client';

/**
 * ShareButton — Universal social share component
 *
 * Priority:
 *   1. Native Web Share API (mobile-first, uses OS share sheet)
 *   2. Share panel with platform-specific deep links:
 *      WhatsApp · Facebook · X (Twitter) · Instagram · copy link
 *
 * Usage:
 *   // Share a hotel
 *   <ShareButton
 *     config={{
 *       title: 'The Taj Mahal Palace, Mumbai',
 *       text: 'Check out this amazing hotel I found on ZygoTrip!',
 *       url: 'https://zygotrip.com/hotels/the-taj-mahal-palace-mumbai/',
 *       hashtags: ['ZygoTrip', 'Travel', 'Mumbai'],
 *     }}
 *   />
 *
 *   // Share a booking
 *   <ShareButton
 *     config={{
 *       title: 'My Goa Trip 🌴',
 *       text: 'Just booked my Goa getaway via ZygoTrip!',
 *       url: 'https://zygotrip.com/booking/ZT-20260315-001234/',
 *     }}
 *     variant="button"
 *     size="md"
 *   />
 */

import { useState, useRef, useEffect } from 'react';
import { Share2, Copy, Check, X } from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ShareConfig {
  /** Page/card title */
  title: string;
  /** Pre-filled share text (shown on WhatsApp, Twitter, etc.) */
  text?: string;
  /** Canonical URL to share */
  url: string;
  /** Hashtags for Twitter/X (without #) */
  hashtags?: string[];
}

export interface ShareButtonProps {
  config: ShareConfig;
  /** "button" shows icon + label; "icon" shows icon only */
  variant?: 'button' | 'icon';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

// ── Platform definitions ─────────────────────────────────────────────────────

interface Platform {
  id: string;
  name: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
  getUrl: (config: ShareConfig) => string;
  /** If true, copy URL to clipboard instead of opening link */
  copyOnClick?: boolean;
}

const PLATFORMS: Platform[] = [
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    color: '#fff',
    bgColor: '#25D366',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
      </svg>
    ),
    getUrl: ({ url, text }) =>
      `https://wa.me/?text=${encodeURIComponent(`${text ?? ''} ${url}`.trim())}`,
  },
  {
    id: 'facebook',
    name: 'Facebook',
    color: '#fff',
    bgColor: '#1877F2',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
      </svg>
    ),
    getUrl: ({ url }) =>
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
  },
  {
    id: 'twitter',
    name: 'X (Twitter)',
    color: '#fff',
    bgColor: '#000',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    ),
    getUrl: ({ url, text, hashtags }) => {
      const tags = (hashtags ?? ['ZygoTrip', 'Travel']).join(',');
      return `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text ?? '')}&hashtags=${tags}&via=ZygoTrip`;
    },
  },
  {
    id: 'instagram',
    name: 'Instagram',
    color: '#fff',
    bgColor: '#E1306C',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
      </svg>
    ),
    // Instagram doesn't support URL pre-fill via web link — copy URL + open profile
    getUrl: () => 'https://www.instagram.com/zygotrip/',
    copyOnClick: true,
  },
];

// ── Component ────────────────────────────────────────────────────────────────

export default function ShareButton({
  config,
  variant = 'button',
  size = 'sm',
  className = '',
}: ShareButtonProps) {
  const [isOpen, setIsOpen]   = useState(false);
  const [copied, setCopied]   = useState(false);
  const [instaCopied, setInstaCopied] = useState(false);
  const panelRef              = useRef<HTMLDivElement>(null);

  // Close panel on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen]);

  const sizeClasses = {
    sm: 'px-3 py-2 text-sm gap-1.5',
    md: 'px-4 py-2.5 text-base gap-2',
    lg: 'px-5 py-3  text-base gap-2',
  }[size];

  const iconSize = { sm: 14, md: 16, lg: 18 }[size];

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleTrigger = async () => {
    // 1. Try native share (mobile / supported browsers)
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({
          title: config.title,
          text:  config.text,
          url:   config.url,
        });
        return; // success — no need to open panel
      } catch {
        // Cancelled or unsupported — fall through to panel
      }
    }
    setIsOpen((v) => !v);
  };

  const handleCopy = async (label?: 'main' | 'insta') => {
    try {
      await navigator.clipboard.writeText(config.url);
    } catch {
      // Clipboard API unavailable — try execCommand
      const el = document.createElement('textarea');
      el.value = config.url;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    if (label === 'insta') {
      setInstaCopied(true);
      setTimeout(() => setInstaCopied(false), 2500);
    } else {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className={`relative inline-block ${className}`}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={handleTrigger}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-label="Share this page"
        className={`flex items-center rounded-xl border border-neutral-200 bg-white font-medium text-neutral-600 hover:shadow-sm active:scale-95 transition-all ${sizeClasses}`}
      >
        <Share2 size={iconSize} />
        {variant === 'button' && <span>Share</span>}
      </button>

      {/* Panel */}
      {isOpen && (
        <>
          {/* Invisible full-screen backdrop */}
          <div className="fixed inset-0 z-40" aria-hidden onClick={() => setIsOpen(false)} />

          {/* Share dropdown */}
          <div
            ref={panelRef}
            role="dialog"
            aria-label="Share options"
            className="absolute right-0 top-full mt-2 z-50 w-72 bg-white rounded-2xl shadow-2xl border border-neutral-100 p-4 animate-in fade-in slide-in-from-top-2 duration-150"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-neutral-800">Share via</span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
                aria-label="Close share panel"
              >
                <X size={15} />
              </button>
            </div>

            {/* Social platform buttons */}
            <div className="grid grid-cols-2 gap-2 mb-3">
              {PLATFORMS.map((platform) => (
                <a
                  key={platform.id}
                  href={platform.copyOnClick ? undefined : platform.getUrl(config)}
                  target={platform.copyOnClick ? undefined : '_blank'}
                  rel="noopener noreferrer"
                  role={platform.copyOnClick ? 'button' : undefined}
                  tabIndex={0}
                  onClick={
                    platform.copyOnClick
                      ? (e) => {
                          e.preventDefault();
                          handleCopy('insta');
                          // Open Instagram after short delay
                          setTimeout(() => window.open('https://www.instagram.com/zygotrip/', '_blank'), 300);
                        }
                      : undefined
                  }
                  className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-neutral-100 hover:bg-neutral-50 transition-colors cursor-pointer text-sm font-medium text-neutral-800 select-none"
                >
                  <span
                    className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0"
                    style={{ backgroundColor: platform.bgColor, color: platform.color }}
                  >
                    {platform.icon}
                  </span>
                  <span>
                    {platform.id === 'instagram' && instaCopied
                      ? '✓ Copied!'
                      : platform.name}
                  </span>
                </a>
              ))}
            </div>

            {/* Divider */}
            <div className="border-t border-neutral-100 my-3" />

            {/* Copy link */}
            <button
              type="button"
              onClick={() => handleCopy('main')}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-neutral-50 border border-neutral-200 text-sm font-medium text-neutral-700 hover:bg-neutral-100 active:scale-[0.99] transition-all"
            >
              {copied ? (
                <>
                  <Check size={14} className="text-green-600" />
                  <span className="text-green-700">Link copied!</span>
                </>
              ) : (
                <>
                  <Copy size={14} />
                  Copy link
                </>
              )}
            </button>

            {/* Follow us */}
            <p className="mt-3 text-center text-xs text-neutral-400">
              Follow{' '}
              <a
                href="https://www.instagram.com/zygotrip/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-pink-500 hover:underline font-semibold"
              >
                @zygotrip
              </a>{' '}
              for travel inspiration ✈️
            </p>
          </div>
        </>
      )}
    </div>
  );
}

// ── Convenience wrappers ─────────────────────────────────────────────────────

/** Pre-configured share button for hotel property pages */
export function HotelShareButton({
  propertyName,
  slug,
  city,
  className,
}: {
  propertyName: string;
  slug: string;
  city?: string;
  className?: string;
}) {
  const url = `https://zygotrip.com/hotels/${slug}/`;
  return (
    <ShareButton
      config={{
        title: propertyName,
        text:  `Check out ${propertyName}${city ? ` in ${city}` : ''} — amazing deals on ZygoTrip! 🏨`,
        url,
        hashtags: ['ZygoTrip', 'Travel', city ?? 'India'].filter(Boolean),
      }}
      className={className}
    />
  );
}

/** Pre-configured share button for confirmed bookings */
export function BookingShareButton({
  bookingRef,
  hotelName,
  city,
  checkIn,
  className,
}: {
  bookingRef: string;
  hotelName: string;
  city?: string;
  checkIn?: string;
  className?: string;
}) {
  const url = `https://zygotrip.com/booking/${bookingRef}/`;
  const when = checkIn ? ` for ${checkIn}` : '';
  return (
    <ShareButton
      config={{
        title: `My ZygoTrip Booking — ${hotelName}`,
        text:  `Just booked ${hotelName}${city ? ` in ${city}` : ''}${when} via ZygoTrip! 🌴`,
        url,
        hashtags: ['ZygoTrip', 'Travel', 'Wanderlust'],
      }}
      variant="button"
      size="md"
      className={className}
    />
  );
}

/** Pre-configured share button for itinerary sharing */
export function ItineraryShareButton({
  bookingRef,
  hotelName,
  city,
  checkIn,
  checkOut,
  className,
}: {
  bookingRef: string;
  hotelName: string;
  city?: string;
  checkIn?: string;
  checkOut?: string;
  className?: string;
}) {
  const url = `https://zygotrip.com/confirmation/${bookingRef}/?view=itinerary`;
  const dates = [checkIn, checkOut].filter(Boolean).join(' to ');
  return (
    <ShareButton
      config={{
        title: `My ZygoTrip Itinerary - ${hotelName}`,
        text: `Sharing my ZygoTrip itinerary for ${hotelName}${city ? ` in ${city}` : ''}${dates ? ` (${dates})` : ''}.`,
        url,
        hashtags: ['ZygoTrip', 'Itinerary', 'Travel'],
      }}
      variant="button"
      size="md"
      className={className}
    />
  );
}

/** Pre-configured share button for post-stay review sharing */
export function ReviewShareButton({
  propertyName,
  slug,
  rating,
  className,
}: {
  propertyName: string;
  slug: string;
  rating?: number;
  className?: string;
}) {
  const url = `https://zygotrip.com/hotels/${slug}/#guest-reviews`;
  const score = typeof rating === 'number' && rating > 0 ? ` Rated ${rating.toFixed(1)}/5.` : '';
  return (
    <ShareButton
      config={{
        title: `My ZygoTrip review for ${propertyName}`,
        text: `I shared my stay experience for ${propertyName} on ZygoTrip.${score}`,
        url,
        hashtags: ['ZygoTrip', 'TravelReview', 'HotelStay'],
      }}
      variant="button"
      size="sm"
      className={className}
    />
  );
}
