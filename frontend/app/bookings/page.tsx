'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Calendar, MapPin, Clock, AlertTriangle, CheckCircle2,
  XCircle, ChevronRight, Loader2, X, Download, RefreshCw,
} from 'lucide-react';
import { format, parseISO, isPast } from 'date-fns';
import { clsx } from 'clsx';
import api from '@/services/api';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';
import { BookingSummarySkeleton } from '@/components/ui/Skeleton';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BookingListItem {
  uuid: string;
  public_booking_id: string | null;
  property_name: string;
  property_slug: string;
  check_in: string;
  check_out: string;
  nights: number;
  status: string;
  total_amount: string;
  created_at: string;
}

interface RefundPreview {
  amount: number;
  tier: string;
  note: string;
}

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  confirmed:          { label: 'Confirmed',        color: 'text-green-700',  bg: 'bg-green-100',  icon: CheckCircle2 },
  checked_in:         { label: 'Checked In',       color: 'text-blue-700',   bg: 'bg-blue-100',   icon: CheckCircle2 },
  checked_out:        { label: 'Completed',        color: 'text-neutral-600',bg: 'bg-neutral-100',icon: CheckCircle2 },
  settled:            { label: 'Completed',        color: 'text-neutral-600',bg: 'bg-neutral-100',icon: CheckCircle2 },
  settlement_pending: { label: 'Completed',        color: 'text-neutral-600',bg: 'bg-neutral-100',icon: CheckCircle2 },
  cancelled:          { label: 'Cancelled',        color: 'text-red-700',    bg: 'bg-red-100',    icon: XCircle },
  refund_pending:     { label: 'Refund Pending',   color: 'text-amber-700',  bg: 'bg-amber-100',  icon: RefreshCw },
  refunded:           { label: 'Refunded',         color: 'text-purple-700', bg: 'bg-purple-100', icon: CheckCircle2 },
  payment_pending:    { label: 'Payment Pending',  color: 'text-amber-700',  bg: 'bg-amber-100',  icon: Clock },
  hold:               { label: 'On Hold',          color: 'text-orange-700', bg: 'bg-orange-100', icon: Clock },
  failed:             { label: 'Failed',           color: 'text-red-700',    bg: 'bg-red-100',    icon: XCircle },
};

function getStatusConfig(status: string) {
  return STATUS_CONFIG[status] ?? { label: status, color: 'text-neutral-600', bg: 'bg-neutral-100', icon: Clock };
}

function isCancellable(status: string): boolean {
  return ['confirmed', 'checked_in'].includes(status);
}

function isUpcoming(b: BookingListItem): boolean {
  return ['confirmed', 'payment_pending', 'hold', 'checked_in'].includes(b.status) && !isPast(parseISO(b.check_out));
}

function isCompleted(b: BookingListItem): boolean {
  return ['checked_out', 'settled', 'settlement_pending'].includes(b.status);
}

function isCancelled(b: BookingListItem): boolean {
  return ['cancelled', 'refunded', 'refund_pending', 'failed'].includes(b.status);
}

// ─── Cancel Modal ─────────────────────────────────────────────────────────────

interface CancelModalProps {
  booking: BookingListItem;
  onClose: () => void;
  onSuccess: (uuid: string) => void;
}

