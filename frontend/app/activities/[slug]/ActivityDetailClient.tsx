'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft, Star, Clock, MapPin, Users, Calendar, Check, Shield,
  ChevronDown, ChevronUp, Loader2, Minus, Plus, Share2, Heart,
} from 'lucide-react';
import { useActivityDetail, useActivityTimeSlots } from '@/hooks/useActivities';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { format, addDays } from 'date-fns';
import type { ActivityTimeSlot } from '@/types/activities';

function TimeSlotCard({ slot, selected, onSelect }: { slot: ActivityTimeSlot; selected: boolean; onSelect: () => void }) {
  const { formatPrice } = useFormatPrice();
  return (
    <button
      onClick={onSelect}
      disabled={slot.remaining_seats <= 0}
      className={`text-left border rounded-xl p-3 transition-all ${
        slot.remaining_seats <= 0
          ? 'opacity-50 cursor-not-allowed border-neutral-200 bg-neutral-50'
          : selected
          ? 'border-primary-500 bg-primary-50 ring-1 ring-primary-200'
          : 'border-neutral-200 hover:border-primary-300 bg-white'
      }`}
    >
      <p className="text-sm font-bold text-neutral-800">{slot.start_time}</p>
      {slot.end_time && <p className="text-[10px] text-neutral-400">Ends {slot.end_time}</p>}
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-neutral-500">{slot.remaining_seats} left</span>
        <span className="text-sm font-bold text-neutral-900">{formatPrice(slot.price_adult)}</span>
      </div>
    </button>
  );
}

