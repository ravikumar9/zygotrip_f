'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, Calendar, MapPin, Users, Clock, Download,
  CheckCircle2, XCircle, AlertTriangle, Loader2, X,
  RefreshCw, Phone, Mail, BedDouble, Receipt,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { clsx } from 'clsx';
import api from '@/services/api';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';
import { HotelDetailSkeleton } from '@/components/ui/Skeleton';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PriceBreakdown {
  base_price?: string;
  tax_amount?: string;
  service_fee?: string;
  discount?: string;
  promo_discount?: string;
  wallet_amount?: string;
  final_amount?: string;
}

interface BookingRoom {
  room_type_name?: string;
  room_number?: string;
  meal_plan?: string;
  rate_plan_name?: string;
  quantity?: number;
  price_per_night?: string;
}

interface BookingDetail {
  uuid: string;
  public_booking_id: string | null;
  property_name: string;
  property_slug: string;
  check_in: string;
  check_out: string;
  nights: number;
  status: string;
  settlement_status?: string;
  is_guest_booking: boolean;
  total_amount: string;
  gross_amount?: string;
  gst_amount?: string;
  refund_amount?: string;
  guest_name?: string;
  guest_email?: string;
  guest_phone?: string;
  rooms: BookingRoom[];
  price_breakdown?: PriceBreakdown;
  hold_expires_at?: string;
  hold_minutes_remaining?: number | null;
  created_at: string;
}

interface RefundPreview {
  amount: number;
  tier: string;
  note: string;
}

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType; description?: string }> = {
  confirmed:          { label: 'Confirmed',        color: 'text-green-700',  bg: 'bg-green-100',  icon: CheckCircle2, description: 'Your booking is confirmed. Have a great stay!' },
  checked_in:         { label: 'Checked In',       color: 'text-blue-700',   bg: 'bg-blue-100',   icon: CheckCircle2, description: 'Guest is currently checked in.' },
  checked_out:        { label: 'Completed',        color: 'text-neutral-600',bg: 'bg-neutral-100',icon: CheckCircle2, description: 'Your stay is complete. Hope you enjoyed it!' },
  settled:            { label: 'Completed',        color: 'text-neutral-600',bg: 'bg-neutral-100',icon: CheckCircle2, description: 'Booking settled.' },
  settlement_pending: { label: 'Completing',       color: 'text-neutral-600',bg: 'bg-neutral-100',icon: Clock },
  cancelled:          { label: 'Cancelled',        color: 'text-red-700',    bg: 'bg-red-100',    icon: XCircle, description: 'This booking has been cancelled.' },
  refund_pending:     { label: 'Refund in Progress',color: 'text-amber-700', bg: 'bg-amber-100',  icon: RefreshCw, description: 'Your refund is being processed. 3-5 business days.' },
  refunded:           { label: 'Refunded',         color: 'text-purple-700', bg: 'bg-purple-100', icon: CheckCircle2, description: 'Your refund has been processed.' },
  payment_pending:    { label: 'Payment Pending',  color: 'text-amber-700',  bg: 'bg-amber-100',  icon: Clock, description: 'Complete payment to confirm your booking.' },
  hold:               { label: 'On Hold',          color: 'text-orange-700', bg: 'bg-orange-100', icon: Clock, description: 'Room held — complete payment within the hold window.' },
  failed:             { label: 'Failed',           color: 'text-red-700',    bg: 'bg-red-100',    icon: XCircle, description: 'Booking could not be processed.' },
};

function getStatusConfig(status: string) {
  return STATUS_CONFIG[status] ?? { label: status, color: 'text-neutral-600', bg: 'bg-neutral-100', icon: Clock };
}

// ─── Cancel Modal ─────────────────────────────────────────────────────────────

