'use client';

import { useState, useEffect, Suspense, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import { paymentService, PaymentGateway, PaymentInitiateResponse } from '@/services/payment';
import { CreditCard, Wallet, Shield, ArrowLeft, CheckCircle, AlertCircle, Loader2, Smartphone } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatPrice as fmt } from '@/lib/formatPrice';

type GatewayKey = 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi';

const GATEWAY_UI: Record<string, { icon: typeof CreditCard; label: string; desc: string }> = {
  wallet: { icon: Wallet, label: 'ZygoTrip Wallet', desc: 'Pay instantly from your wallet balance' },
  cashfree: { icon: CreditCard, label: 'Cards, UPI & Netbanking', desc: 'Visa, Mastercard, RuPay, UPI, Netbanking via Cashfree' },
  stripe: { icon: CreditCard, label: 'International Cards', desc: 'Visa, Mastercard — powered by Stripe' },
  paytm_upi: { icon: Smartphone, label: 'Paytm UPI', desc: 'Pay using Paytm UPI' },
};

function PaymentContent() {
  const { booking_uuid } = useParams<{ booking_uuid: string }>();
  const router = useRouter();

  const [selectedGateway, setSelectedGateway] = useState<GatewayKey | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingTxn, setPendingTxn] = useState<PaymentInitiateResponse | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  // Fetch booking details
  const { data: booking, isLoading: bookingLoading, error: bookingError } = useQuery({
    queryKey: ['booking-payment', booking_uuid],
    queryFn: () => bookingsService.getBooking(booking_uuid!),
    enabled: !!booking_uuid,
  });

  // Fetch available gateways
  const { data: gatewayData, isLoading: gatewaysLoading } = useQuery({
    queryKey: ['payment-gateways', booking_uuid],
    queryFn: () => paymentService.getAvailableGateways(booking_uuid!),
    enabled: !!booking_uuid && !!booking && (booking.status === 'hold' || booking.status === 'payment_pending'),
  });

  // Auto-select first available gateway
  useEffect(() => {
    if (gatewayData?.gateways && !selectedGateway) {
      const available = gatewayData.gateways.filter(g => g.available);
      if (available.length > 0) {
        setSelectedGateway(available[0].name as GatewayKey);
      }
    }
  }, [gatewayData, selectedGateway]);

  // Poll payment status for pending transactions (non-instant gateways)
  const pollStatus = useCallback(async (txnId: string) => {
    try {
      const result = await paymentService.pollPaymentStatus(
        txnId,
        (status) => {
          if (status.status === 'success') {
            toast.success('Payment confirmed!');
            router.push(`/confirmation/${booking_uuid}`);
          }
        },
        60,   // max 60 attempts
        3000, // every 3s
      );
      if (result.status === 'success') {
        router.push(`/confirmation/${booking_uuid}`);
      } else if (result.status === 'failed') {
        setPaymentError('Payment failed. Please try again.');
        setPendingTxn(null);
        setLoading(false);
      }
    } catch {
      setPaymentError('Unable to verify payment status. Please check your bookings.');
      setLoading(false);
    }
  }, [booking_uuid, router]);

  const handlePayment = async () => {
    if (!selectedGateway || !booking_uuid) return;
    setLoading(true);
    setPaymentError(null);

    try {
      const result = await paymentService.initiatePayment(booking_uuid, selectedGateway);
      setPendingTxn(result);

      // Wallet: instant confirmation
      if (result.instant) {
        toast.success('Wallet payment successful!');
        router.push(`/confirmation/${booking_uuid}`);
        return;
      }

      // Stripe: redirect to Stripe checkout
      if (result.payment_url) {
        window.location.href = result.payment_url;
        return;
      }

      // Cashfree: load Cashfree JS SDK and render drop
      if (result.payment_session_id) {
        loadCashfreeDrop(result);
        return;
      }

      // Paytm: redirect to Paytm page
      if (result.txn_token && result.mid) {
        redirectToPaytm(result);
        return;
      }

      // Fallback: poll for status
      pollStatus(result.transaction_id);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
        || 'Payment initiation failed. Please try again.';
      setPaymentError(msg);
      setLoading(false);
    }
  };

  // Cashfree Drop integration
  const loadCashfreeDrop = (result: PaymentInitiateResponse) => {
    const isSandbox = result.environment === 'sandbox';
    const sdkUrl = isSandbox
      ? 'https://sdk.cashfree.com/js/v3/cashfree.js'
      : 'https://sdk.cashfree.com/js/v3/cashfree.js';

    // Load SDK if not already
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

  // Paytm redirect
  const redirectToPaytm = (result: PaymentInitiateResponse) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = result.callback_url || '';
    form.style.display = 'none';

    const fields: Record<string, string> = {
      MID: result.mid || '',
      ORDER_ID: result.transaction_id,
      TXN_TOKEN: result.txn_token || '',
    };
    Object.entries(fields).forEach(([name, value]) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      input.value = value;
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
  };

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
          <p className="text-5xl mb-4">😕</p>
          <h2 className="text-xl font-bold text-neutral-700 mb-4">Booking not found</h2>
          <button onClick={() => router.push('/hotels')} className="btn-primary">Browse Hotels</button>
        </div>
      </div>
    );
  }

  // Already processed
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

  return (
    <div className="page-booking-bg py-10 px-4">
      <div className="max-w-lg mx-auto">

        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => router.back()} className="p-2 rounded-xl hover:bg-white hover:shadow-sm transition-all">
            <ArrowLeft size={20} className="text-neutral-600" />
          </button>
          <div>
            <h1 className="text-2xl font-black text-neutral-900 font-heading">
              Complete Payment
            </h1>
            <p className="text-sm text-neutral-500">
              {booking.public_booking_id} · {booking.property_name}
            </p>
          </div>
        </div>

        {/* Amount due */}
        <div className="bg-white rounded-2xl shadow-card p-6 mb-5">
          <p className="text-sm text-neutral-500 mb-1">Amount Due</p>
          <p className="text-3xl font-black text-neutral-900 font-heading">
            {fmt(booking.total_amount)}
          </p>
          <p className="text-xs text-neutral-400 mt-1">
            {booking.nights} night{booking.nights !== 1 ? 's' : ''} at {booking.property_name}
          </p>
        </div>

        {/* Error banner */}
        {paymentError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 flex gap-3 items-start">
            <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800">{paymentError}</p>
              <button
                onClick={() => setPaymentError(null)}
                className="text-xs text-red-600 underline mt-1"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Payment method selection */}
        <div className="bg-white rounded-2xl shadow-card p-6 mb-5">
          <h2 className="font-bold text-neutral-900 mb-4 flex items-center gap-2 font-heading">
            <CreditCard size={18} className="text-secondary-500" />
            Payment Method
          </h2>

          {gateways.length === 0 ? (
            <p className="text-sm text-neutral-400">No payment gateways available. Please contact support.</p>
          ) : (
            <div className="space-y-3">
              {gateways.map((gw: PaymentGateway) => {
                const ui = GATEWAY_UI[gw.name] || { icon: CreditCard, label: gw.display_name, desc: '' };
                const Icon = ui.icon;
                const isSelected = selectedGateway === gw.name;
                const walletInfo = gw.name === 'wallet' && gw.wallet_balance
                  ? ` (Balance: ${fmt(parseFloat(gw.wallet_balance))})`
                  : '';
                const insufficientWallet = gw.name === 'wallet' && gw.sufficient_balance === false;

                return (
                  <label
                    key={gw.name}
                    className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                      isSelected
                        ? 'border-primary-500 bg-primary-50'
                        : insufficientWallet
                          ? 'border-neutral-200 bg-neutral-50 opacity-60 cursor-not-allowed'
                          : 'border-neutral-200 bg-white hover:border-neutral-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment"
                      value={gw.name}
                      checked={isSelected}
                      onChange={() => !insufficientWallet && setSelectedGateway(gw.name as GatewayKey)}
                      disabled={insufficientWallet}
                      className="accent-primary-600 w-4 h-4"
                    />
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      isSelected ? 'bg-primary-100' : 'bg-neutral-100'
                    }`}>
                      <Icon size={18} className={isSelected ? 'text-primary-600' : 'text-neutral-500'} />
                    </div>
                    <div>
                      <p className="font-semibold text-neutral-800 text-sm">
                        {ui.label}{walletInfo}
                      </p>
                      <p className="text-xs text-neutral-400">
                        {insufficientWallet ? 'Insufficient balance' : ui.desc}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          <div className="flex items-center gap-2.5 mt-5 pt-4 border-t border-neutral-100">
            <Shield size={15} className="text-green-500 shrink-0" />
            <span className="text-xs text-neutral-400">
              256-bit SSL encrypted. Your payment information is never stored.
            </span>
          </div>
        </div>

        <button
          onClick={handlePayment}
          disabled={loading || !selectedGateway}
          className="btn-primary w-full text-base py-3.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="animate-spin w-5 h-5" />
              Processing…
            </span>
          ) : (
            `Pay ${fmt(booking.total_amount)}`
          )}
        </button>

        {/* Pending transaction info */}
        {pendingTxn && !pendingTxn.instant && (
          <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
            <Loader2 className="animate-spin w-5 h-5 text-amber-600 mx-auto mb-2" />
            <p className="text-sm text-amber-800 font-medium">Waiting for payment confirmation…</p>
            <p className="text-xs text-amber-600 mt-1">Transaction: {pendingTxn.transaction_id}</p>
          </div>
        )}
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