export default function ActivityDetailClient({ slug }: { slug: string }) {
  const router = useRouter();
  const { formatPrice } = useFormatPrice();
  const { data: activity, isLoading } = useActivityDetail(slug);

  const [selectedDate, setSelectedDate] = useState(format(addDays(new Date(), 1), 'yyyy-MM-dd'));
  const [selectedSlot, setSelectedSlot] = useState<ActivityTimeSlot | null>(null);
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(0);
  const [expandedSection, setExpandedSection] = useState<string | null>('overview');

  const { data: slotsData, isLoading: slotsLoading } = useActivityTimeSlots(activity?.id || null, selectedDate);
  const slots = slotsData || [];

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={28} className="animate-spin text-neutral-400" />
      </div>
    );
  }

  if (!activity) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-lg font-bold text-neutral-700 mb-1">Activity not found</h2>
          <button onClick={() => router.push('/activities')} className="text-sm text-primary-600 mt-2">Back to activities</button>
        </div>
      </div>
    );
  }

  const totalPrice = selectedSlot
    ? selectedSlot.price_adult * adults + (selectedSlot.price_child || 0) * children
    : activity.price_adult * adults + (activity.price_child || 0) * children;

  const toggleSection = (s: string) => setExpandedSection(expandedSection === s ? null : s);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-white border-b border-neutral-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-neutral-600">
            <ArrowLeft size={16} /> Back
          </button>
          <div className="flex items-center gap-2">
            <button className="p-2 rounded-full hover:bg-neutral-100"><Share2 size={16} /></button>
            <button className="p-2 rounded-full hover:bg-neutral-100"><Heart size={16} /></button>
          </div>
        </div>
      </div>

      {/* Hero */}
      <div className="relative h-64 md:h-80 bg-neutral-200 overflow-hidden">
        {activity.primary_image ? (
          <img src={activity.primary_image} alt={activity.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl">🎯</div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6">
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/20 text-white mb-2 inline-block">
            {activity.category}
          </span>
          <h1 className="text-white text-xl md:text-2xl font-black">{activity.name}</h1>
          <div className="flex items-center gap-3 mt-2 text-white/80 text-xs">
            <span className="flex items-center gap-1"><MapPin size={10} /> {activity.city}</span>
            {activity.duration_display && <span className="flex items-center gap-1"><Clock size={10} /> {activity.duration_display}</span>}
            {activity.rating > 0 && (
              <span className="flex items-center gap-1"><Star size={10} fill="white" /> {activity.rating.toFixed(1)} ({activity.review_count})</span>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        {/* Left column */}
        <div className="space-y-4">
          {/* Trust badges */}
          <div className="flex flex-wrap gap-3">
            {activity.is_instant_confirm && (
              <span className="flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-full">
                <Check size={10} /> Instant Confirmation
              </span>
            )}
            {activity.is_free_cancellation && (
              <span className="flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full">
                <Shield size={10} /> Free Cancellation
              </span>
            )}
          </div>

          {/* Overview accordion */}
          <div className="bg-white rounded-xl border border-neutral-100">
            <button onClick={() => toggleSection('overview')} className="w-full flex items-center justify-between p-4">
              <h2 className="text-sm font-bold text-neutral-900">Overview</h2>
              {expandedSection === 'overview' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {expandedSection === 'overview' && (
              <div className="px-4 pb-4 space-y-3">
                <p className="text-sm text-neutral-600 leading-relaxed">{activity.description}</p>
                {activity.highlights && activity.highlights.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold text-neutral-700 mb-2">Highlights</h3>
                    <ul className="space-y-1">
                      {activity.highlights.map((h, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-neutral-600">
                          <Check size={10} className="text-green-500 shrink-0 mt-0.5" /> {h}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* What's Included */}
          {activity.inclusions && activity.inclusions.length > 0 && (
            <div className="bg-white rounded-xl border border-neutral-100">
              <button onClick={() => toggleSection('included')} className="w-full flex items-center justify-between p-4">
                <h2 className="text-sm font-bold text-neutral-900">What&apos;s Included</h2>
                {expandedSection === 'included' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
              {expandedSection === 'included' && (
                <div className="px-4 pb-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {activity.inclusions.map((item: string, i: number) => (
                    <span key={i} className="flex items-center gap-2 text-xs text-neutral-600">
                      <Check size={10} className="text-green-500" /> {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Time slots */}
          <div className="bg-white rounded-xl border border-neutral-100 p-4">
            <h2 className="text-sm font-bold text-neutral-900 mb-3">Select Time</h2>
            <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
              {Array.from({ length: 7 }).map((_, i) => {
                const d = addDays(new Date(), i + 1);
                const val = format(d, 'yyyy-MM-dd');
                return (
                  <button
                    key={val}
                    onClick={() => { setSelectedDate(val); setSelectedSlot(null); }}
                    className={`text-center px-3 py-2 rounded-lg border text-xs font-semibold shrink-0 transition-all ${
                      selectedDate === val
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="text-[10px]">{format(d, 'EEE')}</div>
                    <div>{format(d, 'd MMM')}</div>
                  </button>
                );
              })}
            </div>
            {slotsLoading ? (
              <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-neutral-300" /></div>
            ) : slots.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {slots.map((slot) => (
                  <TimeSlotCard key={slot.id} slot={slot} selected={selectedSlot?.id === slot.id} onSelect={() => setSelectedSlot(slot)} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-neutral-400 text-center py-4">No time slots available for this date.</p>
            )}
          </div>
        </div>

        {/* Booking sidebar */}
        <div className="lg:sticky lg:top-20 h-fit space-y-4">
          <div className="bg-white rounded-xl border border-neutral-100 p-4">
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-2xl font-black text-neutral-900">{formatPrice(activity.price_adult)}</span>
              <span className="text-xs text-neutral-400">per person</span>
            </div>

            {/* Participants */}
            <div className="space-y-3 mb-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-700">Adults</span>
                <div className="flex items-center gap-3">
                  <button onClick={() => setAdults(Math.max(1, adults - 1))} className="w-7 h-7 rounded-full border border-neutral-200 flex items-center justify-center hover:border-primary-300">
                    <Minus size={12} />
                  </button>
                  <span className="text-sm font-bold w-4 text-center">{adults}</span>
                  <button onClick={() => setAdults(Math.min(20, adults + 1))} className="w-7 h-7 rounded-full border border-neutral-200 flex items-center justify-center hover:border-primary-300">
                    <Plus size={12} />
                  </button>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-700">Children</span>
                <div className="flex items-center gap-3">
                  <button onClick={() => setChildren(Math.max(0, children - 1))} className="w-7 h-7 rounded-full border border-neutral-200 flex items-center justify-center hover:border-primary-300">
                    <Minus size={12} />
                  </button>
                  <span className="text-sm font-bold w-4 text-center">{children}</span>
                  <button onClick={() => setChildren(Math.min(10, children + 1))} className="w-7 h-7 rounded-full border border-neutral-200 flex items-center justify-center hover:border-primary-300">
                    <Plus size={12} />
                  </button>
                </div>
              </div>
            </div>

            <div className="border-t border-neutral-100 pt-3 mb-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-neutral-500">
                  {adults} adult{adults > 1 ? 's' : ''} × {formatPrice(selectedSlot?.price_adult || activity.price_adult)}
                </span>
                <span className="text-xs font-semibold">{formatPrice((selectedSlot?.price_adult || activity.price_adult) * adults)}</span>
              </div>
              {children > 0 && (
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-neutral-500">
                    {children} child{children > 1 ? 'ren' : ''} × {formatPrice(selectedSlot?.price_child || activity.price_child || 0)}
                  </span>
                  <span className="text-xs font-semibold">{formatPrice((selectedSlot?.price_child || activity.price_child || 0) * children)}</span>
                </div>
              )}
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-neutral-50">
                <span className="text-sm font-bold text-neutral-900">Total</span>
                <span className="text-lg font-black text-neutral-900">{formatPrice(totalPrice)}</span>
              </div>
            </div>

            <button className="btn-primary w-full py-3 text-sm font-bold">Book Now</button>
          </div>

          {/* Trust */}
          <div className="bg-green-50 rounded-xl border border-green-100 p-3 text-center">
            <Shield size={16} className="text-green-600 mx-auto mb-1" />
            <p className="text-[10px] text-green-700 font-semibold">Lowest price guarantee</p>
            <p className="text-[10px] text-green-600">Found it cheaper? We&apos;ll match it.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
