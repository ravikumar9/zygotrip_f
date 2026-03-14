'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { X, Gift, Clock } from 'lucide-react';

const STORAGE_KEY = 'zygo_pending_booking';

export interface PendingBooking {
  contextUuid: string;
  propertyName: string;
  checkin: string;
  checkout: string;
  savedAt: number; // timestamp
}

/** Save pending booking context when user enters booking flow */
export function savePendingBooking(data: Omit<PendingBooking, 'savedAt'>) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, savedAt: Date.now() }));
  } catch { /* storage full */ }
}

/** Clear pending booking (on successful confirmation or manual dismiss) */
export function clearPendingBooking() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY);
}

/** Get pending booking if it exists and is less than 24 hours old */
function getPendingBooking(): PendingBooking | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data: PendingBooking = JSON.parse(raw);
    const ageMs = Date.now() - data.savedAt;
    // Expire after 24 hours
    if (ageMs > 24 * 60 * 60 * 1000) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/**
 * Booking abandonment recovery banner.
 * Shows when user navigates away from booking flow and returns to the site.
 * Only appears on non-booking pages (homepage, hotel listing, hotel detail).
 *
 * Usage: Place in layout or specific pages:
 *   <AbandonmentBanner />
 */
export default function AbandonmentBanner() {
  const [pending, setPending] = useState<PendingBooking | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    // Don't show on booking or confirmation pages
    if (pathname.startsWith('/booking/') || pathname.startsWith('/confirmation/')) {
      setPending(null);
      return;
    }

    const data = getPendingBooking();
    setPending(data);
  }, [pathname]);

  if (!pending || dismissed) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 sm:bottom-4 sm:max-w-md z-50 animate-slide-up">
      <div className="bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-2xl shadow-2xl p-4 pr-10 relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full -translate-y-8 translate-x-8" />

        {/* Dismiss button */}
        <button
          onClick={() => { setDismissed(true); clearPendingBooking(); }}
          className="absolute top-3 right-3 w-6 h-6 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition-colors"
          aria-label="Dismiss"
        >
          <X size={12} />
        </button>

        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center shrink-0">
            <Gift size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-sm">Complete your booking</p>
            <p className="text-xs text-white/80 mt-0.5 truncate">
              {pending.propertyName} · {pending.checkin} → {pending.checkout}
            </p>
            <div className="flex items-center gap-1.5 mt-1">
              <Clock size={10} className="text-amber-300 shrink-0" />
              <p className="text-xs text-amber-200 font-medium">
                Earn ₹200 cashback — limited time!
              </p>
            </div>
          </div>
        </div>

        <Link
          href={`/booking/${pending.contextUuid}`}
          className="mt-3 block w-full text-center text-xs font-bold bg-white text-primary-700 rounded-xl py-2.5 hover:bg-white/90 transition-colors"
        >
          Continue Booking →
        </Link>
      </div>
    </div>
  );
}
