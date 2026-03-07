'use client';

import { useState, useEffect, Suspense } from 'react';
import { useParams, useRouter, usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import BookingSummary from '@/components/booking/BookingSummary';
import PriceBreakdown from '@/components/booking/PriceBreakdown';
import {
  Shield, CheckCircle, CreditCard, Wallet,
  ArrowLeft, User, Mail, Phone, Lock,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';
import { format, parseISO, isValid } from 'date-fns';
import clsx from 'clsx';
import { formatPrice as fmt } from '@/lib/formatPrice';

function fmtDate(dateStr: string) {
  try {
    const d = parseISO(dateStr);
    if (!isValid(d)) return dateStr;
    return format(d, 'EEE, d MMM');
  } catch {
    return dateStr;
  }
}

// ── Constants ──────────────────────────────────────────────────────────────

const TITLE_OPTIONS = ['Mr', 'Mrs', 'Ms', 'Dr', 'Prof'];

function splitFullName(full: string): [string, string] {
  const parts = (full ?? '').trim().split(/\s+/);
  return [parts[0] ?? '', parts.slice(1).join(' ')];
}

// ── Main component ─────────────────────────────────────────────────────────

function BookingContent() {
  const { context_uuid } = useParams<{ context_uuid: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  // ── No auth guard — guest checkout is supported ───────────────────────

  // ── UI state ──────────────────────────────────────────────────────────
  const [paymentMethod, setPaymentMethod] = useState<'wallet' | 'gateway'>('wallet');
  const [promoCode, setPromoCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState<{
    uuid: string; public_booking_id: string;
  } | null>(null);

  // ── Guest fields ──────────────────────────────────────────────────────
  const [guestTitle, setGuestTitle] = useState('Mr');
  const [guestFirstName, setGuestFirstName] = useState('');
  const [guestLastName, setGuestLastName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');
  const [guestPhone, setGuestPhone] = useState('');

  // Pre-fill from authenticated user profile
  useEffect(() => {
    if (user) {
      const [first, last] = splitFullName(user.full_name ?? '');
      setGuestFirstName((prev) => prev || first);
      setGuestLastName((prev) => prev || last);
      setGuestEmail((prev) => prev || (user.email ?? ''));
      setGuestPhone((prev) => prev || (user.phone ?? ''));
    }
  }, [user]);

  // ── Booking context query ──────────────────────────────────────────────
  const { data: context, isLoading: ctxLoading, error: ctxError } = useQuery({
    queryKey: ['booking-context', context_uuid],
    queryFn: () => bookingsService.getContext(context_uuid!),
    enabled: !!context_uuid,   // fires for both authenticated and guest users
    refetchInterval: 60_000,
    retry: 1,
  });

  // ── Confirm handler ───────────────────────────────────────────────────
  const handleConfirm = async () => {
    if (!context_uuid || !context) return;
    if (!guestFirstName.trim()) {
      toast.error('Please enter your first name.', { duration: 6000 });
      return;
    }
    if (!guestEmail.trim()) {
      toast.error('Please enter your email address.', { duration: 6000 });
      return;
    }
    const cleanPhone = guestPhone.replace(/\s/g, '');
    if (!cleanPhone || !/^[6-9]\d{9}$/.test(cleanPhone)) {
      toast.error('Please enter a valid 10-digit Indian mobile number.', { duration: 6000 });
      return;
    }

    const fullName = [guestTitle, guestFirstName.trim(), guestLastName.trim()]
      .filter(Boolean)
      .join(' ');

    setLoading(true);
    try {
      const booking = await bookingsService.confirmBooking({
        context_uuid,
        payment_method: paymentMethod,
        guest_name: fullName,
        guest_email: guestEmail,
        guest_phone: guestPhone,
        idempotency_key: `ctx-${context_uuid}-${Date.now()}`,
      });
      setConfirmedBooking({
        uuid: booking.uuid,
        public_booking_id: booking.public_booking_id,
      });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ??
        (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail ??
        'Booking failed. Please try again.';
      toast.error(msg, { duration: 6000 });
    } finally {
      setLoading(false);
    }
  };

  // ── Auth loading state — wait for auth check to finish ────────────────
  if (authLoading) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center">
        <div className="text-center">
          <div className="skeleton w-16 h-16 rounded-full mx-auto mb-4" />
          <p className="text-neutral-500 font-medium">Verifying session…</p>
        </div>
      </div>
    );
  }

  if (ctxLoading) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center">
        <div className="text-center">
          <div className="skeleton w-16 h-16 rounded-full mx-auto mb-4" />
          <p className="text-neutral-500 font-medium">Loading your booking...</p>
        </div>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────
  if (ctxError || !context) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-sm px-4">
          <p className="text-5xl mb-4">😕</p>
          <h2 className="text-xl font-bold text-neutral-700 mb-2">Booking session not found</h2>
          <p className="text-sm text-neutral-400 mb-6">
            This booking session may have expired or is invalid. Please search again.
          </p>
          <button onClick={() => router.push('/hotels')} className="btn-primary">
            Browse Hotels
          </button>
        </div>
      </div>
    );
  }

  // ── Success / Confirmation screen ─────────────────────────────────────
  if (confirmedBooking) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center animate-fade-up">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
            style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
            <CheckCircle size={36} stroke="white" />
          </div>
          <h1 className="text-3xl font-black text-neutral-900 mb-2 font-heading">
            Booking Confirmed! 🎉
          </h1>
          <p className="text-neutral-500 mb-6">
            Your reservation at {context.property_name} has been created.
          </p>

          <div className="bg-white rounded-2xl shadow-card p-6 mb-6 text-left">
            <p className="text-xs text-neutral-400 mb-1 text-center">Booking ID</p>
            <p className="text-2xl font-black text-primary-700 mb-5 text-center font-heading">
              {confirmedBooking.public_booking_id}
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Property</p>
                <p className="font-bold text-neutral-800">{context.property_name}</p>
              </div>
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Total Paid</p>
                <p className="font-bold text-neutral-800">{fmt(context.final_price)}</p>
              </div>
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Check-in</p>
                <p className="font-bold text-neutral-800">{context.checkin}</p>
              </div>
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Check-out</p>
                <p className="font-bold text-neutral-800">{context.checkout}</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => router.push(`/confirmation/${confirmedBooking.uuid}`)}
              className="btn-primary w-full"
            >
              View Booking Confirmation
            </button>
            <button onClick={() => router.push('/hotels')} className="btn-secondary w-full">
              Explore More Hotels
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Derived values ────────────────────────────────────────────────────
  const checkin = context.checkin ?? '';
  const checkout = context.checkout ?? '';
  const nights = context.nights ?? 0;
  const adults = context.adults ?? 1;
  const canSubmit = !loading && guestFirstName.trim().length > 0 && guestEmail.trim().length > 0 && /^[6-9]\d{9}$/.test(guestPhone.replace(/\s/g, ''));

  // ── Main checkout form ────────────────────────────────────────────────
  return (
    <div className="page-booking-bg">
      <div className="max-w-6xl mx-auto px-4 py-8">

        {/* ── Page header ───────────────────────────────────────────── */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-xl hover:bg-white hover:shadow-sm transition-all"
            aria-label="Go back"
          >
            <ArrowLeft size={20} className="text-neutral-600" />
          </button>
          <div>
            <h1 className="text-2xl font-black text-neutral-900 font-heading">
              Complete Booking
            </h1>
            <p className="text-sm text-neutral-500">Secure checkout · Instant confirmation</p>
          </div>
        </div>

        <div className="grid lg:grid-cols-[minmax(0,1fr)_380px] gap-6">

          {/* ════════════════════════════════════════════════════════════
               LEFT COLUMN — Property strip + Guest form + Payment
          ════════════════════════════════════════════════════════════ */}
          <div className="space-y-5">

            {/* ── Compact Property Info Card ───────────────────────── */}
            <div className="bg-white rounded-2xl shadow-card overflow-hidden border border-neutral-100">
              {/* Dark gradient header */}
              <div
                className="flex items-center gap-4 p-4"
                style={{ background: 'linear-gradient(90deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)' }}
              >
                <div className="w-12 h-12 rounded-xl bg-white/15 flex items-center justify-center text-2xl shrink-0">
                  🏨
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className="font-bold text-white text-sm leading-snug truncate font-heading"
                  >
                    {context.property_name}
                  </p>
                  {context.room_type_name && (
                    <p className="text-white/65 text-xs mt-0.5 truncate">
                      {context.room_type_name}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-white/50 text-[10px] uppercase tracking-wider">Total</p>
                  <p className="text-white font-black text-base leading-tight">
                    {fmt(context.final_price)}
                  </p>
                </div>
              </div>

              {/* Check-in / Check-out / Duration grid */}
              <div className="grid grid-cols-3 divide-x divide-neutral-100 text-center text-xs">
                <div className="py-3 px-3">
                  <p className="text-neutral-400 font-medium mb-0.5">Check-in</p>
                  <p className="font-bold text-neutral-800 text-sm">{fmtDate(checkin)}</p>
                  <p className="text-neutral-400 text-[10px] mt-0.5">2:00 PM</p>
                </div>
                <div className="py-3 px-3">
                  <p className="text-neutral-400 font-medium mb-0.5">Check-out</p>
                  <p className="font-bold text-neutral-800 text-sm">{fmtDate(checkout)}</p>
                  <p className="text-neutral-400 text-[10px] mt-0.5">11:00 AM</p>
                </div>
                <div className="py-3 px-3">
                  <p className="text-neutral-400 font-medium mb-0.5">Duration</p>
                  <p className="font-bold text-neutral-800 text-sm">
                    {nights}N&nbsp;·&nbsp;{adults}G
                  </p>
                  <p className="text-neutral-400 text-[10px] mt-0.5">
                    {context.rooms} room{context.rooms !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            </div>

            {/* ── Guest Details ─────────────────────────────────────── */}
            <div className="bg-white rounded-2xl shadow-card p-6">
              <h2
                className="font-bold text-neutral-900 mb-5 flex items-center gap-2 font-heading"
              >
                <User size={18} className="text-secondary-500" />
                Guest Details
              </h2>

              <div className="space-y-4">
                {/* Title + First Name + Last Name */}
                <div>
                  <label className="label">Guest Name *</label>
                  <div className="grid grid-cols-[84px_1fr_1fr] gap-2">
                    {/* Title select */}
                    <select
                      value={guestTitle}
                      onChange={(e) => setGuestTitle(e.target.value)}
                      className="input-field text-sm pr-1"
                    >
                      {TITLE_OPTIONS.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    {/* First Name */}
                    <input
                      type="text"
                      value={guestFirstName}
                      onChange={(e) => setGuestFirstName(e.target.value)}
                      placeholder=" "
                      className="input-field"
                      required
                    />
                    {/* Last Name */}
                    <input
                      type="text"
                      value={guestLastName}
                      onChange={(e) => setGuestLastName(e.target.value)}
                      placeholder=" "
                      className="input-field"
                    />
                  </div>
                  <p className="text-[11px] text-neutral-400 mt-1.5 flex items-center gap-1">
                    <Shield size={10} className="text-neutral-300" />
                    Enter name exactly as on government-issued ID
                  </p>
                </div>

                {/* Email + Phone */}
                <div className="grid sm:grid-cols-2 gap-3">
                  {/* Email */}
                  <div>
                    <label className="label">Email Address *</label>
                    <div className="relative">
                      <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
                      <input
                        type="email"
                        value={guestEmail}
                        onChange={(e) => setGuestEmail(e.target.value)}
                        placeholder=" "
                        className="input-field pl-9"
                        required
                      />
                    </div>
                  </div>

                  {/* Phone with +91 prefix */}
                  <div>
                    <label className="label">Phone Number *</label>
                    <div className="flex rounded-xl border border-neutral-200 focus-within:ring-2 focus-within:ring-primary-200 focus-within:border-primary-400 transition-all overflow-hidden bg-white">
                      <span className="flex items-center gap-1 px-3 bg-neutral-50 border-r border-neutral-200 text-xs font-semibold text-neutral-600 shrink-0 select-none">
                        <Phone size={11} className="text-neutral-400" />
                        +91
                      </span>
                      <input
                        type="tel"
                        value={guestPhone}
                        onChange={(e) => setGuestPhone(e.target.value)}
                        placeholder=" "
                        className="flex-1 px-3 py-2.5 text-sm bg-white outline-none text-neutral-900 placeholder-neutral-400"
                        maxLength={10}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Payment Method ─────────────────────────────────────── */}
            <div className="bg-white rounded-2xl shadow-card p-6">
              <h2
                className="font-bold text-neutral-900 mb-5 flex items-center gap-2 font-heading"
              >
                <CreditCard size={18} className="text-secondary-500" />
                Payment Method
              </h2>

              <div className="space-y-3">
                {([
                  { value: 'wallet', icon: Wallet, label: 'ZygoTrip Wallet', desc: 'Pay instantly using your wallet balance' },
                  { value: 'gateway', icon: CreditCard, label: 'Credit / Debit Card', desc: 'Visa, Mastercard, RuPay & UPI' },
                ] as const).map(({ value, icon: Icon, label, desc }) => (
                  <label
                    key={value}
                    className={clsx(
                      'flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all',
                      paymentMethod === value
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-neutral-200 bg-white hover:border-neutral-300'
                    )}
                  >
                    <input
                      type="radio"
                      name="payment"
                      value={value}
                      checked={paymentMethod === value}
                      onChange={() => setPaymentMethod(value)}
                      className="accent-primary-600 w-4 h-4 shrink-0"
                    />
                    <div className={clsx(
                      'w-10 h-10 rounded-xl flex items-center justify-center shrink-0',
                      paymentMethod === value ? 'bg-primary-100' : 'bg-neutral-100'
                    )}>
                      <Icon size={18} className={paymentMethod === value ? 'text-primary-600' : 'text-neutral-500'} />
                    </div>
                    <div>
                      <p className="font-semibold text-neutral-800 text-sm">{label}</p>
                      <p className="text-xs text-neutral-400">{desc}</p>
                    </div>
                  </label>
                ))}
              </div>

              <div className="flex items-center gap-2.5 mt-5 pt-4 border-t border-neutral-100">
                <Shield size={15} className="text-green-500 shrink-0" />
                <span className="text-xs text-neutral-400">
                  256-bit SSL encrypted. Your payment details are never stored on our servers.
                </span>
              </div>
            </div>

            {/* ── Confirm CTA ───────────────────────────────────────── */}
            <button
              onClick={handleConfirm}
              disabled={!canSubmit}
              className="btn-primary w-full text-base py-4 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="white" strokeWidth="4" />
                    <path className="opacity-75" fill="white" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z" />
                  </svg>
                  Confirming Booking...
                </>
              ) : (
                <>
                  <Lock size={16} />
                  Confirm &amp; Pay {fmt(context.final_price)}
                </>
              )}
            </button>

            {/* Trust badges row */}
            <div className="flex items-center justify-center gap-6 py-2">
              {[
                { icon: '🔒', label: 'Secure Payment' },
                { icon: '⚡', label: 'Instant Confirmation' },
                { icon: '📧', label: 'Email Voucher' },
              ].map(({ icon, label }) => (
                <div key={label} className="flex items-center gap-1.5 text-xs text-neutral-400 font-medium">
                  <span>{icon}</span>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ════════════════════════════════════════════════════════════
               RIGHT COLUMN — Booking summary + Price breakdown
          ════════════════════════════════════════════════════════════ */}
          <div className="space-y-5">
            <BookingSummary context={context} />
            <PriceBreakdown
              context={context}
              promoCode={promoCode}
              onPromoChange={setPromoCode}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BookingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="skeleton w-32 h-8 rounded" />
      </div>
    }>
      <BookingContent />
    </Suspense>
  );
}
