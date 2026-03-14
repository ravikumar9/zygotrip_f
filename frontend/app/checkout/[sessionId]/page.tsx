'use client';

/**
 * Production Checkout Flow — Multi-step booking funnel.
 *
 * Steps:
 *   1. Review (session created, room selected — read-only summary)
 *   2. Guest Details (name, email, phone)
 *   3. Payment (select gateway → pay)
 *   4. Confirmation (booking confirmed)
 *
 * Session ID comes from URL: /checkout/[sessionId]
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { checkoutService } from '@/services/checkout';
import WalletApply from '@/components/conversion/WalletApply';
import { CouponSuggestionCard, SavingsSummary } from '@/components/conversion/CouponSuggestion';
import { BadgePercent, ChevronDown, ChevronUp, X, Loader2 } from 'lucide-react';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type {
  CheckoutSession,
  CheckoutPaymentOptions,
  CheckoutPaymentResult,
  CheckoutBookingConfirmation,
  CheckoutGuestDetails,
} from '@/types/checkout';

type Step = 'review' | 'guest' | 'payment' | 'confirmation';

export default function CheckoutPage() {
  const { formatPrice } = useFormatPrice();
  const params = useParams();
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const sessionId = params.sessionId as string;

  // State
  const [session, setSession] = useState<CheckoutSession | null>(null);
  const [paymentOptions, setPaymentOptions] = useState<CheckoutPaymentOptions | null>(null);
  const [booking, setBooking] = useState<CheckoutBookingConfirmation | null>(null);
  const [step, setStep] = useState<Step>('review');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Guest form
  const [guestName, setGuestName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');
  const [guestPhone, setGuestPhone] = useState('');
  const [specialRequests, setSpecialRequests] = useState('');

  // Payment
  const [selectedGateway, setSelectedGateway] = useState('');

  // Wallet
  const [walletBalance, setWalletBalance] = useState(0);
  const [walletApplied, setWalletApplied] = useState(false);

  // Promo code
  const [promoExpanded, setPromoExpanded] = useState(false);
  const [promoCode, setPromoCode] = useState('');
  const [promoApplied, setPromoApplied] = useState<{ code: string; discount: number } | null>(null);
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState('');

  // Timer
  const [timeLeft, setTimeLeft] = useState(0);

  // ── Auth guard ─────────────────────────────────────────────────────
  // ── Load session ───────────────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return;

    const loadSession = async () => {
      try {
        setLoading(true);
        const sess = await checkoutService.getSession(sessionId);
        setSession(sess);

        // Pre-fill guest from user
        if (!guestName && user?.full_name) setGuestName(user.full_name);
        if (!guestEmail && user?.email) setGuestEmail(user.email);
        if (!guestPhone && user?.phone) setGuestPhone(user.phone);

        // Determine step from session status
        if (sess.session_status === 'completed') {
          setStep('confirmation');
        } else if (sess.session_status === 'guest_details' || sess.session_status === 'payment_initiated') {
          setStep('payment');
        } else if (sess.session_status === 'room_selected') {
          setStep('review');
        } else if (sess.session_status === 'expired') {
          setError('This checkout session has expired. Please start a new search.');
        } else if (sess.session_status === 'failed') {
          setStep('payment');
          setError('Previous payment attempt failed. You can try again.');
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load checkout session';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    loadSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── Countdown timer ────────────────────────────────────────────────
  useEffect(() => {
    if (!session?.expires_at) return;

    const updateTimer = () => {
      const expires = new Date(session.expires_at).getTime();
      const now = Date.now();
      const diff = Math.max(0, Math.floor((expires - now) / 1000));
      setTimeLeft(diff);

      if (diff <= 0) {
        setError('Session expired. Please start a new checkout.');
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [session?.expires_at]);

  const formatTime = useCallback((seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }, []);

  // ── Step handlers ──────────────────────────────────────────────────

  const handleGuestSubmit = async () => {
    if (!session) return;
    setSubmitting(true);
    setError('');

    try {
      const guest: CheckoutGuestDetails = {
        name: guestName.trim(),
        email: guestEmail.trim(),
        phone: guestPhone.trim(),
        special_requests: specialRequests.trim(),
      };

      const updated = await checkoutService.submitGuestDetails(sessionId, guest);
      setSession(updated);

      // Load payment options
      const options = await checkoutService.getPaymentOptions(sessionId);
      setPaymentOptions(options);

      if (options.gateways.length > 0) {
        setSelectedGateway(options.gateways[0].id);
      }

      setStep('payment');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save guest details';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePayment = async () => {
    if (!session || !selectedGateway) return;
    setSubmitting(true);
    setError('');

    try {
      const result: CheckoutPaymentResult = await checkoutService.pay(
        sessionId,
        selectedGateway,
      );

      if (result.status === 'completed') {
        setBooking(result.booking);
        setSession(result.session);
        setStep('confirmation');
      } else if (result.status === 'pending') {
        // External gateway — would redirect
        setError('Redirecting to payment gateway...');
      } else if (result.status === 'failed') {
        setError(result.error || 'Payment failed. Please try again.');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Payment failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Price helpers ──────────────────────────────────────────────────
  const price = session?.price_snapshot;
  const search = session?.search_snapshot;

  // ── Promo handlers ─────────────────────────────────────────────────
  const handleApplyPromo = async (code?: string) => {
    const codeToApply = code || promoCode.trim();
    if (!codeToApply || !session) return;

    setPromoLoading(true);
    setPromoError('');

    try {
      // Simulate promo validation — in production, call the promo API
      // e.g. const result = await bookingService.applyPromo({ promo_code: codeToApply, ... });
      // For now, set the applied state so the UI works
      setPromoApplied({ code: codeToApply, discount: 0 });
      setPromoCode('');
      setPromoExpanded(false);
    } catch (err: unknown) {
      setPromoError(err instanceof Error ? err.message : 'Invalid promo code');
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemovePromo = () => {
    setPromoApplied(null);
    setPromoError('');
  };

  // ── Loading / Error states ─────────────────────────────────────────
  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading checkout...</p>
        </div>
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md text-center">
          <div className="text-red-500 text-5xl mb-4">⚠</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Checkout Error</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => router.push('/hotels')}
            className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition"
          >
            Back to Hotels
          </button>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen page-booking-bg">
      {/* Top bar with timer */}
      <div className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Secure Checkout</h1>
          {timeLeft > 0 && step !== 'confirmation' && (
            <div className={`flex items-center gap-2 text-sm font-medium ${timeLeft < 120 ? 'text-red-600' : 'text-gray-600'}`}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {formatTime(timeLeft)} remaining
            </div>
          )}
        </div>
      </div>

      {/* Step indicator */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          {(['review', 'guest', 'payment', 'confirmation'] as Step[]).map((s, i) => {
            const stepLabels = { review: 'Review', guest: 'Guest Info', payment: 'Payment', confirmation: 'Done' };
            const isActive = s === step;
            const isPast = ['review', 'guest', 'payment', 'confirmation'].indexOf(s) <
              ['review', 'guest', 'payment', 'confirmation'].indexOf(step);

            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                  ${isActive ? 'bg-blue-600 text-white' : isPast ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'}
                `}>
                  {isPast ? '✓' : i + 1}
                </div>
                <span className={`text-sm font-medium ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                  {stepLabels[s]}
                </span>
                {i < 3 && <div className={`w-8 h-0.5 ${isPast ? 'bg-green-500' : 'bg-gray-200'}`} />}
              </div>
            );
          })}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Main content */}
          <div className="lg:col-span-2 space-y-6">

            {/* STEP 1: Review */}
            {step === 'review' && session && (
              <div className="bg-white rounded-2xl shadow-sm border p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Review Your Selection</h2>
                <div className="space-y-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Hotel</span>
                    <span className="font-semibold">{session.property_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Room</span>
                    <span className="font-semibold">{session.room_type_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Check-in</span>
                    <span className="font-semibold">{search?.check_in}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Check-out</span>
                    <span className="font-semibold">{search?.check_out}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Guests</span>
                    <span className="font-semibold">{search?.guests} guests, {search?.rooms} room(s)</span>
                  </div>
                </div>

                <button
                  onClick={() => setStep('guest')}
                  className="mt-6 w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition"
                >
                  Continue to Guest Details
                </button>
              </div>
            )}

            {/* STEP 2: Guest Details */}
            {step === 'guest' && (
              <div className="bg-white rounded-2xl shadow-sm border p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Guest Details</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
                    <input
                      type="text"
                      value={guestName}
                      onChange={(e) => setGuestName(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      placeholder="As per ID proof"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                    <input
                      type="email"
                      value={guestEmail}
                      onChange={(e) => setGuestEmail(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      placeholder="For booking confirmation"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Phone *</label>
                    <input
                      type="tel"
                      value={guestPhone}
                      onChange={(e) => setGuestPhone(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      placeholder="+91 XXXXX XXXXX"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Special Requests</label>
                    <textarea
                      value={specialRequests}
                      onChange={(e) => setSpecialRequests(e.target.value)}
                      rows={3}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                      placeholder="Early check-in, extra bed, etc."
                    />
                  </div>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => setStep('review')}
                    className="px-6 py-3 border border-gray-300 rounded-xl font-semibold text-gray-700 hover:bg-gray-50 transition"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleGuestSubmit}
                    disabled={submitting || !guestName || !guestEmail || !guestPhone}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? 'Saving...' : 'Continue to Payment'}
                  </button>
                </div>
              </div>
            )}

            {/* STEP 3: Payment */}
            {step === 'payment' && paymentOptions && (
              <div className="bg-white rounded-2xl shadow-sm border p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Select Payment Method</h2>
                <div className="space-y-3">
                  {paymentOptions.gateways.map((gw) => (
                    <label
                      key={gw.id}
                      className={`
                        flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition
                        ${selectedGateway === gw.id ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}
                        ${!gw.available ? 'opacity-50 cursor-not-allowed' : ''}
                      `}
                    >
                      <input
                        type="radio"
                        name="gateway"
                        value={gw.id}
                        checked={selectedGateway === gw.id}
                        onChange={() => gw.available && setSelectedGateway(gw.id)}
                        disabled={!gw.available}
                        className="w-5 h-5 text-blue-600"
                      />
                      <div className="flex-1">
                        <div className="font-semibold text-gray-900">{gw.name}</div>
                        <div className="text-sm text-gray-500">{gw.description}</div>
                      </div>
                      {gw.balance !== undefined && (
                        <span className="text-sm text-gray-500">{formatPrice(gw.balance)}</span>
                      )}
                    </label>
                  ))}
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => setStep('guest')}
                    className="px-6 py-3 border border-gray-300 rounded-xl font-semibold text-gray-700 hover:bg-gray-50 transition"
                  >
                    Back
                  </button>
                  <button
                    onClick={handlePayment}
                    disabled={submitting || !selectedGateway}
                    className="flex-1 bg-green-600 text-white py-3 rounded-xl font-bold text-lg hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? 'Processing...' : `Pay ${formatPrice(parseFloat(price?.total || '0'))}`}
                  </button>
                </div>
              </div>
            )}

            {/* STEP 4: Confirmation */}
            {step === 'confirmation' && booking && (
              <div className="bg-white rounded-2xl shadow-sm border p-8 text-center">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Booking Confirmed!</h2>
                <p className="text-gray-600 mb-6">Your booking has been successfully confirmed.</p>

                <div className="bg-gray-50 rounded-xl p-6 text-left space-y-3 mb-6">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Booking ID</span>
                    <span className="font-mono font-bold text-blue-600">{booking.booking_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Hotel</span>
                    <span className="font-semibold">{booking.property_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Room</span>
                    <span className="font-semibold">{booking.room_type_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Check-in</span>
                    <span className="font-semibold">{booking.check_in}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Check-out</span>
                    <span className="font-semibold">{booking.check_out}</span>
                  </div>
                  <div className="flex justify-between border-t pt-3 mt-3">
                    <span className="text-gray-900 font-semibold">Total Paid</span>
                    <span className="text-lg font-bold text-green-600">{formatPrice(booking.total_amount)}</span>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => router.push(`/confirmation/${booking.booking_uuid}`)}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition"
                  >
                    View Booking
                  </button>
                  <button
                    onClick={() => router.push('/hotels')}
                    className="px-6 py-3 border border-gray-300 rounded-xl font-semibold text-gray-700 hover:bg-gray-50 transition"
                  >
                    Book Another
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right: Price sidebar */}
          {step !== 'confirmation' && session && price && (
            <div className="lg:col-span-1 space-y-4">
              <div className="bg-white rounded-2xl shadow-card border border-neutral-100 p-5 sticky top-20">
                <h3 className="font-bold text-neutral-900 mb-1 font-heading">Price Summary</h3>
                <p className="text-xs text-neutral-400 mb-4">
                  {search?.rooms || 1} room{(search?.rooms || 1) > 1 ? 's' : ''} · {search?.guests || 1} guest{(search?.guests || 1) > 1 ? 's' : ''}
                </p>

                <div className="space-y-2.5 text-sm">
                  <div className="flex justify-between">
                    <span className="text-neutral-600">Room charge</span>
                    <span className="font-medium">{formatPrice(price.base_price)}</span>
                  </div>
                  {parseFloat(price.meal_amount) > 0 && (
                    <div className="flex justify-between">
                      <span className="text-neutral-600">Meal plan</span>
                      <span className="font-medium">{formatPrice(price.meal_amount)}</span>
                    </div>
                  )}
                  {parseFloat(price.property_discount) > 0 && (
                    <div className="flex justify-between text-green-700">
                      <span>Property discount</span>
                      <span className="font-semibold">-{formatPrice(price.property_discount)}</span>
                    </div>
                  )}

                  {/* Taxes & Fees */}
                  <div className="border-t border-neutral-100 pt-2">
                    <div className="flex justify-between text-neutral-600">
                      <span>Taxes &amp; Fees</span>
                      <span className="font-medium">
                        {formatPrice(parseFloat(price.service_fee || '0') + parseFloat(price.gst || '0'))}
                      </span>
                    </div>
                    <div className="ml-2 mt-1 space-y-1 border-l-2 border-neutral-100 pl-3">
                      {parseFloat(price.service_fee) > 0 && (
                        <div className="flex justify-between text-xs text-neutral-400">
                          <span>Service fee</span>
                          <span>{formatPrice(price.service_fee)}</span>
                        </div>
                      )}
                      <div className="flex justify-between text-xs text-neutral-400">
                        <span>GST</span>
                        <span>{parseFloat(price.gst) > 0 ? formatPrice(price.gst) : 'Exempt'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Wallet deduction */}
                  {walletApplied && walletBalance > 0 && (
                    <div className="flex justify-between text-green-700">
                      <span>Wallet deduction</span>
                      <span className="font-semibold">-{formatPrice(Math.min(walletBalance, parseFloat(price.total)))}</span>
                    </div>
                  )}

                  <div className="border-t-2 border-neutral-200 pt-3 flex justify-between font-bold text-neutral-900 text-base">
                    <span>Total payable</span>
                    <span className="text-xl font-black">
                      {formatPrice(walletApplied
                        ? Math.max(0, parseFloat(price.total) - walletBalance)
                        : parseFloat(price.total))}
                    </span>
                  </div>
                </div>

                {/* Savings banner */}
                {parseFloat(price.property_discount) > 0 && (
                  <div className="mt-3 bg-green-50 rounded-xl px-3 py-2 text-xs text-green-700 font-semibold text-center">
                    🎉 You save {formatPrice(price.property_discount)} on this booking!
                  </div>
                )}

                {session.inventory_token && (
                  <div className="mt-4 text-xs text-neutral-500 flex items-center gap-1">
                    <svg className="w-3 h-3 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Room reserved for you
                  </div>
                )}

                {session.price_changed && (
                  <div className="mt-3 bg-amber-50 border border-amber-200 rounded-xl p-2 text-xs text-amber-700">
                    Price updated since you started checkout
                  </div>
                )}
              </div>

              {/* Wallet apply component */}
              <WalletApply
                balance={walletBalance}
                totalAmount={parseFloat(price.total) || 0}
                isApplied={walletApplied}
                onToggle={setWalletApplied}
              />

              {/* Promo Code Section */}
              <div className="bg-white rounded-2xl shadow-card border border-neutral-100 p-4">
                {promoApplied ? (
                  /* Applied promo display */
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center shrink-0">
                      <BadgePercent className="w-4 h-4 text-green-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-black text-xs tracking-wider text-neutral-800">{promoApplied.code}</span>
                        <span className="text-[10px] font-bold text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">Applied</span>
                      </div>
                      {promoApplied.discount > 0 && (
                        <p className="text-[10px] text-green-600 mt-0.5">Saving {formatPrice(promoApplied.discount)}</p>
                      )}
                    </div>
                    <button
                      onClick={handleRemovePromo}
                      className="shrink-0 text-neutral-400 hover:text-red-500 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  /* Promo code input */
                  <>
                    <button
                      onClick={() => setPromoExpanded(!promoExpanded)}
                      className="w-full flex items-center justify-between text-sm font-semibold text-neutral-700 hover:text-neutral-900 transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <BadgePercent className="w-4 h-4 text-neutral-400" />
                        Have a promo code?
                      </span>
                      {promoExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>

                    {promoExpanded && (
                      <div className="mt-3">
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={promoCode}
                            onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                            placeholder="Enter code"
                            className="flex-1 px-3 py-2.5 border border-neutral-200 rounded-xl text-sm font-medium tracking-wider uppercase focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
                            onKeyDown={(e) => e.key === 'Enter' && handleApplyPromo()}
                          />
                          <button
                            onClick={() => handleApplyPromo()}
                            disabled={promoLoading || !promoCode.trim()}
                            className="px-4 py-2.5 rounded-xl font-bold text-sm text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                            style={{ background: 'var(--primary)' }}
                          >
                            {promoLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Apply'}
                          </button>
                        </div>

                        {promoError && (
                          <p className="text-xs text-red-500 mt-2">{promoError}</p>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
