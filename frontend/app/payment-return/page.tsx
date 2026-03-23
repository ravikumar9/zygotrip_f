'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Loader2, CheckCircle, XCircle, AlertCircle, Calendar, MapPin, Users, ArrowRight, Download, Home } from 'lucide-react';
import Link from 'next/link';
import api from '@/services/api';

interface BookingSnapshot {
  booking_uuid: string;
  booking_id: string;
  status: string;
  total_amount: string;
  check_in: string;
  check_out: string;
  property_name: string;
  room_type_name: string;
}

function formatDate(d: string) {
  if (!d) return '';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

function BookingSuccessCard({ booking, bookingUuid }: { booking: BookingSnapshot; bookingUuid: string }) {
  const nights = booking.check_in && booking.check_out
    ? Math.round((new Date(booking.check_out).getTime() - new Date(booking.check_in).getTime()) / 86400000)
    : 1;

  return (
    <div className="min-h-screen page-booking-bg flex items-center justify-center py-10 px-4">
      <div className="w-full max-w-lg">

        {/* Confetti-style success header */}
        <div className="text-center mb-6">
          <div className="relative inline-block">
            <div className="w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-1"
              style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 8px 32px rgba(16,185,129,0.4)' }}>
              <CheckCircle size={48} color="white" strokeWidth={2.5} />
            </div>
            <span className="absolute -top-1 -right-1 text-2xl">🎉</span>
          </div>
          <h1 className="text-3xl font-black text-neutral-900 mt-3 font-heading">Payment Successful!</h1>
          <p className="text-neutral-500 mt-1 text-sm">Your booking is confirmed. Check your email for details.</p>
        </div>

        {/* Booking card */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-5">

          {/* Green confirmed bar */}
          <div className="bg-gradient-to-r from-emerald-500 to-green-500 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <CheckCircle size={16} />
              <span className="font-bold text-sm">Confirmed</span>
            </div>
            <span className="text-white/80 font-mono text-xs font-bold tracking-wider">{booking.booking_id}</span>
          </div>

          <div className="p-6 space-y-4">
            {/* Property */}
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center shrink-0">
                <MapPin size={18} className="text-primary-500" />
              </div>
              <div>
                <p className="font-black text-neutral-900 text-base">{booking.property_name}</p>
                <p className="text-sm text-neutral-500">{booking.room_type_name}</p>
              </div>
            </div>

            {/* Check-in / Check-out */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-xs font-bold text-neutral-400 uppercase tracking-wide mb-1">Check-in</p>
                <p className="font-bold text-neutral-800 text-sm">{formatDate(booking.check_in)}</p>
                <p className="text-xs text-neutral-400 mt-0.5">From 2:00 PM</p>
              </div>
              <div className="bg-neutral-50 rounded-xl p-3">
                <p className="text-xs font-bold text-neutral-400 uppercase tracking-wide mb-1">Check-out</p>
                <p className="font-bold text-neutral-800 text-sm">{formatDate(booking.check_out)}</p>
                <p className="text-xs text-neutral-400 mt-0.5">Until 11:00 AM</p>
              </div>
            </div>

            {/* Duration */}
            <div className="flex items-center gap-4 text-sm bg-blue-50 rounded-xl px-4 py-3">
              <div className="flex items-center gap-1.5 text-blue-700">
                <Calendar size={14} />
                <span className="font-bold">{nights} Night{nights !== 1 ? 's' : ''}</span>
              </div>
              <div className="w-px h-4 bg-blue-200" />
              <div className="text-blue-600 font-medium">Breakfast Included</div>
            </div>

            {/* Total */}
            <div className="border-t pt-4 flex items-center justify-between">
              <span className="text-neutral-500 text-sm font-medium">Total Paid</span>
              <span className="text-2xl font-black text-neutral-900">
                ₹{Number(booking.total_amount).toLocaleString('en-IN')}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="grid grid-cols-2 gap-3">
          <Link
            href={`/confirmation/${bookingUuid}`}
            className="flex items-center justify-center gap-2 bg-primary-600 text-white font-bold py-3.5 rounded-xl hover:bg-primary-700 transition-colors text-sm"
          >
            View Full Details
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/"
            className="flex items-center justify-center gap-2 bg-white text-neutral-700 font-bold py-3.5 rounded-xl border border-neutral-200 hover:bg-neutral-50 transition-colors text-sm"
          >
            <Home size={16} />
            Back to Home
          </Link>
        </div>

        <p className="text-center text-xs text-neutral-400 mt-4">
          Booking reference: <span className="font-mono font-bold">{booking.booking_id}</span>
          {' · '}
          <Link href="/bookings" className="text-primary-500 hover:underline">All Bookings</Link>
        </p>
      </div>
    </div>
  );
}

function PaymentReturnContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'failed' | 'pending' | 'error'>('loading');
  const [message, setMessage] = useState('Verifying your payment...');
  const [booking, setBooking] = useState<BookingSnapshot | null>(null);
  const [bookingUuid, setBookingUuid] = useState<string | null>(null);

  useEffect(() => {
    const sessionId = searchParams.get('session_id');
    const orderId = searchParams.get('order_id');

    if (!sessionId || !orderId) {
      setStatus('error');
      setMessage('Invalid payment return URL. Please check My Bookings.');
      return;
    }

    api.post(`/checkout/${sessionId}/verify-cashfree/`, { order_id: orderId })
      .then((res) => {
        const data = res.data;
        const st = data?.status;

        if (st === 'completed') {
          const uuid = data?.booking?.booking_uuid || data?.booking?.uuid || data?.booking_uuid;
          const bk: BookingSnapshot | null = data?.booking || null;

          if (uuid) {
            setBookingUuid(uuid);
            if (bk) setBooking(bk);
            setStatus('success');
          } else {
            // Completed but no inline booking — redirect to bookings list
            setStatus('success');
            setMessage('Payment confirmed! View your booking below.');
          }
        } else if (st === 'pending') {
          setStatus('pending');
          setMessage('Your payment is being processed. Please allow a few minutes.');
        } else if (st === 'failed') {
          setStatus('failed');
          setMessage(data?.error || 'Payment was not successful.');
        } else {
          setStatus('error');
          setMessage('Unexpected response. Please check My Bookings.');
        }
      })
      .catch((err) => {
        const msg = err?.response?.data?.error || 'Verification failed. Please check My Bookings or contact support.';
        setStatus('error');
        setMessage(msg);
      });
  }, [searchParams, router]);

  // Show rich success card with booking details
  if (status === 'success' && booking && bookingUuid) {
    return <BookingSuccessCard booking={booking} bookingUuid={bookingUuid} />;
  }

  // Success but no booking data inline — show simpler card
  if (status === 'success' && bookingUuid) {
    return (
      <div className="min-h-screen flex items-center justify-center page-booking-bg">
        <div className="bg-white rounded-2xl shadow-xl p-10 text-center max-w-sm mx-4">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: 'linear-gradient(135deg, #10b981, #059669)', boxShadow: '0 8px 24px rgba(16,185,129,0.35)' }}>
            <CheckCircle size={40} color="white" />
          </div>
          <h2 className="text-2xl font-black text-neutral-900 mb-1">Booking Confirmed!</h2>
          <p className="text-neutral-500 text-sm mb-6">Payment successful. Your booking is ready.</p>
          <div className="flex flex-col gap-3">
            <Link href={`/confirmation/${bookingUuid}`}
              className="btn-primary py-3 text-sm font-bold text-center">
              View Booking Details →
            </Link>
            <Link href="/bookings" className="text-sm text-neutral-500 hover:underline">All My Bookings</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center page-booking-bg">
      <div className="bg-white rounded-2xl shadow-xl p-10 text-center max-w-sm mx-4">
        {status === 'loading' && (
          <>
            <Loader2 className="w-16 h-16 animate-spin text-primary-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-neutral-800">Verifying Payment</h2>
            <p className="text-neutral-400 mt-2 text-sm">{message}</p>
            <p className="text-xs text-neutral-300 mt-3">Please do not close this page...</p>
          </>
        )}
        {status === 'pending' && (
          <>
            <AlertCircle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-neutral-900">Processing Payment</h2>
            <p className="text-neutral-500 mt-2 text-sm">{message}</p>
            <Link href="/bookings" className="mt-5 inline-block px-6 py-2.5 bg-primary-600 text-white font-bold rounded-xl text-sm hover:bg-primary-700">
              Check My Bookings
            </Link>
          </>
        )}
        {(status === 'failed' || status === 'error') && (
          <>
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-neutral-900">{status === 'failed' ? 'Payment Failed' : 'Verification Issue'}</h2>
            <p className="text-neutral-500 mt-2 text-sm">{message}</p>
            <div className="flex gap-3 mt-5 justify-center">
              <Link href="/bookings" className="px-4 py-2.5 bg-primary-600 text-white font-bold rounded-xl text-sm hover:bg-primary-700">
                My Bookings
              </Link>
              <Link href="/" className="px-4 py-2.5 bg-neutral-100 text-neutral-700 font-bold rounded-xl text-sm hover:bg-neutral-200">
                Home
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function PaymentReturnPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center page-booking-bg">
        <div className="text-center">
          <div className="w-14 h-14 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 font-medium">Loading...</p>
        </div>
      </div>
    }>
      <PaymentReturnContent />
    </Suspense>
  );
}