function CancelModal({
  booking,
  onClose,
  onSuccess,
}: {
  booking: BookingDetail;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [refund, setRefund] = useState<RefundPreview | null>(null);
  const [loadingRefund, setLoadingRefund] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    api
      .get(`/booking/${booking.uuid}/refund-preview/`)
      .then((res) => setRefund(res.data))
      .catch(() => setRefund({ amount: 0, tier: 'unknown', note: 'Could not calculate. Contact support.' }))
      .finally(() => setLoadingRefund(false));
  }, [booking.uuid]);

  const handleConfirm = async () => {
    setCancelling(true);
    try {
      await api.post(`/booking/${booking.uuid}/cancel/`);
      toast.success('Booking cancelled successfully');
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.error?.message ?? 'Cancellation failed. Please try again.');
    } finally {
      setCancelling(false);
    }
  };

  const totalAmount = parseFloat(booking.total_amount);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-slide-down">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-neutral-100">
          <X size={18} className="text-neutral-500" />
        </button>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <AlertTriangle size={20} className="text-red-600" />
          </div>
          <div>
            <h3 className="font-bold text-neutral-900">Cancel Booking</h3>
            <p className="text-xs text-neutral-500">{booking.property_name}</p>
          </div>
        </div>

        <div className="bg-neutral-50 rounded-xl p-4 mb-5 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Booking ID</span>
            <span className="font-semibold">{booking.public_booking_id ?? booking.uuid.slice(0, 8).toUpperCase()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Check-in</span>
            <span className="font-semibold">{format(parseISO(booking.check_in), 'd MMM yyyy')}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Amount paid</span>
            <span className="font-semibold">₹{totalAmount.toLocaleString('en-IN')}</span>
          </div>
        </div>

        <div className="border rounded-xl p-4 mb-5">
          <p className="text-xs font-semibold text-neutral-500 mb-3 uppercase tracking-wide">Refund Estimate</p>
          {loadingRefund ? (
            <div className="flex items-center gap-2 text-sm text-neutral-400">
              <Loader2 size={14} className="animate-spin" /> Calculating...
            </div>
          ) : refund ? (
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">You'll receive</span>
                <span className={clsx('text-xl font-black', refund.amount > 0 ? 'text-green-600' : 'text-red-600')}>
                  ₹{refund.amount.toLocaleString('en-IN')}
                </span>
              </div>
              {refund.amount < totalAmount && (
                <div className="flex justify-between text-xs text-neutral-400">
                  <span>Cancellation fee</span>
                  <span>₹{(totalAmount - refund.amount).toLocaleString('en-IN')}</span>
                </div>
              )}
              {refund.note && (
                <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 mt-2">⚠️ {refund.note}</p>
              )}
            </div>
          ) : null}
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-neutral-200 hover:bg-neutral-50 transition-colors"
          >
            Keep It
          </button>
          <button
            onClick={handleConfirm}
            disabled={cancelling || loadingRefund}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {cancelling && <Loader2 size={14} className="animate-spin" />}
            {cancelling ? 'Cancelling...' : 'Confirm Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Info Row ─────────────────────────────────────────────────────────────────

function InfoRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-neutral-50 last:border-0">
      <Icon size={16} className="text-neutral-400 shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-xs text-neutral-400">{label}</p>
        <p className="text-sm font-semibold text-neutral-800 mt-0.5">{value}</p>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function BookingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCancel, setShowCancel] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const bookingUuid = params?.uuid as string;

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace(`/account/login?next=/bookings/${bookingUuid}`);
    }
  }, [authLoading, isAuthenticated, router, bookingUuid]);

  useEffect(() => {
    if (!isAuthenticated || !bookingUuid) return;
    setLoading(true);
    api
      .get(`/booking/${bookingUuid}/`)
      .then((res) => setBooking(res.data?.data ?? res.data))
      .catch(() => toast.error('Could not load booking details'))
      .finally(() => setLoading(false));
  }, [isAuthenticated, bookingUuid]);

  const handleDownloadInvoice = async () => {
    if (!booking) return;
    setDownloading(true);
    try {
      const res = await api.get(`/booking/${booking.uuid}/invoice/`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ZygoTrip-Invoice-${booking.public_booking_id ?? booking.uuid.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Invoice not available yet');
    } finally {
      setDownloading(false);
    }
  };

  const handleCancelSuccess = () => {
    if (booking) setBooking({ ...booking, status: 'cancelled' });
  };

  if (authLoading || loading) return <HotelDetailSkeleton />;
  if (!booking) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-neutral-500">Booking not found</p>
        <Link href="/bookings" className="text-sm font-semibold text-primary-600 hover:text-primary-700">
          ← Back to My Trips
        </Link>
      </div>
    );
  }

  const statusCfg = getStatusConfig(booking.status);
  const StatusIcon = statusCfg.icon;
  const isCancellable = ['confirmed', 'checked_in'].includes(booking.status);
  const isRefundableStatus = ['cancelled', 'refunded', 'refund_pending'].includes(booking.status);
  const totalAmount = parseFloat(booking.total_amount);

  return (
    <div className="min-h-screen bg-neutral-50 pt-20 pb-16">
      <div className="max-w-3xl mx-auto px-4">

        {/* Back + header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-xl bg-white border border-neutral-200 hover:bg-neutral-50 transition-colors"
          >
            <ArrowLeft size={18} className="text-neutral-600" />
          </button>
          <div>
            <h1 className="text-xl font-black text-neutral-900 font-heading">Booking Details</h1>
            <p className="text-xs text-neutral-500">
              {booking.public_booking_id ? `#${booking.public_booking_id}` : `#${booking.uuid.slice(0, 8).toUpperCase()}`}
            </p>
          </div>
        </div>

        {/* Status banner */}
        <div className={clsx('rounded-2xl p-4 mb-5 border flex items-start gap-3', statusCfg.bg, `border-${statusCfg.color.replace('text-', '')}/20`)}>
          <StatusIcon size={20} className={clsx(statusCfg.color, 'shrink-0 mt-0.5')} />
          <div>
            <p className={clsx('font-bold text-sm', statusCfg.color)}>{statusCfg.label}</p>
            {statusCfg.description && (
              <p className="text-xs text-neutral-500 mt-0.5">{statusCfg.description}</p>
            )}
            {booking.status === 'hold' && booking.hold_minutes_remaining != null && booking.hold_minutes_remaining > 0 && (
              <p className="text-xs font-semibold text-orange-600 mt-1">
                ⏱ Hold expires in {booking.hold_minutes_remaining} minute{booking.hold_minutes_remaining !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] gap-5">
          {/* Left column */}
          <div className="space-y-5">

            {/* Property + Stay */}
            <div className="bg-white rounded-2xl shadow-card p-5">
              <h2 className="font-bold text-neutral-900 text-lg mb-1">{booking.property_name}</h2>
              <Link
                href={`/hotels/${booking.property_slug}`}
                className="text-xs font-semibold text-primary-600 hover:text-primary-700"
              >
                View Property →
              </Link>

              <div className="grid grid-cols-3 gap-3 bg-neutral-50 rounded-xl p-4 mt-4">
                <div className="text-center">
                  <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Check-in</p>
                  <p className="text-base font-black text-neutral-800">
                    {format(parseISO(booking.check_in), 'd MMM')}
                  </p>
                  <p className="text-xs text-neutral-500">{format(parseISO(booking.check_in), 'EEE, yyyy')}</p>
                </div>
                <div className="text-center border-x border-neutral-200">
                  <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Nights</p>
                  <p className="text-2xl font-black text-primary-600">{booking.nights}</p>
                  <p className="text-xs text-neutral-400">night{booking.nights !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-center">
                  <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Check-out</p>
                  <p className="text-base font-black text-neutral-800">
                    {format(parseISO(booking.check_out), 'd MMM')}
                  </p>
                  <p className="text-xs text-neutral-500">{format(parseISO(booking.check_out), 'EEE, yyyy')}</p>
                </div>
              </div>
            </div>

            {/* Room info */}
            {booking.rooms && booking.rooms.length > 0 && (
              <div className="bg-white rounded-2xl shadow-card p-5">
                <h3 className="font-bold text-neutral-800 text-sm mb-3 flex items-center gap-2">
                  <BedDouble size={16} className="text-neutral-400" /> Room Details
                </h3>
                <div className="space-y-3">
                  {booking.rooms.map((room, i) => (
                    <div key={i} className="bg-neutral-50 rounded-xl p-3">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-sm font-bold text-neutral-800">{room.room_type_name ?? 'Room'}</p>
                          {room.meal_plan && (
                            <p className="text-xs text-neutral-500 mt-0.5">🍽 {room.meal_plan}</p>
                          )}
                          {room.rate_plan_name && (
                            <p className="text-xs text-neutral-400">{room.rate_plan_name}</p>
                          )}
                        </div>
                        {room.price_per_night && (
                          <p className="text-sm font-bold text-neutral-800">
                            ₹{parseFloat(room.price_per_night).toLocaleString('en-IN')}
                            <span className="text-xs font-normal text-neutral-400">/night</span>
                          </p>
                        )}
                      </div>
                      {room.room_number && (
                        <p className="text-xs text-neutral-400 mt-1">Room #{room.room_number}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Guest info */}
            {(booking.guest_name || booking.guest_email || booking.guest_phone) && (
              <div className="bg-white rounded-2xl shadow-card p-5">
                <h3 className="font-bold text-neutral-800 text-sm mb-2 flex items-center gap-2">
                  <Users size={16} className="text-neutral-400" /> Guest Information
                </h3>
                {booking.guest_name && <InfoRow icon={Users} label="Guest name" value={booking.guest_name} />}
                {booking.guest_email && <InfoRow icon={Mail} label="Email" value={booking.guest_email} />}
                {booking.guest_phone && <InfoRow icon={Phone} label="Phone" value={booking.guest_phone} />}
              </div>
            )}
          </div>

          {/* Right column — Price summary */}
          <div className="space-y-4">
            <div className="bg-white rounded-2xl shadow-card p-5">
              <h3 className="font-bold text-neutral-800 text-sm mb-4 flex items-center gap-2">
                <Receipt size={16} className="text-neutral-400" /> Price Summary
              </h3>

              <div className="space-y-2.5">
                {booking.price_breakdown?.base_price && (
                  <div className="flex justify-between text-sm">
                    <span className="text-neutral-500">Room charges</span>
                    <span className="font-semibold">₹{parseFloat(booking.price_breakdown.base_price).toLocaleString('en-IN')}</span>
                  </div>
                )}
                {booking.price_breakdown?.service_fee && parseFloat(booking.price_breakdown.service_fee) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-neutral-500">Service fee</span>
                    <span className="font-semibold">₹{parseFloat(booking.price_breakdown.service_fee).toLocaleString('en-IN')}</span>
                  </div>
                )}
                {booking.gst_amount && parseFloat(booking.gst_amount) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-neutral-500">GST</span>
                    <span className="font-semibold">₹{parseFloat(booking.gst_amount).toLocaleString('en-IN')}</span>
                  </div>
                )}
                {booking.price_breakdown?.discount && parseFloat(booking.price_breakdown.discount) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-green-600">Discount</span>
                    <span className="font-semibold text-green-600">−₹{parseFloat(booking.price_breakdown.discount).toLocaleString('en-IN')}</span>
                  </div>
                )}
                {booking.price_breakdown?.promo_discount && parseFloat(booking.price_breakdown.promo_discount) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-green-600">Promo discount</span>
                    <span className="font-semibold text-green-600">−₹{parseFloat(booking.price_breakdown.promo_discount).toLocaleString('en-IN')}</span>
                  </div>
                )}
                {booking.price_breakdown?.wallet_amount && parseFloat(booking.price_breakdown.wallet_amount) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-blue-600">Wallet used</span>
                    <span className="font-semibold text-blue-600">−₹{parseFloat(booking.price_breakdown.wallet_amount).toLocaleString('en-IN')}</span>
                  </div>
                )}

                <div className="border-t border-neutral-100 pt-2.5 flex justify-between items-center">
                  <span className="font-bold text-neutral-900">Total</span>
                  <span className="text-xl font-black text-neutral-900">
                    ₹{totalAmount.toLocaleString('en-IN')}
                  </span>
                </div>

                {isRefundableStatus && booking.refund_amount && parseFloat(booking.refund_amount) > 0 && (
                  <div className="bg-green-50 rounded-xl px-3 py-2 mt-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-green-700 font-semibold">Refund amount</span>
                      <span className="font-black text-green-700">₹{parseFloat(booking.refund_amount).toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-2.5">
              {/* Download invoice */}
              {['confirmed', 'checked_in', 'checked_out', 'settled', 'settlement_pending'].includes(booking.status) && (
                <button
                  onClick={handleDownloadInvoice}
                  disabled={downloading}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold border border-neutral-200 bg-white hover:bg-neutral-50 transition-colors disabled:opacity-60"
                >
                  {downloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                  {downloading ? 'Downloading...' : 'Download Invoice'}
                </button>
              )}

              {/* Cancel button */}
              {isCancellable && (
                <button
                  onClick={() => setShowCancel(true)}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors"
                >
                  <XCircle size={16} /> Cancel Booking
                </button>
              )}

              <Link
                href="/bookings"
                className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold border border-neutral-200 bg-white hover:bg-neutral-50 transition-colors"
              >
                <ArrowLeft size={16} /> All Bookings
              </Link>
            </div>

            {/* Booking meta */}
            <div className="bg-white rounded-2xl shadow-card p-4 text-xs text-neutral-400 space-y-1.5">
              <p>
                <span className="font-semibold text-neutral-500">Booked on: </span>
                {format(parseISO(booking.created_at), 'd MMM yyyy, h:mm a')}
              </p>
              <p>
                <span className="font-semibold text-neutral-500">Booking ID: </span>
                {booking.public_booking_id ?? booking.uuid.slice(0, 8).toUpperCase()}
              </p>
              <p>
                <span className="font-semibold text-neutral-500">Reference: </span>
                <span className="font-mono text-[10px] break-all">{booking.uuid}</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {showCancel && (
        <CancelModal
          booking={booking}
          onClose={() => setShowCancel(false)}
          onSuccess={handleCancelSuccess}
        />
      )}
    </div>
  );
}
