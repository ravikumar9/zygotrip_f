'use client';
import Image from 'next/image';
import { Users, Check, BedDouble, Layers, X, ChevronRight } from 'lucide-react';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { MEAL_PLAN_META } from '@/lib/mealPlans';
import type { RoomType, RoomMealPlan } from '@/types';

interface RoomCardProps {
  room: RoomType;
  isSelected?: boolean;
  selectedMealPlanCode?: string;
  onSelect: (room: RoomType, mealPlan?: RoomMealPlan) => void;
}

/* Meal plan display meta comes from canonical lib/mealPlans.ts */

/**
 * RoomCard — individual room type card for hotel detail page.
 * Displays room image, bed type, occupancy, amenities, refund policy,
 * price per night, and a book button.
 *
 * Uses stopPropagation on image clicks to prevent navigation
 * to hotel detail page (Phase 5 fix).
 */
export default function RoomCard({ room, isSelected, selectedMealPlanCode, onSelect }: RoomCardProps) {
  const { formatPrice } = useFormatPrice();
  const primaryImage = room.images?.find(i => i.is_primary) ?? room.images?.[0];
  const availCount = room.inventory_remaining ?? room.available_count ?? 0;
  const basePrice = parseFloat(String(room.base_price));
  const isFree = room.cancellation_policy === 'free';
  const mealPlans = (room.meal_plans ?? []).filter(mp => mp.is_available !== false);

  return (
    <div className={[
      'rounded-2xl border-2 overflow-hidden bg-white/80 transition-all duration-200',
      isSelected
        ? 'border-primary-500 shadow-booking ring-1 ring-primary-200'
        : 'border-neutral-200 hover:border-primary-300 hover:shadow-md',
    ].join(' ')}>
      <div className="flex flex-col lg:flex-row">
        {/* LEFT: Room image + info */}
        <div className="lg:w-56 shrink-0 flex flex-col">
          {/* Image — clicks are isolated (stopPropagation) */}
          <div
            className="relative h-44 lg:h-52 bg-neutral-100 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {primaryImage?.url ? (
              <Image
                src={primaryImage.url}
                alt={primaryImage.alt_text || room.name}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 224px"
                unoptimized={primaryImage.url.startsWith('http')}
                loading="lazy"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-5xl bg-neutral-100">🏨</div>
            )}

            {/* Scarcity signal */}
            {availCount > 0 && availCount <= 5 && (
              <div className="absolute bottom-2 left-2 bg-orange-500 text-white text-xs font-bold px-2 py-0.5 rounded-full shadow">
                Only {availCount} left!
              </div>
            )}
            {availCount === 0 && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                <span className="text-white font-bold text-sm bg-red-600 px-3 py-1.5 rounded-full">Sold Out</span>
              </div>
            )}
            {(room.images?.length ?? 0) > 1 && (
              <div className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded backdrop-blur-sm">
                +{room.images!.length - 1} Photos
              </div>
            )}
          </div>

          {/* Room info */}
          <div className="p-3 border-t border-neutral-100 flex-1">
            <h4 className="font-bold text-neutral-900 text-sm leading-tight mb-2">
              {room.name}
            </h4>
            <div className="space-y-1 text-xs text-neutral-500 mb-3">
              <p className="flex items-center gap-1.5">
                <Users size={11} className="shrink-0" />
                Up to {room.max_occupancy || room.capacity} guests
              </p>
              {room.bed_type && (
                <p className="flex items-center gap-1.5">
                  <BedDouble size={11} className="shrink-0" />
                  {room.bed_type}
                </p>
              )}
              {room.room_size && room.room_size > 0 && (
                <p className="flex items-center gap-1.5">
                  <Layers size={11} className="shrink-0" />
                  {room.room_size} sq ft
                </p>
              )}
            </div>

            {/* Room amenities */}
            {(room.amenities ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {room.amenities!.map((a) => (
                  <span key={a.name} className="flex items-center gap-1 text-xs text-neutral-500 bg-page border border-neutral-100 px-1.5 py-0.5 rounded">
                    <Check size={9} className="text-green-500" />
                    {a.name}
                  </span>
                ))}
              </div>
            )}

            {/* Cancellation policy */}
            <div className="mt-2">
              <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-semibold ${
                isFree ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
              }`}>
                {isFree ? <><Check size={10} strokeWidth={3} /> Free Cancellation</> : <><X size={10} /> Non-Refundable</>}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: Price & Book */}
        <div className="flex-1 border-t lg:border-t-0 lg:border-l border-neutral-100">
          {/* No meal plans — single row */}
          {mealPlans.length === 0 && (
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4">
              <div>
                <p className="font-semibold text-neutral-800 text-sm mb-1">{room.name}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-black text-neutral-900">{formatPrice(basePrice)}</p>
                <p className="text-xs text-neutral-400">+ taxes · per night</p>
                <button
                  disabled={availCount === 0}
                  onClick={() => onSelect(room, undefined)}
                  className="mt-2 text-sm font-bold px-5 py-2 rounded-xl transition-all bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white"
                >
                  {availCount === 0 ? 'Sold Out' : 'Select Room'}
                </button>
              </div>
            </div>
          )}

          {/* Meal plan rows */}
          {mealPlans.map((mp, idx) => {
            const modifier = parseFloat(String(mp.price_modifier));
            const totalPrice = basePrice + modifier;
            const isMpSelected = isSelected && selectedMealPlanCode === mp.code;
            const meta = MEAL_PLAN_META[mp.code];

            return (
              <div
                key={mp.code}
                className={[
                  'grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-4 px-4 py-4 transition-colors',
                  idx < mealPlans.length - 1 ? 'border-b border-neutral-100' : '',
                  isMpSelected ? 'bg-primary-50' : 'hover:bg-page/80',
                ].join(' ')}
              >
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <p className="font-semibold text-neutral-800 text-sm">{mp.name}</p>
                    {meta && (
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded bg-neutral-100 ${meta.color}`}>
                        {meta.short}
                      </span>
                    )}
                  </div>
                  {mp.description && (
                    <p className="text-xs text-neutral-500 mb-2 line-clamp-2">{mp.description}</p>
                  )}
                </div>

                <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-3">
                  <div className="text-left sm:text-right">
                    {modifier > 0 && (
                      <p className="text-xs text-green-600 font-medium">+{formatPrice(modifier)} meals</p>
                    )}
                    <p className="text-2xl font-black text-neutral-900">{formatPrice(totalPrice)}</p>
                    <p className="text-xs text-neutral-400">+ taxes · per night</p>
                  </div>
                  {isMpSelected ? (
                    <button
                      onClick={() => onSelect(room, mp)}
                      className="flex items-center gap-1.5 text-sm font-bold px-4 py-2 rounded-xl bg-primary-100 text-primary-700 border border-primary-300"
                    >
                      <Check size={13} strokeWidth={3} /> Selected
                    </button>
                  ) : (
                    <button
                      disabled={availCount === 0}
                      onClick={() => onSelect(room, mp)}
                      className="flex items-center gap-1.5 text-sm font-bold px-4 py-2 rounded-xl bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white shadow-sm"
                    >
                      {availCount === 0 ? 'Sold Out' : <>Select Room <ChevronRight size={13} /></>}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
