'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Shield, Clock, ChevronRight, Check, AlertCircle, CreditCard, Loader2 } from 'lucide-react';

import { checkoutService } from '@/services/checkout';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import BookingSummary from '@/components/booking/BookingSummary';
import PriceBreakdown from '@/components/booking/PriceBreakdown';
import WalletApply from '@/components/conversion/WalletApply';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import Skeleton from '@/components/ui/Skeleton';
import type {
  CheckoutSession,
  CheckoutGuestDetails,
  CheckoutPaymentOptions,
} from '@/types/checkout';
import type { BookingContext } from '@/types';

type CheckoutStep = 'guest-details' | 'payment';

function HoldTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState('');
  const [isWarning, setIsWarning] = useState(false);

  useEffect(() => {
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining('Expired');
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setIsWarning(diff < 3 * 60 * 1000);
      setRemaining(`${mins}:${secs.toString().padStart(2, '0')}`);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  return (
    <div
      className={`flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-full ${
        isWarning
          ? 'bg-red-50 text-red-700 border border-red-200'
          : 'bg-amber-50 text-amber-700 border border-amber-200'
      }`}
    >
      <Clock size={14} />
      Price locked for {remaining}
    </div>
  );
}

function toBookingContext(session: CheckoutSession): BookingContext {
  return {
    id: 0,
    uuid: session.session_id,
    property_id: session.property_id,
    property_name: session.property_name,
    property_slug: '',
    room_type_id: session.room_type_id,
    room_type_name: session.room_type_name,
    checkin: session.search_snapshot.check_in,
    checkout: session.search_snapshot.check_out,
    nights:
      Math.max(
        1,
        Math.ceil(
          (new Date(session.search_snapshot.check_out).getTime() -
            new Date(session.search_snapshot.check_in).getTime()) /
            (24 * 60 * 60 * 1000),
        ),
      ) || 1,
    adults: session.search_snapshot.guests,
    children: 0,
    rooms: session.search_snapshot.rooms,
    meal_plan: session.search_snapshot.meal_plan_code || 'R',
    base_price: session.price_snapshot.base_price,
    meal_amount: session.price_snapshot.meal_amount,
    property_discount: session.price_snapshot.property_discount,
    platform_discount: session.price_snapshot.platform_discount,
    promo_discount: '0',
    tax: session.price_snapshot.gst,
    service_fee: session.price_snapshot.service_fee,
    final_price: session.price_snapshot.total,
    price_locked: true,
    locked_price: session.price_snapshot.total,
    price_expires_at: session.expires_at,
    rate_plan_id: '',
    supplier_id: '',
    gst_amount: session.price_snapshot.gst,
    gst_percentage: session.price_snapshot.gst && Number(session.price_snapshot.gst) > 0 ? '18' : '0',
    total_price: session.price_snapshot.total,
    promo_code: session.search_snapshot.promo_code || '',
    context_status: 'active',
    expires_at: session.expires_at,
    created_at: session.created_at,
  };
}

export default function CheckoutSessionPage() {
  const params = useParams();
  const router = useRouter();
  const { formatPrice } = useFormatPrice();
  const sessionId = typeof params.sessionId === 'string' ? params.sessionId : '';

  const [step, setStep] = useState<CheckoutStep>('guest-details');
  const [guestDetails, setGuestDetails] = useState({
    name: '',
    email: '',
    phone: '',
    special_requests: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [selectedGateway, setSelectedGateway] = useState<string>('cashfree');
  const [walletApplied, setWalletApplied] = useState(false);
  const [walletAmount, setWalletAmount] = useState(0);

  const {
    data: session,
    isLoading,
    error: sessionError,
  } = useQuery({
    queryKey: ['checkout-session', sessionId],
    queryFn: () => checkoutService.getSession(sessionId),
    enabled: !!sessionId,
    refetchInterval: 30000,
  });

  const { data: paymentOptions } = useQuery<CheckoutPaymentOptions>({
    queryKey: ['payment-options', sessionId],
    queryFn: () => checkoutService.getPaymentOptions(sessionId),
    enabled: !!sessionId && step === 'payment',
  });

  const submitGuestMutation = useMutation({
    mutationFn: (details: CheckoutGuestDetails) =>
      checkoutService.submitGuestDetails(sessionId, details),
    onSuccess: () => {
      setStep('payment');
      setErrors({});
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error || 'Could not save guest details.';
      setErrors({ general: msg });
    },
  });

  const payMutation = useMutation({
    mutationFn: () =>
      checkoutService.initiatePayment(sessionId, {
        gateway: selectedGateway as 'cashfree' | 'wallet' | 'stripe' | 'paytm_upi' | 'dev_simulate',
        idempotency_key: `pay-${sessionId}-${Date.now()}`,
      }),
    onSuccess: (result) => {
      const redirectUrl = (result as unknown as { payment_url?: string }).payment_url;
      if (redirectUrl) {
        window.location.href = redirectUrl;
        return;
      }

      if (result.status === 'completed') {
        router.push(`/bookings/${result.booking.booking_uuid}?success=true`);
      }
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error || 'Payment failed. Please try again.';
      setPaymentError(msg);
    },
  });

  const validateGuest = () => {
    const e: Record<string, string> = {};
    if (!guestDetails.name.trim() || guestDetails.name.trim().length < 2)
      e.name = 'Full name is required';
    if (
      !guestDetails.email.trim() ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(guestDetails.email)
    )
      e.email = 'Valid email is required';
    if (
      !guestDetails.phone.trim() ||
      guestDetails.phone.replace(/\D/g, '').length < 10
    )
      e.phone = 'Valid 10-digit phone number is required';

    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleGuestSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateGuest()) return;
    submitGuestMutation.mutate(guestDetails);
  };

  useEffect(() => {
    if (!paymentOptions?.gateways?.length) return;
    if (!paymentOptions.gateways.some((g) => g.id === selectedGateway)) {
      setSelectedGateway(paymentOptions.gateways[0].id);
    }
  }, [paymentOptions, selectedGateway]);

  useEffect(() => {
    if (!walletApplied) {
      setWalletAmount(0);
      return;
    }
    if (!session) return;
    const total = Number(session.price_snapshot.total || 0);
    const walletGateway = paymentOptions?.gateways?.find((g) => g.id === 'wallet');
    const bal = Number(walletGateway?.balance || 0);
    setWalletAmount(Math.min(total, bal));
  }, [walletApplied, paymentOptions, session]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-50">
        <Header />
        <div className="max-w-4xl mx-auto px-4 py-10">
          <Skeleton className="h-64 w-full rounded-2xl mb-6" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Skeleton className="h-96 rounded-2xl" />
            </div>
            <div>
              <Skeleton className="h-80 rounded-2xl" />
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  if (sessionError || !session) {
    return (
      <div className="min-h-screen bg-neutral-50">
        <Header />
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-neutral-900 mb-2">
            Session Expired or Not Found
          </h1>
          <p className="text-neutral-500 mb-6">
            Your booking session has expired. Please start over.
          </p>
          <button
            onClick={() => router.push('/hotels')}
            className="bg-primary-600 text-white font-bold px-6 py-3 rounded-xl hover:bg-primary-700 transition-colors"
          >
            Search Hotels
          </button>
        </div>
        <Footer />
      </div>
    );
  }

  const totalAmount = Number(session.price_snapshot.total || 0);
  const walletGateway = paymentOptions?.gateways?.find((g) => g.id === 'wallet');
  const walletBalance = Number(walletGateway?.balance || 0);
  const payable = Math.max(0, totalAmount - walletAmount);

  return (
    <div className="min-h-screen bg-neutral-50">
      <Header />
      <div className="max-w-4xl mx-auto px-4 py-6 pb-16">
        <div className="flex items-center gap-3 mb-6">
          <div
            className={`flex items-center gap-2 text-sm font-semibold ${
              step === 'guest-details' ? 'text-primary-600' : 'text-green-600'
            }`}
          >
            {step === 'payment' ? (
              <Check size={16} />
            ) : (
              <span className="w-5 h-5 rounded-full bg-primary-600 text-white text-xs flex items-center justify-center">
                1
              </span>
            )}
            Guest Details
          </div>
          <ChevronRight size={14} className="text-neutral-300" />
          <div
            className={`flex items-center gap-2 text-sm font-semibold ${
              step === 'payment' ? 'text-primary-600' : 'text-neutral-400'
            }`}
          >
            <span
              className={`w-5 h-5 rounded-full text-xs flex items-center justify-center ${
                step === 'payment'
                  ? 'bg-primary-600 text-white'
                  : 'bg-neutral-200 text-neutral-500'
              }`}
            >
              2
            </span>
            Payment
          </div>
        </div>

        {session.expires_at && (
          <div className="flex justify-end mb-4">
            <HoldTimer expiresAt={session.expires_at} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-5">
            {step === 'guest-details' && (
              <div className="bg-white rounded-2xl shadow-sm border border-neutral-100 p-6">
                <h2 className="text-lg font-bold text-neutral-900 mb-5">Guest Details</h2>
                <form onSubmit={handleGuestSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-neutral-700 mb-1.5">
                      Full Name *
                    </label>
                    <input
                      type="text"
                      value={guestDetails.name}
                      onChange={(e) =>
                        setGuestDetails((d) => ({ ...d, name: e.target.value }))
                      }
                      className={`w-full px-4 py-3 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-primary-400 ${
                        errors.name
                          ? 'border-red-400 bg-red-50'
                          : 'border-neutral-200'
                      }`}
                      placeholder="Enter your full name"
                    />
                    {errors.name && (
                      <p className="text-xs text-red-500 mt-1">{errors.name}</p>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-neutral-700 mb-1.5">
                        Email Address *
                      </label>
                      <input
                        type="email"
                        value={guestDetails.email}
                        onChange={(e) =>
                          setGuestDetails((d) => ({ ...d, email: e.target.value }))
                        }
                        className={`w-full px-4 py-3 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-primary-400 ${
                          errors.email
                            ? 'border-red-400 bg-red-50'
                            : 'border-neutral-200'
                        }`}
                        placeholder="your@email.com"
                      />
                      {errors.email && (
                        <p className="text-xs text-red-500 mt-1">{errors.email}</p>
                      )}
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-neutral-700 mb-1.5">
                        Phone Number *
                      </label>
                      <div className="flex">
                        <span className="inline-flex items-center px-3 rounded-l-xl border border-r-0 border-neutral-200 bg-neutral-50 text-neutral-500 text-sm">
                          +91
                        </span>
                        <input
                          type="tel"
                          value={guestDetails.phone}
                          onChange={(e) =>
                            setGuestDetails((d) => ({ ...d, phone: e.target.value }))
                          }
                          className={`flex-1 px-4 py-3 rounded-r-xl border text-sm focus:outline-none focus:ring-2 focus:ring-primary-400 ${
                            errors.phone
                              ? 'border-red-400 bg-red-50'
                              : 'border-neutral-200'
                          }`}
                          placeholder="10-digit number"
                          maxLength={10}
                        />
                      </div>
                      {errors.phone && (
                        <p className="text-xs text-red-500 mt-1">{errors.phone}</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-neutral-700 mb-1.5">
                      Special Requests <span className="font-normal text-neutral-400">(optional)</span>
                    </label>
                    <textarea
                      value={guestDetails.special_requests}
                      onChange={(e) =>
                        setGuestDetails((d) => ({
                          ...d,
                          special_requests: e.target.value,
                        }))
                      }
                      className="w-full px-4 py-3 rounded-xl border border-neutral-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400 resize-none"
                      rows={3}
                      placeholder="Early check-in, specific floor, dietary requirements..."
                    />
                  </div>

                  {errors.general && (
                    <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3">
                      <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700">{errors.general}</p>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={submitGuestMutation.isPending}
                    className="w-full py-4 bg-primary-600 hover:bg-primary-700 disabled:bg-neutral-400 text-white font-bold rounded-xl transition-colors text-base"
                  >
                    {submitGuestMutation.isPending
                      ? 'Saving...'
                      : 'Continue to Payment →'}
                  </button>
                </form>
              </div>
            )}

            {step === 'payment' && (
              <div className="space-y-4">
                <WalletApply
                  balance={walletBalance}
                  totalAmount={totalAmount}
                  isApplied={walletApplied}
                  onToggle={setWalletApplied}
                />

                <div className="bg-white rounded-2xl shadow-sm border border-neutral-100 p-6">
                  <h3 className="text-base font-bold text-neutral-900 mb-4">
                    Select Payment Method
                  </h3>

                  <div className="space-y-3">
                    {(paymentOptions?.gateways || [
                      {
                        id: 'cashfree',
                        name: 'UPI / Cards / NetBanking',
                        available: true,
                        description:
                          'Powered by Cashfree — all Indian payment methods',
                      },
                      {
                        id: 'wallet',
                        name: 'ZygoTrip Wallet',
                        available: true,
                        description: 'Instant — use your wallet balance',
                      },
                    ])
                      .filter((gw) => gw.available)
                      .map((gw) => (
                        <label
                          key={gw.id}
                          className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                            selectedGateway === gw.id
                              ? 'border-primary-500 bg-primary-50'
                              : 'border-neutral-200 hover:border-primary-300'
                          }`}
                        >
                          <input
                            type="radio"
                            name="gateway"
                            value={gw.id}
                            checked={selectedGateway === gw.id}
                            onChange={() => setSelectedGateway(gw.id)}
                            className="accent-primary-600"
                          />
                          <div className="flex-1">
                            <p className="font-semibold text-sm text-neutral-800">
                              {gw.name}
                            </p>
                            <p className="text-xs text-neutral-500">
                              {gw.description}
                            </p>
                          </div>
                        </label>
                      ))}
                  </div>

                  {paymentError && (
                    <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 mt-4">
                      <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700">{paymentError}</p>
                    </div>
                  )}

                  <button
                    onClick={() => payMutation.mutate()}
                    disabled={payMutation.isPending}
                    className="w-full mt-5 py-4 bg-primary-600 hover:bg-primary-700 disabled:bg-neutral-400 text-white font-bold rounded-xl transition-colors text-base flex items-center justify-center gap-2"
                  >
                    {payMutation.isPending ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CreditCard size={18} />
                        Pay {formatPrice(payable)}
                      </>
                    )}
                  </button>

                  <p className="text-xs text-neutral-400 text-center mt-3 flex items-center justify-center gap-1">
                    <Shield size={11} className="text-green-500" /> 100% Secure Payment —
                    SSL Encrypted
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-1 space-y-4">
            <BookingSummary context={toBookingContext(session)} />
            <PriceBreakdown
              basePrice={session.price_snapshot.base_price}
              propertyDiscount={session.price_snapshot.property_discount}
              platformDiscount={session.price_snapshot.platform_discount}
              couponDiscount={0}
              serviceFee={session.price_snapshot.service_fee}
              gst={session.price_snapshot.gst}
              finalPrice={session.price_snapshot.total}
              gstPercent={session.price_snapshot.gst && Number(session.price_snapshot.gst) > 0 ? '18' : '0'}
              nights={toBookingContext(session).nights}
              rooms={session.search_snapshot.rooms}
            />
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
