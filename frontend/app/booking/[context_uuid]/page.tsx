'use client';

import { useState, useEffect, Suspense } from 'react';
import { useParams, useRouter, usePathname } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import { checkoutService } from '@/services/checkout';
import { getWalletBalance } from '@/services/wallet';
import BookingSummary from '@/components/booking/BookingSummary';
import PriceBreakdown from '@/components/booking/PriceBreakdown';
import {
  Shield, CheckCircle, CreditCard, Wallet,
  ArrowLeft, User, Mail, Phone, Lock,
  Gift, Sparkles, Clock, Tag, QrCode, Building2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';
import { format, parseISO, isValid } from 'date-fns';
import clsx from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { savePendingBooking, clearPendingBooking } from '@/components/booking/AbandonmentBanner';
import { analytics } from '@/lib/analytics';

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

// ── Hold Countdown Timer (extracted to respect React rules of hooks) ─────

function HoldCountdownTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState('');
  const [isExpired, setIsExpired] = useState(false);
  const [isUrgent, setIsUrgent] = useState(false);

  useEffect(() => {
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) {
        setIsExpired(true);
        setRemaining('Expired');
        return;
      }
      setIsUrgent(diff < 2 * 60 * 1000); // < 2 min
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setRemaining(`${mins}:${secs.toString().padStart(2, '0')}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  return (
    <div className={clsx(
      'flex items-center gap-2 rounded-xl px-4 py-2.5 border',
      isExpired
        ? 'bg-red-50 border-red-200'
        : isUrgent
          ? 'bg-red-50 border-red-200 animate-pulse'
          : 'bg-amber-50 border-amber-200'
    )}>
      <Clock size={14} className={clsx(
        'shrink-0',
        isExpired ? 'text-red-600' : isUrgent ? 'text-red-600 animate-pulse' : 'text-amber-600 animate-pulse'
      )} />
      <p className={clsx(
        'text-xs font-semibold',
        isExpired ? 'text-red-700' : isUrgent ? 'text-red-700' : 'text-amber-700'
      )}>
        {isExpired
          ? 'Session expired — please start a new booking'
          : <>Price locked — <span className="font-mono">{remaining}</span> remaining to complete booking</>
        }
      </p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

function BookingContent() {
  const { formatPrice: fmt } = useFormatPrice();
  const { context_uuid } = useParams<{ context_uuid: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  // ── No auth guard — guest checkout is supported ───────────────────────

  // ── UI state ──────────────────────────────────────────────────────────
  const [paymentMethod, setPaymentMethod] = useState<'wallet' | 'gateway'>('gateway');
  const [promoCode, setPromoCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [redirectingToCheckout, setRedirectingToCheckout] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState<{
    uuid: string; public_booking_id: string; status?: string;
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

  // ── Wallet balance query (only for authenticated users) ───────────────
  const { data: walletData } = useQuery({
    queryKey: ['wallet-balance'],
    queryFn: getWalletBalance,
    enabled: isAuthenticated,
    staleTime: 30_000,
    retry: 1,
  });
  const walletBalance = Number(walletData?.balance) || 0;
  const [useWallet, setUseWallet] = useState(false);

  // ── Save pending booking for abandonment recovery (Step 24) ──────────
  useEffect(() => {
    if (!context || !context_uuid) return;
    savePendingBooking({
      contextUuid: context_uuid,
      propertyName: context.property_name || 'Your hotel',
      checkin: context.checkin || '',
      checkout: context.checkout || '',
    });
  }, [context, context_uuid]);

  useEffect(() => {
    if (!context || !context.room_type_id || redirectingToCheckout) return;
    const roomTypeId = context.room_type_id;

    let cancelled = false;
    const moveToCanonicalCheckout = async () => {
      try {
        setRedirectingToCheckout(true);
        const session = await checkoutService.startCheckout({
          property_id: context.property_id,
          room_type_id: roomTypeId,
          check_in: context.checkin,
          check_out: context.checkout,
          guests: context.adults,
          rooms: context.rooms,
          rate_plan_id: context.rate_plan_id,
          meal_plan_code: context.meal_plan,
          promo_code: context.promo_code,
        });

        if (!cancelled) {
          router.replace(`/checkout/${session.session_id}`);
        }
      } catch {
        if (!cancelled) {
          setRedirectingToCheckout(false);
        }
      }
    };

    moveToCanonicalCheckout();

    return () => {
      cancelled = true;
    };
  }, [context, redirectingToCheckout, router]);

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
      analytics.track('booking_started', {
        context_uuid,
        payment_method: paymentMethod,
        property_name: context.property_name,
        amount: Number(context.final_price),
      });

      const booking = await bookingsService.confirmBooking({
        context_uuid,
        payment_method: paymentMethod,
        guest_name: fullName,
        guest_email: guestEmail,
        guest_phone: guestPhone,
        use_wallet: useWallet,
        idempotency_key: `ctx-${context_uuid}-${Date.now()}`,
      });

      // Invalidate wallet balance so it refreshes
      queryClient.invalidateQueries({ queryKey: ['wallet-balance'] });
      clearPendingBooking(); // Remove abandonment state on success

      analytics.track('booking_completed', {
        booking_uuid: booking.uuid,
        booking_id: booking.public_booking_id,
        status: booking.status,
        payment_method: paymentMethod,
      });

      // For gateway payments (status=hold), redirect to payment page
      // For wallet payments (status=confirmed), show inline success
      if (booking.status !== 'confirmed') {
        router.push(`/payment/${booking.uuid}`);
        return;
      }

      setConfirmedBooking({
        uuid: booking.uuid,
        public_booking_id: booking.public_booking_id,
        status: booking.status,
      });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ??
        (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail ??
        'Booking failed. Please try again.';
      toast.error(msg, { duration: 6000 });
      analytics.track('booking_failed', { error: msg, context_uuid });
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

  if (ctxLoading || redirectingToCheckout) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center">
        <div className="text-center">
          <div className="skeleton w-16 h-16 rounded-full mx-auto mb-4" />
          <p className="text-neutral-500 font-medium">
            {redirectingToCheckout ? 'Redirecting to secure checkout...' : 'Loading your booking...'}
          </p>
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
    const isConfirmed = confirmedBooking.status === 'confirmed';
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center animate-fade-up">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
            style={{ background: isConfirmed ? 'linear-gradient(135deg, #10b981, #059669)' : 'linear-gradient(135deg, #f59e0b, #d97706)' }}>
            <CheckCircle size={36} stroke="white" />
          </div>
          <h1 className="text-3xl font-black text-neutral-900 mb-2 font-heading">
            {isConfirmed ? 'Booking Confirmed! \uD83C\uDF89' : 'Booking Created!'}
          </h1>
          <p className="text-neutral-500 mb-6">
            {isConfirmed
              ? `Your reservation at ${context?.property_name ?? 'the hotel'} is confirmed. Payment received.`
              : `Your reservation at ${context?.property_name ?? 'the hotel'} has been created. Complete payment to confirm.`
            }
          </p>

          <div className="bg-white/80 rounded-2xl shadow-card p-6 mb-6 text-left">
            <p className="text-xs text-neutral-400 mb-1 text-center">Booking ID</p>
            <p className="text-2xl font-black text-primary-700 mb-5 text-center font-heading">
              {confirmedBooking.public_booking_id}
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-page rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Property</p>
                <p className="font-bold text-neutral-800">{context.property_name}</p>
              </div>
              <div className="bg-page rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Total Paid</p>
                <p className="font-bold text-neutral-800">{fmt(context?.final_price ?? 0)}</p>
              </div>
              <div className="bg-page rounded-xl p-3">
                <p className="text-neutral-400 text-xs mb-0.5">Check-in</p>
                <p className="font-bold text-neutral-800">{context.checkin}</p>
              </div>
              <div className="bg-page rounded-xl p-3">
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

          {/* Cashback earned hint */}
          <div className="mt-4 bg-green-50 rounded-xl px-4 py-3 border border-green-100 text-center">
            <Sparkles size={14} className="inline text-green-500 mr-1" />
            <span className="text-xs font-semibold text-green-700">
              Cashback will be credited to your ZygoTrip Wallet within 24 hours
            </span>
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
            className="p-2 rounded-xl hover:bg-white/80 hover:shadow-sm transition-all"
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
            <div className="bg-white/80 rounded-2xl shadow-card overflow-hidden border border-neutral-100">
              {/* Dark gradient header */}
              <div
                className="flex items-center gap-4 p-4"
                style={{ background: 'linear-gradient(90deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)' }}
              >
                <div className="w-12 h-12 rounded-xl bg-white/80/15 flex items-center justify-center text-2xl shrink-0">
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
            <div className="bg-white/80 rounded-2xl shadow-card p-6">
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
                    <div className="flex rounded-xl border border-neutral-200 focus-within:ring-2 focus-within:ring-primary-200 focus-within:border-primary-400 transition-all overflow-hidden bg-white/80">
                      <span className="flex items-center gap-1 px-3 bg-page border-r border-neutral-200 text-xs font-semibold text-neutral-600 shrink-0 select-none">
                        <Phone size={11} className="text-neutral-400" />
                        +91
                      </span>
                      <input
                        type="tel"
                        value={guestPhone}
                        onChange={(e) => setGuestPhone(e.target.value)}
                        placeholder=" "
                        className="flex-1 px-3 py-2.5 text-sm bg-white/80 outline-none text-neutral-900 placeholder-neutral-400"
                        maxLength={10}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Payment Method ─────────────────────────────────────── */}
            <div className="bg-white/80 rounded-2xl shadow-card p-6">
              <h2
                className="font-bold text-neutral-900 mb-5 flex items-center gap-2 font-heading"
              >
                <CreditCard size={18} className="text-secondary-500" />
                Payment Method
              </h2>

              {/* Wallet Card — different treatment for auth vs guest */}
              {isAuthenticated && walletBalance > 0 ? (
                <div className={clsx(
                  'mb-4 rounded-xl border-2 p-4 transition-all',
                  useWallet ? 'border-green-400 bg-green-50' : 'border-neutral-200 bg-page'
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={clsx(
                        'w-8 h-8 rounded-lg flex items-center justify-center',
                        useWallet ? 'bg-green-100' : 'bg-neutral-200'
                      )}>
                        <Wallet size={16} className={useWallet ? 'text-green-600' : 'text-neutral-500'} />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-neutral-800">ZygoTrip Wallet</p>
                        <p className="text-xs text-neutral-500">Available: <span className="font-bold text-green-600">{fmt(walletBalance)}</span></p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        const next = !useWallet;
                        setUseWallet(next);
                        analytics.track('wallet_applied', { applied: next, balance: walletBalance });
                      }}
                      className={clsx(
                        'text-xs font-bold px-3 py-1.5 rounded-lg transition-all',
                        useWallet
                          ? 'bg-green-600 text-white'
                          : 'bg-white/80 border border-neutral-300 text-neutral-700 hover:border-green-400 hover:text-green-600'
                      )}
                    >
                      {useWallet ? '✓ Applied' : 'Use Wallet'}
                    </button>
                  </div>
                  {useWallet && context && (
                    <div className="text-xs text-green-700 bg-green-100 rounded-lg px-3 py-2 mt-2">
                      <Sparkles size={10} className="inline mr-1" />
                      {walletBalance >= Number(context.final_price)
                        ? <>Full amount will be paid from wallet — no card needed!</>
                        : <>{fmt(Math.min(walletBalance, Number(context.final_price)))} from wallet, rest via card/UPI</>
                      }
                    </div>
                  )}
                </div>
              ) : !isAuthenticated ? (
                /* Guest user — wallet disabled with login CTA */
                <div className="mb-4 rounded-xl border-2 border-neutral-200 bg-page p-4 opacity-75">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-neutral-200">
                        <Wallet size={16} className="text-neutral-400" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-neutral-500">ZygoTrip Wallet</p>
                        <p className="text-[11px] text-neutral-400">Login or create an account to use wallet balance</p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        analytics.track('login_started', { source: 'checkout_wallet' });
                        router.push(`/account/login?next=${pathname}`);
                      }}
                      className="text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 rounded-lg transition-colors shrink-0"
                    >
                      Sign In
                    </button>
                  </div>
                </div>
              ) : null}

              {/* Payment method cards */}
              <div className="space-y-3">
                {([
                  {
                    value: 'wallet' as const,
                    icon: Wallet,
                    label: 'ZygoTrip Wallet',
                    desc: 'Pay instantly using your wallet balance',
                    disabled: !isAuthenticated || walletBalance <= 0,
                  },
                  {
                    value: 'gateway' as const,
                    icon: CreditCard,
                    label: 'Credit / Debit Card',
                    desc: 'Visa, Mastercard, RuPay — secure card payments',
                    disabled: false,
                  },
                ] as const).map(({ value, icon: Icon, label, desc, disabled }) => {
                  const isSelected = paymentMethod === value;
                  const isWalletDisabled = value === 'wallet' && disabled;

                  return (
                    <label
                      key={value}
                      className={clsx(
                        'flex items-center gap-4 p-4 rounded-xl border-2 transition-all',
                        isWalletDisabled
                          ? 'border-neutral-200 bg-page opacity-50 cursor-not-allowed'
                          : isSelected
                            ? 'border-primary-500 bg-primary-50 cursor-pointer'
                            : 'border-neutral-200 bg-white/80 hover:border-neutral-300 cursor-pointer'
                      )}
                    >
                      <input
                        type="radio"
                        name="payment"
                        value={value}
                        checked={isSelected}
                        onChange={() => {
                          if (!isWalletDisabled) {
                            setPaymentMethod(value);
                            analytics.track('payment_initiated', { method: value });
                          }
                        }}
                        disabled={isWalletDisabled}
                        className="accent-primary-600 w-4 h-4 shrink-0"
                      />
                      <div className={clsx(
                        'w-10 h-10 rounded-xl flex items-center justify-center shrink-0',
                        isWalletDisabled ? 'bg-neutral-100' : isSelected ? 'bg-primary-100' : 'bg-neutral-100'
                      )}>
                        <Icon size={18} className={isWalletDisabled ? 'text-neutral-400' : isSelected ? 'text-primary-600' : 'text-neutral-500'} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={clsx('font-semibold text-sm', isWalletDisabled ? 'text-neutral-400' : 'text-neutral-800')}>{label}</p>
                        <p className="text-xs text-neutral-400">{isWalletDisabled && !isAuthenticated ? 'Login to use wallet' : desc}</p>
                      </div>
                      {value === 'wallet' && isAuthenticated && walletBalance > 0 && (
                        <span className="text-[10px] font-bold text-green-700 bg-green-100 px-2 py-1 rounded-lg shrink-0">Instant</span>
                      )}
                    </label>
                  );
                })}
              </div>

              <div className="flex items-center gap-2.5 mt-5 pt-4 border-t border-neutral-100">
                <Shield size={15} className="text-green-500 shrink-0" />
                <span className="text-xs text-neutral-400">
                  256-bit SSL encrypted. Your payment details are never stored on our servers.
                </span>
              </div>
            </div>

            {/* ── Savings & Urgency Section ───────────────────────── */}
            {context && (() => {
              const totalDiscount = Number(context.property_discount || 0) + Number(context.platform_discount || 0) + Number(context.promo_discount || 0);
              const walletDeduction = useWallet ? Math.min(walletBalance, Number(context.final_price)) : 0;
              const totalSavings = totalDiscount + walletDeduction;
              return totalSavings > 0 ? (
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl border border-green-200 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Gift size={16} className="text-green-600" />
                    <p className="text-sm font-bold text-green-800">Your Savings on this Booking</p>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    {totalDiscount > 0 && (
                      <div className="flex justify-between text-green-700">
                        <span>Room discount + promo</span>
                        <span className="font-bold">-{fmt(totalDiscount)}</span>
                      </div>
                    )}
                    {walletDeduction > 0 && (
                      <div className="flex justify-between text-green-700">
                        <span>Wallet applied</span>
                        <span className="font-bold">-{fmt(walletDeduction)}</span>
                      </div>
                    )}
                    <div className="border-t border-green-200 pt-1.5 flex justify-between text-green-800 font-bold text-sm">
                      <span>Total savings</span>
                      <span>{fmt(totalSavings)}</span>
                    </div>
                  </div>
                </div>
              ) : null;
            })()}

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
              walletDeduction={useWallet ? Math.min(walletBalance, Number(context.final_price)) : 0}
            />
            {/* ── Countdown Timer — right column ─────────────── */}
            {context?.expires_at && (
              <HoldCountdownTimer expiresAt={context.expires_at} />
            )}
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
