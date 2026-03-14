'use client';
import { Calendar, Users, Bed, Clock } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import type { BookingContext } from '@/types';
import { getMealPlanLabel } from '@/lib/mealPlans';

interface BookingSummaryProps {
  context: BookingContext;
}

function fmtDate(dateStr: string) {
  try {
    const d = parseISO(dateStr);
    if (!isValid(d)) return dateStr;
    return format(d, 'EEE, d MMM yyyy');
  } catch {
    return dateStr;
  }
}

export default function BookingSummary({ context }: BookingSummaryProps) {
  // Handle both legacy (check_in/check_out) and current (checkin/checkout) field names
  const checkin = context.checkin
    ?? (context as unknown as { check_in?: string }).check_in
    ?? '';
  const checkout = context.checkout
    ?? (context as unknown as { check_out?: string }).check_out
    ?? '';
  const adults = context.adults
    ?? (context as unknown as { guests?: number }).guests
    ?? 1;

  return (
    <div className="bg-white rounded-2xl shadow-card overflow-hidden">
      {/* Gradient header with property name */}
      <div className="bg-gradient-to-br from-primary-600 via-primary-700 to-primary-800 p-5 text-white">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center shrink-0 text-xl">
            🏨
          </div>
          <div className="min-w-0">
            <h3
              className="font-bold text-base leading-snug font-heading"
            >
              {context.property_name}
            </h3>
            {context.room_type_name && (
              <p className="text-primary-100 text-sm mt-0.5">{context.room_type_name}</p>
            )}
          </div>
        </div>
      </div>

      {/* Stay details */}
      <div className="p-5 space-y-4">
        {/* Check-in / Check-out grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-neutral-50 rounded-xl p-3 border border-neutral-100">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-400 mb-1.5">
              <Calendar size={11} /> Check-in
            </div>
            <p className="font-bold text-sm text-neutral-900">{fmtDate(checkin)}</p>
            <p className="text-xs text-neutral-400 mt-0.5">From 2:00 PM</p>
          </div>
          <div className="bg-neutral-50 rounded-xl p-3 border border-neutral-100">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-400 mb-1.5">
              <Calendar size={11} /> Check-out
            </div>
            <p className="font-bold text-sm text-neutral-900">{fmtDate(checkout)}</p>
            <p className="text-xs text-neutral-400 mt-0.5">Until 11:00 AM</p>
          </div>
        </div>

        {/* Rooms / Guests / Nights pill row */}
        <div className="flex items-center justify-center gap-4 bg-primary-50 rounded-xl py-3 border border-primary-100 text-sm font-semibold text-primary-800">
          <span className="flex items-center gap-1.5">
            <Bed size={14} className="text-primary-500" />
            {context.rooms} Room{context.rooms !== 1 ? 's' : ''}
          </span>
          <span className="text-primary-200">·</span>
          <span className="flex items-center gap-1.5">
            <Users size={14} className="text-primary-500" />
            {adults} Guest{adults !== 1 ? 's' : ''}
          </span>
          <span className="text-primary-200">·</span>
          <span className="flex items-center gap-1.5">
            <Clock size={14} className="text-primary-500" />
            {context.nights} Night{context.nights !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Meal plan (if any) */}
        {context.meal_plan && context.meal_plan !== 'none' && (
          <div className="flex items-center gap-2 text-xs text-green-700 font-medium bg-green-50 rounded-xl px-3 py-2.5 border border-green-100">
            🍽️ {getMealPlanLabel(context.meal_plan)}
          </div>
        )}

        {/* Timer is rendered separately below PriceBreakdown */}
      </div>
    </div>
  );
}
