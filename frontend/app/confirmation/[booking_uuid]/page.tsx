'use client';

import { Suspense } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { bookingsService } from '@/services/bookings';
import { CheckCircle, Calendar, MapPin, Users, Printer, ArrowRight } from 'lucide-react';
import { formatPrice as fmt } from '@/lib/formatPrice';

function ConfirmationContent() {
  const { booking_uuid } = useParams<{ booking_uuid: string }>();
  const router = useRouter();

  const { data: booking, isLoading, error } = useQuery({
    queryKey: ['booking', booking_uuid],
    queryFn: () => bookingsService.getBooking(booking_uuid!),
    enabled: !!booking_uuid,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="skeleton w-20 h-20 rounded-full mx-auto mb-4" />
          <div className="skeleton w-48 h-4 rounded mx-auto mb-2" />
          <div className="skeleton w-32 h-4 rounded mx-auto" />
        </div>
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <p className="text-5xl mb-4">😕</p>
          <h2 className="text-xl font-bold text-neutral-700 mb-2">Booking not found</h2>
          <p className="text-sm text-neutral-400 mb-6">
            We could not find this booking. It may have been cancelled or does not exist.
          </p>
          <button onClick={() => router.push('/account')} className="btn-primary">
            My Bookings
          </button>
        </div>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    hold: 'bg-amber-50 text-amber-700 border-amber-200',
    confirmed: 'bg-green-50 text-green-700 border-green-200',
    cancelled: 'bg-red-50 text-red-700 border-red-200',
    payment_pending: 'bg-blue-50 text-blue-700 border-blue-200',
  };
  const statusColor = statusColors[booking.status] ?? 'bg-neutral-50 text-neutral-700 border-neutral-200';

  return (
    <div className="page-booking-bg py-10 px-4">
      <div className="max-w-2xl mx-auto">

        {/* Success header */}
        <div className="text-center mb-8 animate-fade-up">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
            <CheckCircle size={40} stroke="white" />
          </div>
          <h1 className="text-3xl font-black text-neutral-900 font-heading">
            Booking Confirmed!
          </h1>
          <p className="text-neutral-500 mt-2">
            A confirmation has been sent to {booking.guest_email}
          </p>
        </div>

        {/* Booking card */}
        <div className="bg-white rounded-2xl shadow-card overflow-hidden mb-6">

          {/* Status bar */}
          <div className={`px-6 py-3 border-b flex items-center justify-between ${statusColor}`}>
            <span className="text-sm font-semibold capitalize">{booking.status.replace('_', ' ')}</span>
            <span className="text-xs font-mono">{booking.public_booking_id}</span>
          </div>

          <div className="p-6 space-y-5">
            {/* Property */}
            <div className="flex items-start gap-3">
              <MapPin size={18} className="text-primary-500 mt-0.5 shrink-0" />
              <div>
                <p className="font-bold text-neutral-900">{booking.property_name}</p>
                <p className="text-sm text-neutral-500">{booking.property_slug}</p>
              </div>
            </div>

            {/* Dates */}
            <div className="flex items-center gap-3">
              <Calendar size={18} className="text-primary-500 shrink-0" />
              <div className="flex items-center gap-2 text-sm">
                <span className="font-semibold text-neutral-800">{booking.check_in}</span>
                <ArrowRight size={14} className="text-neutral-400" />
                <span className="font-semibold text-neutral-800">{booking.check_out}</span>
                <span className="text-neutral-400">({booking.nights} night{booking.nights !== 1 ? 's' : ''})</span>
              </div>
            </div>

            {/* Guest */}
            <div className="flex items-center gap-3">
              <Users size={18} className="text-primary-500 shrink-0" />
              <div className="text-sm">
                <span className="font-semibold text-neutral-800">{booking.guest_name}</span>
                <span className="text-neutral-400 ml-2">{booking.guest_email}</span>
              </div>
            </div>

            {/* Price summary */}
            <div className="border-t pt-4">
              {booking.price_breakdown && (
                <div className="space-y-1.5 text-sm">
                  <div className="flex justify-between text-neutral-600">
                    <span>Base amount</span>
                    <span>{fmt(booking.price_breakdown.base_amount)}</span>
                  </div>
                  {Number(booking.price_breakdown.meal_amount) > 0 && (
                    <div className="flex justify-between text-neutral-600">
                      <span>Meal plan</span>
                      <span>{fmt(booking.price_breakdown.meal_amount)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-neutral-600">
                    <span>Service fee</span>
                    <span>{fmt(booking.price_breakdown.service_fee)}</span>
                  </div>
                  <div className="flex justify-between text-neutral-600">
                    <span>GST</span>
                    <span>{fmt(booking.price_breakdown.gst)}</span>
                  </div>
                  {Number(booking.price_breakdown.promo_discount) > 0 && (
                    <div className="flex justify-between text-green-600">
                      <span>Promo discount</span>
                      <span>−{fmt(booking.price_breakdown.promo_discount)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-neutral-900 text-base border-t pt-2 mt-2">
                    <span>Total paid</span>
                    <span>{fmt(booking.total_amount)}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={() => router.push('/account')}
            className="btn-primary flex-1"
          >
            My Bookings
          </button>
          <button
            onClick={() => window.print()}
            className="btn-secondary flex items-center gap-2"
          >
            <Printer size={16} />
            Print
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConfirmationPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="skeleton w-48 h-8 rounded" />
      </div>
    }>
      <ConfirmationContent />
    </Suspense>
  );
}