function CancelModal({ booking, onClose, onSuccess }: CancelModalProps) {
  const [refund, setRefund] = useState<RefundPreview | null>(null);
  const [loadingRefund, setLoadingRefund] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    api
      .get(`/booking/${booking.uuid}/refund-preview/`)
      .then((res) => setRefund(res.data))
      .catch(() => setRefund({ amount: 0, tier: 'unknown', note: 'Could not calculate refund. Please contact support.' }))
      .finally(() => setLoadingRefund(false));
  }, [booking.uuid]);

  const handleConfirm = async () => {
    setCancelling(true);
    try {
      await api.post(`/booking/${booking.uuid}/cancel/`);
      toast.success('Booking cancelled successfully');
      onSuccess(booking.uuid);
      onClose();
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message ?? 'Could not cancel. Please try again.';
      toast.error(msg);
    } finally {
      setCancelling(false);
    }
  };

  const totalAmount = parseFloat(booking.total_amount);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-slide-down">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-neutral-100">
          <X size={18} className="text-neutral-500" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
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
            <span className="font-semibold text-neutral-800">{booking.public_booking_id ?? booking.uuid.slice(0, 8).toUpperCase()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Check-in</span>
            <span className="font-semibold text-neutral-800">{format(parseISO(booking.check_in), 'd MMM yyyy')}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Total paid</span>
            <span className="font-semibold text-neutral-800">₹{parseFloat(booking.total_amount).toLocaleString('en-IN')}</span>
          </div>
        </div>

        {/* Refund preview */}
        <div className="border border-neutral-200 rounded-xl p-4 mb-5">
          <p className="text-xs font-semibold text-neutral-500 mb-3 uppercase tracking-wide">Refund Estimate</p>
          {loadingRefund ? (
            <div className="flex items-center gap-2 text-sm text-neutral-400">
              <Loader2 size={14} className="animate-spin" /> Calculating refund...
            </div>
          ) : refund ? (
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-neutral-600">Refund amount</span>
                <span className={clsx('text-lg font-black', refund.amount > 0 ? 'text-green-600' : 'text-red-600')}>
                  ₹{refund.amount.toLocaleString('en-IN')}
                </span>
              </div>
              {refund.amount < totalAmount && (
                <div className="flex justify-between items-center text-xs text-neutral-400">
                  <span>Cancellation charge</span>
                  <span>₹{(totalAmount - refund.amount).toLocaleString('en-IN')}</span>
                </div>
              )}
              {refund.note && (
                <p className="text-xs text-neutral-500 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
                  ⚠️ {refund.note}
                </p>
              )}
            </div>
          ) : null}
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors"
          >
            Keep Booking
          </button>
          <button
            onClick={handleConfirm}
            disabled={cancelling || loadingRefund}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {cancelling ? <Loader2 size={14} className="animate-spin" /> : null}
            {cancelling ? 'Cancelling...' : 'Yes, Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Booking Card ─────────────────────────────────────────────────────────────

interface BookingCardProps {
  booking: BookingListItem;
  onCancel: (b: BookingListItem) => void;
}

function BookingCard({ booking, onCancel }: BookingCardProps) {
  const statusCfg = getStatusConfig(booking.status);
  const StatusIcon = statusCfg.icon;

  return (
    <div className="bg-white rounded-2xl shadow-card border border-neutral-100 overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-neutral-900 truncate">{booking.property_name}</h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              {booking.public_booking_id
                ? `#${booking.public_booking_id}`
                : `#${booking.uuid.slice(0, 8).toUpperCase()}`}
              {' · '}Booked {format(parseISO(booking.created_at), 'd MMM yyyy')}
            </p>
          </div>
          <span className={clsx('flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold shrink-0', statusCfg.color, statusCfg.bg)}>
            <StatusIcon size={11} />
            {statusCfg.label}
          </span>
        </div>

        {/* Stay details */}
        <div className="grid grid-cols-3 gap-3 bg-neutral-50 rounded-xl p-3 mb-4">
          <div>
            <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Check-in</p>
            <p className="text-sm font-bold text-neutral-800">{format(parseISO(booking.check_in), 'd MMM')}</p>
            <p className="text-xs text-neutral-400">{format(parseISO(booking.check_in), 'yyyy')}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Check-out</p>
            <p className="text-sm font-bold text-neutral-800">{format(parseISO(booking.check_out), 'd MMM')}</p>
            <p className="text-xs text-neutral-400">{format(parseISO(booking.check_out), 'yyyy')}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-neutral-400 uppercase mb-1">Duration</p>
            <p className="text-sm font-bold text-neutral-800">{booking.nights}</p>
            <p className="text-xs text-neutral-400">night{booking.nights !== 1 ? 's' : ''}</p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-neutral-400">Total amount</p>
            <p className="text-lg font-black text-neutral-900">
              ₹{parseFloat(booking.total_amount).toLocaleString('en-IN')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isCancellable(booking.status) && (
              <button
                onClick={() => onCancel(booking)}
                className="text-xs font-semibold text-red-600 border border-red-200 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
              >
                Cancel
              </button>
            )}
            <Link
              href={`/bookings/${booking.uuid}`}
              className="flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-lg transition-colors text-white"
              style={{ background: 'var(--primary)' }}
            >
              Details <ChevronRight size={13} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = 'all' | 'upcoming' | 'completed' | 'cancelled';

const TABS: { id: Tab; label: string }[] = [
  { id: 'all',       label: 'All' },
  { id: 'upcoming',  label: 'Upcoming' },
  { id: 'completed', label: 'Completed' },
  { id: 'cancelled', label: 'Cancelled' },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MyBookingsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [bookings, setBookings] = useState<BookingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('upcoming');
  const [cancelTarget, setCancelTarget] = useState<BookingListItem | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/account/login?next=/bookings');
    }
  }, [authLoading, isAuthenticated, router]);

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/booking/my/?page_size=100');
      setBookings(data.results ?? data ?? []);
    } catch {
      toast.error('Could not load bookings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) fetchBookings();
  }, [isAuthenticated, fetchBookings]);

  const handleCancelSuccess = (uuid: string) => {
    setBookings((prev) =>
      prev.map((b) => b.uuid === uuid ? { ...b, status: 'cancelled' } : b),
    );
  };

  // Filter by tab
  const filtered = bookings.filter((b) => {
    if (activeTab === 'upcoming')  return isUpcoming(b);
    if (activeTab === 'completed') return isCompleted(b);
    if (activeTab === 'cancelled') return isCancelled(b);
    return true;
  });

  // Tab counts
  const counts: Record<Tab, number> = {
    all:       bookings.length,
    upcoming:  bookings.filter(isUpcoming).length,
    completed: bookings.filter(isCompleted).length,
    cancelled: bookings.filter(isCancelled).length,
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-neutral-300" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50 pt-20 pb-16">
      <div className="max-w-3xl mx-auto px-4">
        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-2xl font-black text-neutral-900 font-heading">My Trips</h1>
          <p className="text-sm text-neutral-500 mt-1">
            {loading ? 'Loading...' : `${bookings.length} booking${bookings.length !== 1 ? 's' : ''} total`}
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white rounded-2xl p-1 shadow-sm border border-neutral-100 mb-6 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex-1 min-w-[80px] flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-sm font-bold whitespace-nowrap transition-all',
                activeTab === tab.id
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50',
              )}
            >
              {tab.label}
              {counts[tab.id] > 0 && (
                <span className={clsx(
                  'text-xs px-1.5 py-0.5 rounded-full font-black',
                  activeTab === tab.id ? 'bg-white/20 text-white' : 'bg-neutral-100 text-neutral-500',
                )}>
                  {counts[tab.id]}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => <BookingSummarySkeleton key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-card p-12 text-center">
            <div className="w-16 h-16 rounded-full bg-neutral-100 flex items-center justify-center mx-auto mb-4">
              <Calendar size={28} className="text-neutral-300" />
            </div>
            <h3 className="font-bold text-neutral-700 mb-2">No bookings found</h3>
            <p className="text-sm text-neutral-400 mb-5">
              {activeTab === 'upcoming' ? "You don't have any upcoming trips." : `No ${activeTab} bookings yet.`}
            </p>
            <Link
              href="/hotels"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold text-white transition-colors"
              style={{ background: 'var(--primary)' }}
            >
              🏨 Find Hotels
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((booking) => (
              <BookingCard
                key={booking.uuid}
                booking={booking}
                onCancel={setCancelTarget}
              />
            ))}
          </div>
        )}
      </div>

      {/* Cancel modal */}
      {cancelTarget && (
        <CancelModal
          booking={cancelTarget}
          onClose={() => setCancelTarget(null)}
          onSuccess={handleCancelSuccess}
        />
      )}
    </div>
  );
}
