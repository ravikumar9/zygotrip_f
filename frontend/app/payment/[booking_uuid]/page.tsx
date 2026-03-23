'use client';

import { useState, useEffect, Suspense, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import { paymentService, PaymentGateway, PaymentInitiateResponse } from '@/services/payment';
import {
  CreditCard, Wallet, Shield, ArrowLeft, CheckCircle, AlertCircle,
  Loader2, Smartphone, Lock, Building2, QrCode, Globe,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { useAuth } from '@/contexts/AuthContext';
import { analytics } from '@/lib/analytics';

/* ══════════════════════════════════════════════════════════════════════
   TYPES & CONSTANTS
   ══════════════════════════════════════════════════════════════════════ */

type GatewayKey = 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi' | 'dev_simulate';
type PaymentSubMethod = 'credit_card' | 'debit_card' | 'upi' | 'netbanking';

interface CardDetails { number: string; name: string; expiry: string; cvv: string; }

const POPULAR_BANKS = [
  'State Bank of India', 'HDFC Bank', 'ICICI Bank', 'Axis Bank',
  'Kotak Mahindra Bank', 'Bank of Baroda', 'Punjab National Bank', 'Union Bank',
] as const;

/* ══════════════════════════════════════════════════════════════════════
   PAYMENT CONTENT
   ══════════════════════════════════════════════════════════════════════ */

function PaymentContent() {
  const { formatPrice: fmt } = useFormatPrice();
  const { booking_uuid } = useParams<{ booking_uuid: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [selectedGateway, setSelectedGateway] = useState<GatewayKey | null>(null);
  const [subMethod, setSubMethod] = useState<PaymentSubMethod | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingTxn, setPendingTxn] = useState<PaymentInitiateResponse | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const [card, setCard] = useState<CardDetails>({ number: '', name: '', expiry: '', cvv: '' });
  const [upiId, setUpiId] = useState('');
  const [selectedBank, setSelectedBank] = useState('');

  // ── Data fetching ─────────────────────────────────────────────

  const { data: booking, isLoading: bookingLoading, error: bookingError } = useQuery({
    queryKey: ['booking-payment', booking_uuid],
    queryFn: () => bookingsService.getBooking(booking_uuid!),
    enabled: !!booking_uuid,
  });

  const { data: gatewayData, isLoading: gatewaysLoading } = useQuery({
    queryKey: ['payment-gateways', booking_uuid],
    queryFn: () => paymentService.getAvailableGateways(booking_uuid!),
    enabled: !!booking_uuid && !!booking && (booking.status === 'hold' || booking.status === 'payment_pending'),
  });

  useEffect(() => {
    if (gatewayData?.gateways && !selectedGateway) {
      const available = gatewayData.gateways.filter(g => g.available);
      // Auto-select first card gateway (not wallet) for best UX
      const firstCard = available.find(g => g.name !== 'wallet');
      if (firstCard) {
        setSelectedGateway(firstCard.name as GatewayKey);
      } else if (available.length > 0) {
        setSelectedGateway(available[0].name as GatewayKey);
      }
    }
  }, [gatewayData, selectedGateway]);

  // ── Helpers ───────────────────────────────────────────────────

  const isAggregatorGateway = (gw: GatewayKey | null) =>
    gw === 'cashfree' || gw === 'dev_simulate';

  const formatCardNumber = (val: string) =>
    val.replace(/\D/g, '').replace(/(\d{4})(?=\d)/g, '$1 ').substring(0, 19);

  const formatExpiry = (val: string) => {
    const digits = val.replace(/\D/g, '').substring(0, 4);
    if (digits.length >= 3) return digits.substring(0, 2) + '/' + digits.substring(2);
    return digits;
  };

  const isFormValid = (): boolean => {
    if (!selectedGateway) return false;
    if (selectedGateway === 'wallet' || selectedGateway === 'stripe' || selectedGateway === 'paytm_upi') return true;
    if (isAggregatorGateway(selectedGateway)) {
      if (!subMethod) return false;
      if (subMethod === 'credit_card' || subMethod === 'debit_card') {
        const num = card.number.replace(/\s/g, '');
        return num.length >= 15 && card.name.trim().length >= 2
          && card.expiry.length === 5 && card.cvv.length >= 3;
      }
      if (subMethod === 'upi') return /^[\w.-]+@[\w]+$/.test(upiId.trim());
      if (subMethod === 'netbanking') return selectedBank.length > 0;
    }
    return true;
  };

  // ── Poll payment status ───────────────────────────────────────

  const pollStatus = useCallback(async (txnId: string) => {
    try {
      const result = await paymentService.pollPaymentStatus(txnId, (s) => {
        if (s.status === 'success') {
          toast.success('Payment confirmed!');
          router.push(`/confirmation/${booking_uuid}`);
        }
      }, 60, 3000);
      if (result.status === 'success') router.push(`/confirmation/${booking_uuid}`);
      else if (result.status === 'failed') {
        setPaymentError('Payment failed. Please try again.');
        setPendingTxn(null);
        setLoading(false);
      }
    } catch {
      setPaymentError('Unable to verify payment status. Please check your bookings.');
      setLoading(false);
    }
  }, [booking_uuid, router]);

  // ── Handle payment ────────────────────────────────────────────

  const handlePayment = async () => {
    if (!selectedGateway || !booking_uuid || !isFormValid()) return;
    setLoading(true);
    setPaymentError(null);

    analytics.track('payment_initiated', {
      gateway: selectedGateway,
      sub_method: subMethod || undefined,
      booking_uuid,
    });

    try {
      const result = await paymentService.initiatePayment(booking_uuid, selectedGateway);
      setPendingTxn(result);

      if (result.instant) {
        const methodLabel =
          selectedGateway === 'wallet' ? 'Wallet' :
          subMethod === 'upi' ? 'UPI' :
          subMethod === 'netbanking' ? 'Netbanking' :
          subMethod === 'credit_card' ? 'Credit Card' :
          subMethod === 'debit_card' ? 'Debit Card' :
          'Payment';
        analytics.track('payment_completed', { gateway: selectedGateway, method: methodLabel, booking_uuid });
        toast.success(`${methodLabel} payment successful!`);
        router.push(`/confirmation/${booking_uuid}`);
        return;
      }

      if (result.payment_url) { window.location.href = result.payment_url; return; }
      if (result.payment_session_id) { loadCashfreeDrop(result); return; }
      if (result.txn_token && result.mid) { redirectToPaytm(result); return; }

      pollStatus(result.transaction_id);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
        || 'Payment initiation failed. Please try again.';
      analytics.track('payment_failed', { gateway: selectedGateway, error: msg, booking_uuid });
      setPaymentError(msg);
      setLoading(false);
    }
  };

  // ── Gateway integrations ──────────────────────────────────────

  const loadCashfreeDrop = (result: PaymentInitiateResponse) => {
    const isSandbox = result.environment === 'sandbox';
    const sdkUrl = isSandbox
      ? 'https://sdk.cashfree.com/js/v3/cashfree.js'
      : 'https://sdk.cashfree.com/js/v3/cashfree-prod.js';
    if (!(window as unknown as Record<string, unknown>).Cashfree) {
      const script = document.createElement('script');
      script.src = sdkUrl;
      script.onload = () => openCashfreeCheckout(result);
      document.body.appendChild(script);
    } else {
      openCashfreeCheckout(result);
    }
  };

  const openCashfreeCheckout = (result: PaymentInitiateResponse) => {
    const Cashfree = (window as unknown as Record<string, unknown>).Cashfree as {
      PG: { new(config: { mode: string }): { redirect: (opts: { paymentSessionId: string; returnUrl: string }) => void } };
    };
    const cashfree = new Cashfree.PG({ mode: result.environment === 'sandbox' ? 'sandbox' : 'production' });
    cashfree.redirect({
      paymentSessionId: result.payment_session_id!,
      returnUrl: `${window.location.origin}/confirmation/${booking_uuid}?txn_id=${result.transaction_id}`,
    });
  };

  const redirectToPaytm = (result: PaymentInitiateResponse) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = result.callback_url || '';
    form.style.display = 'none';
    const fields: Record<string, string> = {
      MID: result.mid || '', ORDER_ID: result.transaction_id, TXN_TOKEN: result.txn_token || '',
    };
    Object.entries(fields).forEach(([n, v]) => {
      const inp = document.createElement('input');
      inp.type = 'hidden'; inp.name = n; inp.value = v;
      form.appendChild(inp);
    });
    document.body.appendChild(form);
    form.submit();
  };

  // ── Loading / Error / Processed states ────────────────────────

  if (bookingLoading || gatewaysLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin w-8 h-8 text-primary-500" />
      </div>
    );
  }

  if (bookingError || !booking) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <AlertCircle size={48} className="text-neutral-300 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-neutral-700 mb-2">Booking not found</h2>
          <p className="text-sm text-neutral-500 mb-6">This booking may have expired or the link is invalid.</p>
          <button onClick={() => router.push('/hotels')} className="btn-primary">Browse Hotels</button>
        </div>
      </div>
    );
  }

  if (booking.status !== 'hold' && booking.status !== 'payment_pending') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <CheckCircle size={48} className="text-green-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-neutral-700 mb-2">Already processed</h2>
          <p className="text-sm text-neutral-400 mb-6">
            This booking is in <strong>{booking.status}</strong> status.
          </p>
          <button onClick={() => router.push(`/confirmation/${booking_uuid}`)} className="btn-primary">
            View Confirmation
          </button>
        </div>
      </div>
    );
  }

  const gateways = gatewayData?.gateways?.filter(g => g.available) ?? [];
  const walletGw = gateways.find(g => g.name === 'wallet');
  const cardGateways = gateways.filter(g => g.name !== 'wallet');

  return (
    <div className="page-booking-bg py-10 px-4">
      <div className="max-w-xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className="p-2 rounded-xl hover:bg-white/80/60 transition-all">
            <ArrowLeft size={20} className="text-neutral-600" />
          </button>
          <div>
            <h1 className="text-2xl font-black text-neutral-900 font-heading">Secure Payment</h1>
            <p className="text-sm text-neutral-500">
              {booking.public_booking_id} &middot; {booking.property_name}
            </p>
          </div>
        </div>

        {/* Order Summary */}
        <div className="bg-white/80 rounded-2xl shadow-card p-5 mb-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Amount Due</p>
              <p className="text-3xl font-black text-neutral-900 font-heading mt-1">{fmt(booking.total_amount)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-neutral-400">{booking.nights} night{booking.nights !== 1 ? 's' : ''}</p>
              <p className="text-xs text-neutral-500 font-medium mt-0.5">{booking.property_name}</p>
            </div>
          </div>
        </div>

        {/* Error banner */}
        {paymentError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 flex gap-3 items-start">
            <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">{paymentError}</p>
              <button onClick={() => setPaymentError(null)} className="text-xs text-red-600 underline mt-1">Dismiss</button>
            </div>
          </div>
        )}

        {/* ═══ Wallet section (only for logged-in users with balance) ═══ */}
        {walletGw && (
          <div className="bg-white/80 rounded-2xl shadow-card p-5 mb-5">
            <h2 className="font-bold text-neutral-900 mb-3 flex items-center gap-2 text-sm">
              <Wallet size={16} className="text-indigo-500" /> ZygoTrip Wallet
            </h2>
            <label className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
              selectedGateway === 'wallet' ? 'border-indigo-500 bg-indigo-50' : 'border-neutral-200 hover:border-neutral-300'
            }`}>
              <input type="radio" name="gateway" value="wallet" checked={selectedGateway === 'wallet'}
                onChange={() => { setSelectedGateway('wallet'); setSubMethod(null); analytics.track('payment_method_selected', { method: 'wallet' }); }}
                className="accent-indigo-600 w-4 h-4" />
              <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-indigo-100">
                <Wallet size={18} className="text-indigo-600" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-neutral-800 text-sm">Pay from Wallet</p>
                <p className="text-xs text-neutral-400">
                  Balance: {fmt(parseFloat(walletGw.wallet_balance || '0'))}
                </p>
              </div>
              <span className="text-[10px] font-bold text-green-700 bg-green-100 px-2 py-1 rounded-lg">Instant</span>
            </label>
          </div>
        )}

        {/* ═══ Login prompt for wallet (guest users only) ═══ */}
        {!isAuthenticated && (
          <div className="bg-indigo-50/70 border border-indigo-200 rounded-2xl p-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-indigo-100 shrink-0">
                <Wallet size={16} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-indigo-900">Use ZygoTrip Wallet?</p>
                <p className="text-[11px] text-indigo-600">Sign in to access wallet payments & earn cashback</p>
              </div>
              <button
                onClick={() => router.push(`/account/login?next=/payment/${booking_uuid}`)}
                className="text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 px-3.5 py-2 rounded-xl transition-colors shrink-0"
              >Sign In</button>
            </div>
          </div>
        )}

        {/* ═══ Card / UPI / Netbanking ═══ */}
        {cardGateways.length > 0 && (
          <div className="bg-white/80 rounded-2xl shadow-card overflow-hidden mb-5">
            <div className="p-5 pb-0">
              <h2 className="font-bold text-neutral-900 flex items-center gap-2 text-sm mb-0">
                <CreditCard size={16} className="text-primary-500" /> Payment Method
              </h2>
            </div>

            {cardGateways.map(gw => {
              const gwKey = gw.name as GatewayKey;

              if (!isAggregatorGateway(gwKey)) {
                // Non-aggregator (Stripe / Paytm)
                const isSelected = selectedGateway === gwKey;
                const Icon = gwKey === 'stripe' ? Globe : Smartphone;
                const label = gwKey === 'stripe' ? 'International Cards (Visa, Mastercard)' : 'Paytm UPI';
                return (
                  <div key={gwKey} className="px-5 py-3 border-b border-neutral-50 last:border-0">
                    <label className={`flex items-center gap-4 p-3 rounded-xl cursor-pointer transition-all ${
                      isSelected ? 'bg-primary-50 border border-primary-200' : 'hover:bg-page'
                    }`}>
                      <input type="radio" name="gateway" value={gwKey} checked={isSelected}
                        onChange={() => { setSelectedGateway(gwKey); setSubMethod(null); }}
                        className="accent-primary-600 w-4 h-4" />
                      <Icon size={18} className={isSelected ? 'text-primary-600' : 'text-neutral-400'} />
                      <span className={`text-sm font-medium ${isSelected ? 'text-primary-700' : 'text-neutral-700'}`}>{label}</span>
                    </label>
                  </div>
                );
              }

              // Aggregator: show Credit Card / Debit Card / UPI / Netbanking tabs
              const isGwSelected = selectedGateway === gwKey;
              return (
                <div key={gwKey}>
                  <div className="flex border-b border-neutral-100 mt-2">
                    {([
                      { key: 'credit_card' as const, label: 'Credit Card', icon: CreditCard },
                      { key: 'debit_card' as const, label: 'Debit Card', icon: CreditCard },
                      { key: 'upi' as const, label: 'UPI', icon: QrCode },
                      { key: 'netbanking' as const, label: 'Netbanking', icon: Building2 },
                    ]).map(tab => {
                      const active = isGwSelected && subMethod === tab.key;
                      return (
                        <button key={tab.key}
                          onClick={() => { setSelectedGateway(gwKey); setSubMethod(tab.key); analytics.track('payment_method_selected', { method: tab.key, gateway: gwKey }); }}
                          className={`flex-1 flex items-center justify-center gap-1.5 py-3.5 text-xs font-semibold transition-all border-b-2 ${
                            active
                              ? 'border-primary-500 text-primary-600 bg-primary-50/50'
                              : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:bg-page'
                          }`}>
                          <tab.icon size={14} />
                          <span className="hidden sm:inline">{tab.label}</span>
                          <span className="sm:hidden">{tab.label.split(' ')[0]}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="p-5">
                    {/* Credit / Debit Card */}
                    {isGwSelected && (subMethod === 'credit_card' || subMethod === 'debit_card') && (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-xs font-semibold text-neutral-600 mb-1.5">Card Number</label>
                          <div className="relative">
                            <input type="text" placeholder="1234 5678 9012 3456" value={card.number}
                              onChange={(e) => setCard({ ...card, number: formatCardNumber(e.target.value) })}
                              className="input-field pl-10" maxLength={19} />
                            <CreditCard size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-neutral-600 mb-1.5">Cardholder Name</label>
                          <input type="text" placeholder="Name on card" value={card.name}
                            onChange={(e) => setCard({ ...card, name: e.target.value })}
                            className="input-field" />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">Expiry</label>
                            <input type="text" placeholder="MM/YY" value={card.expiry}
                              onChange={(e) => setCard({ ...card, expiry: formatExpiry(e.target.value) })}
                              className="input-field" maxLength={5} />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">CVV</label>
                            <div className="relative">
                              <input type="password" placeholder="***" value={card.cvv}
                                onChange={(e) => setCard({ ...card, cvv: e.target.value.replace(/\D/g, '').substring(0, 4) })}
                                className="input-field pl-10" maxLength={4} />
                              <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-1.5 pt-1">
                          {['Visa', 'Mastercard', 'RuPay', 'Amex'].map(b => (
                            <span key={b} className="text-[10px] font-bold border rounded px-1.5 py-0.5 text-neutral-400 border-neutral-200">{b}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* UPI */}
                    {isGwSelected && subMethod === 'upi' && (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-xs font-semibold text-neutral-600 mb-1.5">UPI ID</label>
                          <div className="relative">
                            <input type="text" placeholder="yourname@upi" value={upiId}
                              onChange={(e) => setUpiId(e.target.value)}
                              className="input-field pl-10" />
                            <QrCode size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                          </div>
                          <p className="text-[11px] text-neutral-400 mt-1.5">e.g. name@okicici, name@ybl, name@paytm</p>
                        </div>
                        <div className="flex gap-2 flex-wrap">
                          {['@okicici', '@ybl', '@paytm', '@okhdfcbank'].map(suffix => (
                            <button key={suffix}
                              onClick={() => setUpiId((upiId.split('@')[0] || '') + suffix)}
                              className="text-[11px] font-semibold border rounded-lg px-2.5 py-1.5 text-neutral-500 border-neutral-200 hover:border-primary-300 hover:text-primary-600 transition-colors">
                              {suffix}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Netbanking */}
                    {isGwSelected && subMethod === 'netbanking' && (
                      <div className="space-y-3">
                        <label className="block text-xs font-semibold text-neutral-600 mb-1">Select Your Bank</label>
                        <div className="grid grid-cols-2 gap-2">
                          {POPULAR_BANKS.map(bank => (
                            <button key={bank} onClick={() => setSelectedBank(bank)}
                              className={`p-3 rounded-xl text-xs font-medium border-2 transition-all text-left ${
                                selectedBank === bank
                                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                                  : 'border-neutral-200 text-neutral-600 hover:border-neutral-300'
                              }`}>
                              <Building2 size={14} className={`mb-1 ${selectedBank === bank ? 'text-primary-500' : 'text-neutral-400'}`} />
                              {bank}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Prompt */}
                    {isGwSelected && !subMethod && (
                      <div className="text-center py-6">
                        <CreditCard size={32} className="text-neutral-300 mx-auto mb-3" />
                        <p className="text-sm text-neutral-500">Select a payment method above</p>
                      </div>
                    )}

                    {/* Auto-select first submethod when not selected yet */}
                    {!isGwSelected && !subMethod && null}
                  </div>
                </div>
              );
            })}

            <div className="flex items-center gap-2.5 px-5 py-3 border-t border-neutral-100 bg-page/50">
              <Shield size={14} className="text-green-600 shrink-0" />
              <span className="text-[11px] text-neutral-500">
                256-bit SSL encrypted &middot; PCI DSS compliant &middot; Card details are never stored
              </span>
            </div>
          </div>
        )}

        {/* Pay button */}
        <button onClick={handlePayment}
          disabled={loading || !isFormValid()}
          className="btn-primary w-full text-base py-4 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2">
          {loading ? (
            <><Loader2 className="animate-spin w-5 h-5" /> Processing…</>
          ) : (
            <><Lock size={16} /> Pay {fmt(booking.total_amount)}</>
          )}
        </button>

        {/* Pending txn */}
        {pendingTxn && !pendingTxn.instant && (
          <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
            <Loader2 className="animate-spin w-5 h-5 text-amber-600 mx-auto mb-2" />
            <p className="text-sm text-amber-800 font-medium">Waiting for payment confirmation…</p>
            <p className="text-xs text-amber-600 mt-1">Transaction: {pendingTxn.transaction_id}</p>
          </div>
        )}

        {/* Trust badges */}
        <div className="flex items-center justify-center gap-4 mt-6 text-[10px] text-neutral-400">
          <span className="flex items-center gap-1"><Shield size={11} /> Secure Checkout</span>
          <span className="w-1 h-1 rounded-full bg-neutral-300" />
          <span className="flex items-center gap-1"><Lock size={11} /> 100% Safe</span>
          <span className="w-1 h-1 rounded-full bg-neutral-300" />
          <span>PCI Certified</span>
        </div>
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin w-8 h-8 text-primary-500" />
      </div>
    }>
      <PaymentContent />
    </Suspense>
  );
}
