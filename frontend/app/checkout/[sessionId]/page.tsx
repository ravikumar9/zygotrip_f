'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Shield, Clock, ChevronRight, Check, AlertCircle, CreditCard, Loader2,
  Tag, X, Star, MapPin, Calendar, Users, Moon, Utensils, ChevronDown, Info,
  Sparkles, Ticket
} from 'lucide-react';

import { checkoutService } from '@/services/checkout';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import BookingSummary from '@/components/booking/BookingSummary';
import Skeleton from '@/components/ui/Skeleton';
import api from '@/services/api';
import type { CheckoutSession, CheckoutGuestDetails, CheckoutPaymentOptions } from '@/types/checkout';

type CheckoutStep = 'guest-details' | 'payment';

// ─── Hold Timer ──────────────────────────────────────────────────────────────

function HoldTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState('');
  const [isWarning, setIsWarning] = useState(false);

  useEffect(() => {
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) { setRemaining('Expired'); return; }
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
    <div className={`inline-flex items-center gap-2 text-sm font-bold px-4 py-2 rounded-full border ${
      isWarning ? 'bg-red-50 text-red-700 border-red-200 animate-pulse' : 'bg-amber-50 text-amber-700 border-amber-200'
    }`}>
      <Clock size={14} />
      Price locked · {remaining}
    </div>
  );
}

// ─── Hotel Summary Card (right panel) ────────────────────────────────────────

