'use client';

import { Suspense } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import {
  CheckCircle, Calendar, MapPin, Users, Printer, ArrowRight,
  Mail, Phone, Moon, CreditCard, Shield, Home, Star, Download,
  AlertCircle, ChevronRight, Sparkles
} from 'lucide-react';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import Link from 'next/link';

function formatDate(d: string, opts?: Intl.DateTimeFormatOptions) {
  if (!d) return '';
  return new Date(d).toLocaleDateString('en-IN', opts || {
    weekday: 'short', day: 'numeric', month: 'long', year: 'numeric'
  });
}

function ConfirmationContent() {
  const { formatPrice: fmtRaw } = useFormatPrice();
  const fmt = (v: number | string) => fmtRaw(Math.round(Number(v)));
  const { booking_uuid } = useParams<{ booking_uuid: string }>();
  const router = useRouter();

  const { data: bookingResp, isLoading, error } = useQuery({
    queryKey: ['booking', booking_uuid],
    queryFn: () => bookingsService.getBooking(booking_uuid!),
    enabled: !!booking_uuid,
    retry: 2,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen page-booking-bg flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 font-medium">Loading your booking...</p>
        </div>
      </div>
    );
  }

  if (error || !bookingResp) {
    return (
      <div className="min-h-screen page-booking-bg flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center max-w-sm">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-neutral-700 mb-2">Booking Not Found</h2>
          <p className="text-sm text-neutral-400 mb-6">
            This booking may have expired or you may need to log in to view it.
          </p>
          <div className="flex flex-col gap-3">
            <button onClick={() => router.push('/account/login?next=' + encodeURIComponent(window.location.pathname))}
              className="btn-primary w-full py-3">
              Log in to view
            </button>
            <Link href="/bookings" className="text-sm text-neutral-500 hover:underline">My Bookings</Link>
          </div>
        </div>
      </div>
    );
  }

  // Support both wrapped {success, data} and direct object responses
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const booking = ((bookingResp as any)?.data || bookingResp) as any;

  const nights = booking.check_in && booking.check_out
    ? Math.round((new Date(booking.check_out).getTime() - new Date(booking.check_in).getTime()) / 86400000)
    : (booking.nights || 1);

  const isConfirmed = booking.status === 'confirmed';
  const totalPaid = Math.round(Number(booking.total_amount || 0));

  return (
    <div className="min-h-screen page-booking-bg py-8 px-4">
      <div className="max-w-2xl mx-auto">

        {/* Success Hero */}
        <div className="text-center mb-8">
          <div className="relative inline-block mb-4">
            <div className="w-24 h-24 rounded-full flex items-center justify-center mx-auto"
              style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 12px 40px rgba(16,185,129,0.4)' }}>
              <CheckCircle size={48} color="white" strokeWidth={2.5} />
            </div>
            <span className="absolute -top-2 -right-2 text-3xl select-none">🎉</span>
          </div>
          <h1 className="text-3xl font-black text-neutral-900 font-heading">Booking Confirmed!</h1>
          <p className="text-neutral-500 mt-2 text-sm">
            Confirmation sent to <span className="font-semibold text-neutral-700">{booking.guest_email}</span>
          </p>
        </div>

        {/* Main booking card */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-5">

          {/* Status header */}
          <div className={`px-6 py-3.5 flex items-center justify-between ${isConfirmed
            ? 'bg-gradient-to-r from-emerald-500 to-green-500'
            : 'bg-gradient-to-r from-amber-500 to-orange-500'}`}>
            <div className="flex items-center gap-2 text-white">
              <CheckCircle size={18} />
              <span className="font-black text-sm capitalize">{booking.status?.replace('_', ' ')}</span>
            </div>
            <div className="text-right">
              <p className="text-white/70 text-xs">Booking Reference</p>
              <p className="text-white font-black font-mono tracking-wider text-sm">{booking.public_booking_id}</p>
            </div>
          </div>

          <div className="p-6 space-y-5">
            {/* Property */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: 'linear-gradient(135deg, #1a1a2e, #0f3460)' }}>
                <MapPin size={20} className="text-white" />
              </div>
              <div>
                <p className="font-black text-neutral-900 text-lg leading-tight">{booking.property_name}</p>
                <p className="text-sm text-neutral-500 mt-0.5">{booking.rooms?.[0]?.room_type_name || booking.property_slug}</p>
              </div>
            </div>

            {/* Dates grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Calendar size={13} className="text-blue-500" />
                  <p className="text-xs font-bold text-blue-600 uppercase tracking-wide">Check-in</p>
                </div>
                <p className="font-black text-neutral-900">{formatDate(booking.check_in, { weekday: 'short', day: 'numeric', month: 'short' })}</p>
                <p className="text-xs text-neutral-400 mt-0.5">After 2:00 PM</p>
              </div>
              <div className="bg-orange-50 border border-orange-100 rounded-xl p-4">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Calendar size={13} className="text-orange-500" />
                  <p className="text-xs font-bold text-orange-600 uppercase tracking-wide">Check-out</p>
                </div>
                <p className="font-black text-neutral-900">{formatDate(booking.check_out, { weekday: 'short', day: 'numeric', month: 'short' })}</p>
                <p className="text-xs text-neutral-400 mt-0.5">Before 11:00 AM</p>
              </div>
            </div>

            {/* Duration strip */}
            <div className="flex items-center gap-3 bg-neutral-50 rounded-xl px-4 py-3">
              <div className="flex items-center gap-1.5 text-sm font-bold text-neutral-700">
                <Moon size={14} className="text-indigo-400" />
                {nights} Night{nights !== 1 ? 's' : ''}
              </div>
              <div className="w-px h-4 bg-neutral-200" />
              <div className="flex items-center gap-1.5 text-sm font-bold text-neutral-700">
                <Users size={14} className="text-primary-400" />
                {booking.adults || 2} Guests
              </div>
              {booking.room_count && (
                <>
                  <div className="w-px h-4 bg-neutral-200" />
                  <div className="text-sm font-bold text-neutral-700">{booking.room_count} Room{(booking.room_count ?? 1) > 1 ? 's' : ''}</div>
                </>
              )}
            </div>

            {/* Guest info */}
            <div className="border border-neutral-100 rounded-xl p-4 space-y-2">
              <p className="text-xs font-bold text-neutral-400 uppercase tracking-wide mb-2">Guest Information</p>
              <div className="flex items-center gap-2.5 text-sm">
                <Users size={14} className="text-neutral-400 shrink-0" />
                <span className="font-semibold text-neutral-800">{booking.guest_name}</span>
              </div>
              {booking.guest_email && (
                <div className="flex items-center gap-2.5 text-sm">
                  <Mail size={14} className="text-neutral-400 shrink-0" />
                  <span className="text-neutral-600">{booking.guest_email}</span>
                </div>
              )}
              {booking.guest_phone && (
                <div className="flex items-center gap-2.5 text-sm">
                  <Phone size={14} className="text-neutral-400 shrink-0" />
                  <span className="text-neutral-600">{booking.guest_phone}</span>
                </div>
              )}
            </div>

            {/* Price breakdown */}
            <div className="border-t border-dashed border-neutral-200 pt-4">
              <p className="text-xs font-bold text-neutral-400 uppercase tracking-wide mb-3">Price Summary</p>
              <div className="space-y-2 text-sm">
                {booking.price_breakdown?.base_amount !== undefined && (
                  <div className="flex justify-between text-neutral-600">
                    <span>Room charge</span><span className="font-medium">{fmt(booking.price_breakdown.base_amount)}</span>
                  </div>
                )}
                {Number(booking.price_breakdown?.meal_amount) > 0 && (
                  <div className="flex justify-between text-neutral-600">
                    <span>Meal plan</span><span className="font-medium">{fmt(booking.price_breakdown.meal_amount)}</span>
                  </div>
                )}
                {Number(booking.price_breakdown?.service_fee) > 0 && (
                  <div className="flex justify-between text-neutral-600">
                    <span>Service fee</span><span className="font-medium">{fmt(booking.price_breakdown.service_fee)}</span>
                  </div>
                )}
                {Number(booking.price_breakdown?.gst) > 0 && (
                  <div className="flex justify-between text-neutral-600">
                    <span>GST</span><span className="font-medium">{fmt(booking.price_breakdown.gst)}</span>
                  </div>
                )}
                {Number(booking.price_breakdown?.promo_discount) > 0 && (
                  <div className="flex justify-between text-green-600 bg-green-50 rounded-lg px-2 py-1.5">
                    <span className="flex items-center gap-1.5 font-semibold"><Sparkles size={12} />Discount</span>
                    <span className="font-bold">−{fmt(booking.price_breakdown.promo_discount)}</span>
                  </div>
                )}
                <div className="flex justify-between items-center font-black text-neutral-900 text-lg border-t-2 border-neutral-200 pt-2.5 mt-1">
                  <span>Total Paid</span>
                  <span className="text-primary-600">{fmt(totalPaid)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Important info card */}
        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-5 mb-5">
          <p className="text-sm font-black text-blue-800 mb-2 flex items-center gap-2">
            <Shield size={15} />What happens next?
          </p>
          <ul className="space-y-2 text-xs text-blue-700">
            <li className="flex items-start gap-2"><CheckCircle size={12} className="mt-0.5 shrink-0" />Booking confirmation e-mail sent to {booking.guest_email}</li>
            <li className="flex items-start gap-2"><CheckCircle size={12} className="mt-0.5 shrink-0" />The property will contact you 24 hours before check-in</li>
            <li className="flex items-start gap-2"><CheckCircle size={12} className="mt-0.5 shrink-0" />Carry a valid government ID for check-in</li>
            <li className="flex items-start gap-2"><CheckCircle size={12} className="mt-0.5 shrink-0" />Free cancellation available — check your confirmation email for terms</li>
          </ul>
        </div>

        {/* Action buttons */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <Link href="/bookings"
            className="flex items-center justify-center gap-2 bg-primary-600 text-white font-bold py-3.5 rounded-xl hover:bg-primary-700 transition-colors text-sm">
            <Users size={15} />My Bookings
          </Link>
          <button onClick={() => window.print()}
            className="flex items-center justify-center gap-2 bg-white text-neutral-700 font-bold py-3.5 rounded-xl border border-neutral-200 hover:bg-neutral-50 transition-colors text-sm">
            <Printer size={15} />Print / Save
          </button>
        </div>
        <Link href="/"
          className="flex items-center justify-center gap-2 text-sm text-neutral-400 hover:text-neutral-600 transition-colors">
          <Home size={14} />Back to Home
        </Link>

        <p className="text-center text-xs text-neutral-300 mt-6">
          Need help? Email <a href="mailto:support@zygotrip.com" className="underline text-neutral-400">support@zygotrip.com</a>
        </p>
      </div>
    </div>
  );
}

export default function ConfirmationPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen page-booking-bg flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ConfirmationContent />
    </Suspense>
  );
}