function HotelSummaryCard({ session }: { session: CheckoutSession }) {
  const nights = Math.max(1, Math.round(
    (new Date(session.search_snapshot.check_out).getTime() - new Date(session.search_snapshot.check_in).getTime()) / 86400000
  ));

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', weekday: 'short' });
  const mealLabel = session.search_snapshot.meal_plan_code === 'BB' ? 'Breakfast Included'
    : session.search_snapshot.meal_plan_code === 'MAP' ? 'Breakfast & Dinner'
    : session.search_snapshot.meal_plan_code === 'AP' ? 'All Meals'
    : 'Room Only';

  return (
    <div className="bg-white rounded-2xl shadow-card overflow-hidden">
      {/* Property header */}
      <div className="px-5 py-4 border-b border-neutral-100"
        style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%)' }}>
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-white/15 rounded-xl flex items-center justify-center shrink-0">
            <MapPin size={18} className="text-white" />
          </div>
          <div>
            <h3 className="font-black text-white text-base leading-tight">{session.property_name}</h3>
            <p className="text-white/70 text-xs mt-0.5 font-medium">{session.room_type_name}</p>
          </div>
        </div>
      </div>

      {/* Stay details */}
      <div className="p-5 space-y-4">
        {/* Check-in / Check-out */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-blue-50 rounded-xl p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <Calendar size={12} className="text-blue-500" />
              <p className="text-xs font-bold text-blue-600 uppercase tracking-wide">Check-in</p>
            </div>
            <p className="font-black text-neutral-900 text-sm leading-tight">{formatDate(session.search_snapshot.check_in)}</p>
            <p className="text-xs text-neutral-400 mt-0.5">After 2:00 PM</p>
          </div>
          <div className="bg-orange-50 rounded-xl p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <Calendar size={12} className="text-orange-500" />
              <p className="text-xs font-bold text-orange-600 uppercase tracking-wide">Check-out</p>
            </div>
            <p className="font-black text-neutral-900 text-sm leading-tight">{formatDate(session.search_snapshot.check_out)}</p>
            <p className="text-xs text-neutral-400 mt-0.5">Before 11:00 AM</p>
          </div>
        </div>

        {/* Stats row */}
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-neutral-50 rounded-xl p-2.5 text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <Moon size={12} className="text-indigo-400" />
              <span className="font-black text-neutral-900 text-sm">{nights}</span>
            </div>
            <p className="text-xs text-neutral-400">{nights === 1 ? 'Night' : 'Nights'}</p>
          </div>
          <div className="flex-1 bg-neutral-50 rounded-xl p-2.5 text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <Users size={12} className="text-primary-400" />
              <span className="font-black text-neutral-900 text-sm">{session.search_snapshot.guests}</span>
            </div>
            <p className="text-xs text-neutral-400">Guests</p>
          </div>
          <div className="flex-1 bg-neutral-50 rounded-xl p-2.5 text-center">
            <div className="flex items-center justify-center gap-1 mb-0.5">
              <CreditCard size={12} className="text-green-500" />
              <span className="font-black text-neutral-900 text-sm">{session.search_snapshot.rooms}</span>
            </div>
            <p className="text-xs text-neutral-400">Room</p>
          </div>
        </div>

        {/* Meal plan badge */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-green-50 border border-green-200 rounded-full px-3 py-1.5 text-xs font-bold text-green-700">
            <Utensils size={11} />
            {mealLabel}
          </div>
          <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-200 rounded-full px-3 py-1.5 text-xs font-bold text-blue-700">
            <Shield size={11} />
            Free Cancellation
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Price Breakdown ─────────────────────────────────────────────────────────

function PriceBreakdownCard({
  session, promoDiscount, walletDeduction
}: {
  session: CheckoutSession;
  promoDiscount: number;
  walletDeduction: number;
}) {
  const { formatPrice: fmt } = useFormatPrice();
  const [showTaxBreakdown, setShowTaxBreakdown] = useState(false);

  const base = Number(session.price_snapshot.base_price || 0);
  const meal = Number(session.price_snapshot.meal_amount || 0);
  const propDisc = Number(session.price_snapshot.property_discount || 0);
  const platDisc = Number(session.price_snapshot.platform_discount || 0);
  const svc = Number(session.price_snapshot.service_fee || 0);
  const gst = Number(session.price_snapshot.gst || 0);
  // Use backend-authoritative total; wallet deducted for display only
  const backendTotal = Number(((session.price_snapshot as unknown) as Record<string, unknown>).final_price as number ?? session.price_snapshot.total ?? 0);
  const total = Math.max(0, backendTotal - walletDeduction);
  const nights = Math.max(1, Math.round(
    (new Date(session.search_snapshot.check_out).getTime() - new Date(session.search_snapshot.check_in).getTime()) / 86400000
  ));

  return (
    <div className="bg-white rounded-2xl shadow-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-neutral-100 flex items-center gap-2">
        <CreditCard size={15} className="text-primary-500" />
        <span className="font-black text-neutral-900 text-sm">Price Breakdown</span>
      </div>
      <div className="p-5 space-y-2.5">
        {/* Base */}
        <div className="flex justify-between text-sm">
          <span className="text-neutral-600">Room charge <span className="text-neutral-400 text-xs">({nights}N × {session.search_snapshot.rooms}R)</span></span>
          <span className="font-semibold text-neutral-800">{fmt(base)}</span>
        </div>
        {meal > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-neutral-600">Meal plan</span>
            <span className="font-semibold text-neutral-800">{fmt(meal)}</span>
          </div>
        )}
        {propDisc > 0 && (
          <div className="flex justify-between text-sm text-green-600">
            <span>Property discount</span>
            <span className="font-semibold">−{fmt(propDisc)}</span>
          </div>
        )}
        {platDisc > 0 && (
          <div className="flex justify-between text-sm text-green-600">
            <span>Platform discount</span>
            <span className="font-semibold">−{fmt(platDisc)}</span>
          </div>
        )}

        {/* Taxes row with expand */}
        <div>
          <button
            onClick={() => setShowTaxBreakdown(v => !v)}
            className="w-full flex justify-between items-center text-sm text-neutral-600 hover:text-neutral-800 transition-colors"
          >
            <span className="flex items-center gap-1">
              Taxes & Fees
              <Info size={12} className="text-neutral-400" />
            </span>
            <span className="flex items-center gap-1 font-semibold text-neutral-800">
              {fmt(svc + gst)}
              <ChevronDown size={12} className={`transition-transform ${showTaxBreakdown ? 'rotate-180' : ''}`} />
            </span>
          </button>
          {showTaxBreakdown && (
            <div className="mt-2 pl-3 border-l-2 border-neutral-100 space-y-1.5 text-xs text-neutral-500">
              {svc > 0 && <div className="flex justify-between"><span>Service fee</span><span>{fmt(svc)}</span></div>}
              {gst > 0 && <div className="flex justify-between"><span>GST</span><span>{fmt(gst)}</span></div>}
            </div>
          )}
        </div>

        {/* Promo discount */}
        {promoDiscount > 0 && (
          <div className="flex justify-between text-sm text-green-600 bg-green-50 rounded-lg px-3 py-2">
            <span className="flex items-center gap-1.5 font-semibold"><Tag size={12} />Coupon savings</span>
            <span className="font-bold">−{fmt(promoDiscount)}</span>
          </div>
        )}
        {walletDeduction > 0 && (
          <div className="flex justify-between text-sm text-purple-600">
            <span>Wallet credit</span>
            <span className="font-semibold">−{fmt(walletDeduction)}</span>
          </div>
        )}

        {/* Total */}
        <div className="border-t-2 border-dashed border-neutral-200 pt-3 mt-1">
          <div className="flex justify-between items-center">
            <div>
              <span className="font-black text-neutral-900 text-base">Total Payable</span>
              <p className="text-xs text-neutral-400">Inclusive of all taxes</p>
            </div>
            <span className="text-2xl font-black text-neutral-900">{fmt(total)}</span>
          </div>
        </div>

        {/* Savings callout */}
        {(propDisc + platDisc + promoDiscount) > 0 && (
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl px-4 py-2.5 flex items-center gap-2">
            <Sparkles size={14} className="text-green-600" />
            <span className="text-sm font-bold text-green-700">
              You save {fmt(propDisc + platDisc + promoDiscount)} on this booking!
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Coupon Section with auto-suggest ────────────────────────────────────────

interface CouponOffer { code: string; title: string; discount_type: string; value: string; max_discount?: string; }

function CouponSection({
  sessionId, promoInput, setPromoInput,
  promoApplied, setPromoApplied,
  promoDiscount, setPromoDiscount,
  promoMsg, setPromoMsg,
  promoLoading, setPromoLoading,
  onPromoApplied,
}: {
  sessionId: string;
  promoInput: string; setPromoInput: (v: string) => void;
  promoApplied: boolean; setPromoApplied: (v: boolean) => void;
  promoDiscount: number; setPromoDiscount: (v: number) => void;
  promoMsg: string; setPromoMsg: (v: string) => void;
  promoLoading: boolean; setPromoLoading: (v: boolean) => void;
  onPromoApplied?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [offers, setOffers] = useState<CouponOffer[]>([]);

  useEffect(() => {
    api.get('/offers/featured/').then(res => {
      const data = res.data;
      const list = Array.isArray(data) ? data : (data?.results || data?.data || []);
      setOffers(list.slice(0, 4).map((o: Record<string, string | undefined>) => ({
        code: o.coupon_code || o.code || '',
        title: o.title || '',
        discount_type: o.offer_type === 'percentage' ? 'percent' : (o.offer_type || o.discount_type || 'percent'),
        value: o.discount_percentage || o.value || '0',
        max_discount: o.max_discount,
      })));
    }).catch(() => {});
  }, []);

  const applyPromo = async (code: string) => {
    const c = code.trim().toUpperCase();
    if (!c) return;
    setPromoInput(c);
    setPromoLoading(true);
    setPromoMsg('');
    try {
      const res = await api.post(`/checkout/${sessionId}/apply-promo/`, { promo_code: c });
      const data = res.data;
      if (data.applied) {
        setPromoApplied(true);
        setPromoDiscount(Number(data.discount_amount || 0));
        setPromoMsg(data.discount_description || `${c} applied! You saved ₹${data.discount_amount}`);
        setExpanded(false);
        onPromoApplied?.();
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      setPromoMsg(e?.response?.data?.error || 'Invalid promo code. Please try another.');
      setPromoApplied(false);
      setPromoDiscount(0);
    } finally {
      setPromoLoading(false);
    }
  };

  const removePromo = async () => {
    setPromoLoading(true);
    try { await api.post(`/checkout/${sessionId}/apply-promo/`, { promo_code: '' }); } catch {}
    setPromoApplied(false); setPromoDiscount(0); setPromoInput(''); setPromoMsg('');
    setPromoLoading(false);
    onPromoApplied?.();
  };

  return (
    <div className="bg-white rounded-2xl shadow-card overflow-hidden">
      <button
        onClick={() => !promoApplied && setExpanded(v => !v)}
        className="w-full px-5 py-4 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-50 rounded-xl flex items-center justify-center">
            <Ticket size={16} className="text-primary-500" />
          </div>
          <div>
            <p className="font-bold text-neutral-800 text-sm">Apply Coupon</p>
            {promoApplied
              ? <p className="text-xs text-green-600 font-semibold mt-0.5">🎉 {promoMsg}</p>
              : <p className="text-xs text-neutral-400 mt-0.5">{offers.length > 0 ? `${offers.length} offers available` : 'Have a code? Save more!'}</p>
            }
          </div>
        </div>
        {promoApplied ? (
          <button onClick={e => { e.stopPropagation(); removePromo(); }}
            className="text-xs text-red-500 font-bold border border-red-200 px-3 py-1 rounded-full hover:bg-red-50 transition-colors">
            Remove
          </button>
        ) : (
          <ChevronDown size={16} className={`text-neutral-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        )}
      </button>

      {expanded && !promoApplied && (
        <div className="border-t border-neutral-100 px-5 pb-4">
          {/* Input */}
          <div className="flex gap-2 mt-3 mb-4">
            <input
              type="text"
              value={promoInput}
              onChange={e => setPromoInput(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && applyPromo(promoInput)}
              placeholder="Type coupon code here"
              className="input-field flex-1 text-sm font-mono uppercase tracking-widest"
            />
            <button
              onClick={() => applyPromo(promoInput)}
              disabled={promoLoading || !promoInput.trim()}
              className="px-5 py-2.5 bg-primary-600 text-white font-bold text-sm rounded-xl hover:bg-primary-700 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {promoLoading ? '...' : 'Apply'}
            </button>
          </div>
          {promoMsg && !promoApplied && (
            <p className="text-red-500 text-xs mb-3 flex items-center gap-1.5">
              <X size={12} />{promoMsg}
            </p>
          )}

          {/* Featured offers */}
          {offers.length > 0 && (
            <>
              <p className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Available Offers</p>
              <div className="space-y-2">
                {offers.map((offer) => (
                  <div key={offer.code} className="border border-dashed border-primary-200 rounded-xl p-3 bg-primary-50/50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-black text-primary-700 text-sm font-mono tracking-wide">{offer.code}</span>
                          <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full font-bold">
                            {offer.discount_type === 'percent' ? `${offer.value}% OFF` : `₹${offer.value} OFF`}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-600">{offer.title}</p>
                        {offer.max_discount && <p className="text-xs text-neutral-400 mt-0.5">Max discount ₹{offer.max_discount}</p>}
                      </div>
                      <button
                        onClick={() => applyPromo(offer.code)}
                        disabled={promoLoading}
                        className="text-xs font-bold text-primary-600 border border-primary-300 px-3 py-1.5 rounded-lg hover:bg-primary-100 transition-colors whitespace-nowrap"
                      >
                        Apply
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function CheckoutSessionPage() {
  const params = useParams();
  const router = useRouter();
  const { formatPrice: fmt } = useFormatPrice();
  const sessionId = typeof params.sessionId === 'string' ? params.sessionId : '';
  const queryClient = useQueryClient();

  const [step, setStep] = useState<CheckoutStep>('guest-details');
  const [guestDetails, setGuestDetails] = useState({ name: '', email: '', phone: '', special_requests: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [selectedGateway, setSelectedGateway] = useState<string>('cashfree');
  const [walletApplied, setWalletApplied] = useState(false);
  const [walletAmount, setWalletAmount] = useState(0);
  const [confirmNewPrice, setConfirmNewPrice] = useState<number | null>(null);

  // Coupon state
  const [promoInput, setPromoInput] = useState('');
  const [promoApplied, setPromoApplied] = useState(false);
  const [promoDiscount, setPromoDiscount] = useState(0);
  const [promoMsg, setPromoMsg] = useState('');
  const [promoLoading, setPromoLoading] = useState(false);

  const { data: session, isLoading, error: sessionError } = useQuery({
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
    mutationFn: (details: CheckoutGuestDetails) => checkoutService.submitGuestDetails(sessionId, details),
    onSuccess: () => { setStep('payment'); setErrors({}); },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Could not save guest details.';
      setErrors({ general: msg });
    },
  });

  const handlePaymentSuccess = (result: unknown) => {
    const res = result as { payment_url?: string; payment_session_id?: string; order_id?: string; status?: string; booking?: { booking_uuid?: string } };
    if (res.payment_session_id) {
      const script = document.createElement('script');
      script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js';
      script.onload = () => {
        // @ts-ignore
        const cashfree = window.Cashfree({ mode: 'sandbox' });
        cashfree.checkout({ paymentSessionId: res.payment_session_id, redirectTarget: '_self' });
      };
      document.head.appendChild(script);
      return;
    }
    if (res.payment_url) { window.location.href = res.payment_url; return; }
    if (res.status === 'completed') {
      router.push(`/confirmation/${res.booking?.booking_uuid}`);
    }
  };

  const payMutation = useMutation({
    mutationFn: () => checkoutService.initiatePayment(sessionId, {
      gateway: selectedGateway as 'cashfree' | 'wallet' | 'stripe' | 'paytm_upi' | 'dev_simulate',
      idempotency_key: `pay-${sessionId}-${Date.now()}`,
    }),
    onSuccess: handlePaymentSuccess,
    onError: async (err: unknown) => {
      const axiosErr = err as { response?: { status?: number; data?: { error?: string; can_retry?: boolean; retry_endpoint?: string; action?: string; new_price?: number } } };
      const status = axiosErr?.response?.status;
      const data = axiosErr?.response?.data;

      if (status === 409) {
        // Case 1: can_retry — call the retry endpoint automatically
        if (data?.can_retry && data?.retry_endpoint) {
          try {
            const retryRes = await api.post(data.retry_endpoint, {
              gateway: selectedGateway,
              idempotency_key: `retry-${sessionId}-${Date.now()}`,
            });
            handlePaymentSuccess(retryRes.data);
          } catch (retryErr: unknown) {
            const re = retryErr as { response?: { data?: { error?: string } } };
            setPaymentError(re?.response?.data?.error || 'Retry payment failed. Please try again.');
          }
          return;
        }

        // Case 2: price changed — ask user to confirm new price
        if (data?.action === 'confirm_new_price' && data?.new_price != null) {
          setConfirmNewPrice(data.new_price);
          setPaymentError(null);
          queryClient.invalidateQueries({ queryKey: ['checkout-session', sessionId] });
          return;
        }

        // Case 3: generic price-changed 409
        if (data?.error === 'Price has changed') {
          queryClient.invalidateQueries({ queryKey: ['checkout-session', sessionId] });
          setPaymentError('The price has been updated. Please review the new amount and try again.');
          return;
        }

        setPaymentError(data?.error || 'A conflict occurred. Please refresh and try again.');
        return;
      }

      setPaymentError(data?.error || 'Payment failed. Please try again.');
    },
  });

  const validateGuest = () => {
    const e: Record<string, string> = {};
    if (!guestDetails.name.trim() || guestDetails.name.trim().length < 2) e.name = 'Full name is required';
    if (!guestDetails.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(guestDetails.email)) e.email = 'Valid email is required';
    if (!guestDetails.phone.trim() || guestDetails.phone.replace(/\D/g, '').length < 10) e.phone = 'Valid 10-digit mobile number is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  useEffect(() => {
    if (!paymentOptions?.gateways?.length) return;
    if (!paymentOptions.gateways.some(g => g.id === selectedGateway)) {
      setSelectedGateway(paymentOptions.gateways[0].id);
    }
  }, [paymentOptions, selectedGateway]);

  useEffect(() => {
    if (!walletApplied || !session) { setWalletAmount(0); return; }
    const backendTotal = Number(((session.price_snapshot as unknown) as Record<string, unknown>).final_price as number ?? session.price_snapshot.total ?? 0);
    const walletGw = paymentOptions?.gateways?.find(g => g.id === 'wallet');
    setWalletAmount(Math.min(backendTotal, Number(walletGw?.balance || 0)));
  }, [walletApplied, paymentOptions, session]);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen page-listing-bg">
        <div className="max-w-5xl mx-auto px-4 py-10">
          <Skeleton className="h-12 w-64 rounded-xl mb-6" />
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-3"><Skeleton className="h-[500px] rounded-2xl" /></div>
            <div className="lg:col-span-2 space-y-4">
              <Skeleton className="h-72 rounded-2xl" />
              <Skeleton className="h-48 rounded-2xl" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (sessionError || !session) {
    return (
      <div className="min-h-screen page-listing-bg flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-neutral-900 mb-2">Session Expired</h1>
          <p className="text-neutral-500 mb-6">Your booking session has expired. Please search again.</p>
          <button onClick={() => router.push('/hotels')} className="btn-primary px-8 py-3">Search Hotels</button>
        </div>
      </div>
    );
  }

  // Use backend-authoritative total for display
  const backendPayable = Number(((session.price_snapshot as unknown) as Record<string, unknown>).final_price as number ?? session.price_snapshot.total ?? 0);
  const walletGateway = paymentOptions?.gateways?.find(g => g.id === 'wallet');
  const walletBalance = Number(walletGateway?.balance || 0);
  // Wallet deducted from display; applied server-side at payment time
  const payable = Math.max(0, backendPayable - walletAmount);

  return (
    <div className="min-h-screen page-listing-bg pb-16">
      <div className="max-w-5xl mx-auto px-4 py-6">

        {/* Top bar: steps + timer */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          {/* Steps */}
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold transition-colors ${
              step === 'guest-details' ? 'bg-primary-600 text-white shadow-md' : 'bg-green-100 text-green-700'
            }`}>
              {step === 'payment' ? <Check size={14} /> : <span className="w-5 h-5 rounded-full border-2 border-current flex items-center justify-center text-xs">1</span>}
              Guest Details
            </div>
            <ChevronRight size={16} className="text-neutral-300" />
            <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold transition-colors ${
              step === 'payment' ? 'bg-primary-600 text-white shadow-md' : 'bg-neutral-100 text-neutral-400'
            }`}>
              <span className="w-5 h-5 rounded-full border-2 border-current flex items-center justify-center text-xs">2</span>
              Payment
            </div>
          </div>
          <HoldTimer expiresAt={session.expires_at} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

          {/* LEFT: Form */}
          <div className="lg:col-span-3">

            {/* ── STEP 1: Guest Details ── */}
            {step === 'guest-details' && (
              <div className="bg-white rounded-2xl shadow-card p-6 md:p-8">
                <div className="mb-6">
                  <h2 className="text-xl font-black text-neutral-900">Guest Details</h2>
                  <p className="text-sm text-neutral-400 mt-0.5">Details must match your government-issued ID</p>
                </div>

                <form onSubmit={e => { e.preventDefault(); if (validateGuest()) submitGuestMutation.mutate(guestDetails as CheckoutGuestDetails); }} className="space-y-5">

                  {/* Full name */}
                  <div>
                    <label className="block text-xs font-bold text-neutral-500 uppercase tracking-wide mb-1.5">
                      Full Name (as per Govt. ID) *
                    </label>
                    <input
                      type="text"
                      value={guestDetails.name}
                      onChange={e => { setGuestDetails(p => ({ ...p, name: e.target.value })); setErrors(p => ({ ...p, name: '' })); }}
                      placeholder="E.g. Rahul Sharma"
                      className={'input-field' + (errors.name ? ' border-red-400 bg-red-50' : '')}
                      autoComplete="name"
                    />
                    {errors.name && <p className="text-red-500 text-xs mt-1 flex items-center gap-1"><AlertCircle size={11} />{errors.name}</p>}
                  </div>

                  {/* Email + Phone row */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-neutral-500 uppercase tracking-wide mb-1.5">
                        Email Address *
                      </label>
                      <input
                        type="email"
                        value={guestDetails.email}
                        onChange={e => { setGuestDetails(p => ({ ...p, email: e.target.value })); setErrors(p => ({ ...p, email: '' })); }}
                        placeholder="booking@example.com"
                        className={'input-field' + (errors.email ? ' border-red-400 bg-red-50' : '')}
                        autoComplete="email"
                      />
                      {errors.email && <p className="text-red-500 text-xs mt-1 flex items-center gap-1"><AlertCircle size={11} />{errors.email}</p>}
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-neutral-500 uppercase tracking-wide mb-1.5">
                        Mobile Number *
                      </label>
                      <div className="relative">
                        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-bold text-neutral-500 border-r border-neutral-200 pr-2.5">+91</span>
                        <input
                          type="tel"
                          value={guestDetails.phone}
                          onChange={e => { setGuestDetails(p => ({ ...p, phone: e.target.value.replace(/\D/g, '').slice(0, 10) })); setErrors(p => ({ ...p, phone: '' })); }}
                          placeholder="98765 43210"
                          className={'input-field pl-14' + (errors.phone ? ' border-red-400 bg-red-50' : '')}
                          autoComplete="tel"
                          maxLength={10}
                        />
                      </div>
                      {errors.phone && <p className="text-red-500 text-xs mt-1 flex items-center gap-1"><AlertCircle size={11} />{errors.phone}</p>}
                    </div>
                  </div>

                  {/* Special requests */}
                  <div>
                    <label className="block text-xs font-bold text-neutral-500 uppercase tracking-wide mb-1.5">
                      Special Requests <span className="font-normal normal-case text-neutral-400">(Optional)</span>
                    </label>
                    <textarea
                      rows={3}
                      value={guestDetails.special_requests}
                      onChange={e => setGuestDetails(p => ({ ...p, special_requests: e.target.value }))}
                      placeholder="Early check-in, high floor, extra pillows, dietary requirements..."
                      className="input-field resize-none"
                    />
                  </div>

                  {errors.general && (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-600 flex items-center gap-2">
                      <AlertCircle size={15} />{errors.general}
                    </div>
                  )}

                  {/* Info strip */}
                  <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 flex items-start gap-2.5 text-xs text-blue-700">
                    <Shield size={14} className="shrink-0 mt-0.5" />
                    <p>Your booking confirmation &amp; e-voucher will be sent to the email above. Please ensure it's correct.</p>
                  </div>

                  <button
                    type="submit"
                    disabled={submitGuestMutation.isPending}
                    className="w-full py-4 bg-gradient-to-r from-primary-600 to-primary-700 text-white font-black text-base rounded-xl shadow-lg hover:from-primary-700 hover:to-primary-800 transition-all duration-200 disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {submitGuestMutation.isPending
                      ? <><Loader2 size={18} className="animate-spin" /> Saving...</>
                      : <>Continue to Payment <ChevronRight size={18} /></>
                    }
                  </button>
                </form>
              </div>
            )}

            {/* ── STEP 2: Payment ── */}
            {step === 'payment' && (
              <div className="space-y-4">

                {/* Guest summary card */}
                <div className="bg-white rounded-2xl shadow-card p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold text-neutral-800 text-sm">Guest Information</h3>
                    <button onClick={() => setStep('guest-details')} className="text-xs text-primary-600 font-bold hover:underline">Edit</button>
                  </div>
                  <div className="space-y-1.5 text-sm">
                    <p className="font-semibold text-neutral-900">{guestDetails.name}</p>
                    <p className="text-neutral-500">{guestDetails.email} · +91 {guestDetails.phone}</p>
                    {guestDetails.special_requests && (
                      <p className="text-neutral-400 text-xs mt-1 italic">"{guestDetails.special_requests}"</p>
                    )}
                  </div>
                </div>

                {/* Payment method */}
                <div className="bg-white rounded-2xl shadow-card p-5">
                  <h3 className="font-bold text-neutral-800 text-sm mb-4">Payment Method</h3>

                  {paymentOptions?.gateways && paymentOptions.gateways.length > 0 ? (
                    <div className="space-y-2">
                      {paymentOptions.gateways.filter(g => g.id !== 'wallet').map(gw => (
                        <label key={gw.id} className={`flex items-center gap-3 p-3.5 rounded-xl border-2 cursor-pointer transition-all ${
                          selectedGateway === gw.id ? 'border-primary-500 bg-primary-50' : 'border-neutral-200 hover:border-neutral-300'
                        }`}>
                          <input type="radio" name="gateway" value={gw.id}
                            checked={selectedGateway === gw.id}
                            onChange={() => setSelectedGateway(gw.id)}
                            className="accent-primary-600" />
                          <div className="flex-1">
                            <p className="font-bold text-neutral-800 text-sm">{gw.name}</p>
                            {gw.id === 'cashfree' && <p className="text-xs text-neutral-400">UPI · Cards · Net Banking · Wallets</p>}
                          </div>
                          {gw.id === 'cashfree' && (
                            <div className="flex items-center gap-1.5">
                              <div className="px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded">UPI</div>
                              <div className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-bold rounded">Card</div>
                            </div>
                          )}
                        </label>
                      ))}

                      {/* Wallet option */}
                      {walletGateway && walletBalance > 0 && (
                        <label className={`flex items-center gap-3 p-3.5 rounded-xl border-2 cursor-pointer transition-all ${
                          walletApplied ? 'border-purple-400 bg-purple-50' : 'border-neutral-200 hover:border-neutral-300'
                        }`}>
                          <input type="checkbox"
                            checked={walletApplied}
                            onChange={e => setWalletApplied(e.target.checked)}
                            className="accent-purple-600" />
                          <div className="flex-1">
                            <p className="font-bold text-neutral-800 text-sm">Wallet Balance</p>
                            <p className="text-xs text-purple-600 font-semibold">Available: {fmt(walletBalance)}</p>
                          </div>
                        </label>
                      )}
                    </div>
                  ) : (
                    <div className="border-2 border-primary-200 bg-primary-50 rounded-xl p-4">
                      <div className="flex items-center gap-3">
                        <CreditCard size={20} className="text-primary-500" />
                        <div>
                          <p className="font-bold text-primary-800">Cashfree Payments</p>
                          <p className="text-xs text-primary-600">UPI · Cards · Net Banking · Wallets</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {confirmNewPrice != null && (
                  <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 text-sm text-amber-800 flex items-start gap-2">
                    <AlertCircle size={16} className="shrink-0 mt-0.5 text-amber-600" />
                    <div>
                      <p className="font-bold">Price Updated</p>
                      <p>The price for this booking has changed to <span className="font-black">{fmt(confirmNewPrice)}</span>. Click Pay to continue with the new price.</p>
                    </div>
                  </div>
                )}
                {paymentError && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-600 flex items-center gap-2">
                    <AlertCircle size={16} />{paymentError}
                  </div>
                )}

                {/* Pay button */}
                <button
                  onClick={() => { setConfirmNewPrice(null); setPaymentError(null); payMutation.mutate(); }}
                  disabled={payMutation.isPending}
                  className="w-full py-4 rounded-xl font-black text-white text-lg shadow-xl flex items-center justify-center gap-3 transition-all duration-200 disabled:opacity-60"
                  style={{ background: 'linear-gradient(135deg, #EB2026 0%, #c71a1f 100%)', boxShadow: '0 8px 24px rgba(235,32,38,0.35)' }}
                >
                  {payMutation.isPending ? (
                    <><Loader2 size={20} className="animate-spin" />Processing...</>
                  ) : (
                    <><Shield size={20} />Pay Securely · {fmt(confirmNewPrice ?? payable)}</>
                  )}
                </button>

                <p className="text-center text-xs text-neutral-400 flex items-center justify-center gap-1.5">
                  <Shield size={11} />
                  256-bit SSL encryption · PCI DSS compliant · Powered by Cashfree
                </p>
              </div>
            )}
          </div>

          {/* RIGHT: Summary panel */}
          <div className="lg:col-span-2 space-y-4">
            <HotelSummaryCard session={session} />

            <CouponSection
              sessionId={sessionId}
              promoInput={promoInput} setPromoInput={setPromoInput}
              promoApplied={promoApplied} setPromoApplied={setPromoApplied}
              promoDiscount={promoDiscount} setPromoDiscount={setPromoDiscount}
              promoMsg={promoMsg} setPromoMsg={setPromoMsg}
              promoLoading={promoLoading} setPromoLoading={setPromoLoading}
              onPromoApplied={() => queryClient.invalidateQueries({ queryKey: ['checkout-session', sessionId] })}
            />

            <PriceBreakdownCard
              session={session}
              promoDiscount={promoDiscount}
              walletDeduction={walletAmount}
            />

            {/* Trust badges */}
            <div className="bg-white rounded-2xl shadow-sm border border-neutral-100 p-4">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { icon: Shield, label: 'Secure Payment', color: 'text-green-500' },
                  { icon: Check, label: 'Instant Confirm', color: 'text-blue-500' },
                  { icon: Star, label: '24/7 Support', color: 'text-amber-500' },
                ].map(({ icon: Icon, label, color }) => (
                  <div key={label} className="flex flex-col items-center gap-1.5">
                    <div className={`w-8 h-8 rounded-full bg-neutral-50 flex items-center justify-center ${color}`}>
                      <Icon size={15} />
                    </div>
                    <p className="text-xs font-semibold text-neutral-600 leading-tight">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
