'use client';
import Image from 'next/image';
import {
  Users, Check, BedDouble, Utensils, AlertCircle, ChevronRight, ChevronDown,
  Wifi, Wind, Tv, Coffee, UtensilsCrossed, Star, X, Layers,
} from 'lucide-react';
import type { RoomType, RoomMealPlan } from '@/types';
import { useState } from 'react';

interface RoomSelectorProps {
  rooms: RoomType[];
  selectedRoomId?: number;
  selectedMealPlanCode?: string;
  onSelect: (room: RoomType, mealPlan?: RoomMealPlan) => void;
}

import { formatPrice as fmt } from '@/lib/formatPrice';

const AMENITY_ICON: Record<string, React.ReactNode> = {
  'free wi-fi': <Wifi size={11} />, 'wifi': <Wifi size={11} />, 'wi-fi': <Wifi size={11} />,
  'air conditioning': <Wind size={11} />, 'ac': <Wind size={11} />, 'air conditioned': <Wind size={11} />,
  'flat-screen tv': <Tv size={11} />, 'tv': <Tv size={11} />, 'television': <Tv size={11} />,
  'breakfast': <Coffee size={11} />, 'coffee maker': <Coffee size={11} />,
  'room service': <UtensilsCrossed size={11} />,
};

/** Industry-standard short codes for meal plan badges */
const MEAL_SHORT_CODE: Record<string, { short: string; color: string }> = {
  room_only:     { short: 'EP',  color: 'text-neutral-700' },
  breakfast:     { short: 'CP',  color: 'text-green-700' },
  half_board:    { short: 'MAP', color: 'text-blue-700' },
  full_board:    { short: 'AP',  color: 'text-purple-700' },
  all_inclusive: { short: 'AI',  color: 'text-amber-700' },
};

/** Get up to 3 benefits from the meal plan description provided by the backend. */
function getMealBenefits(mp: RoomMealPlan): string[] {
  if (mp.description && mp.description.trim()) {
    return mp.description.split(/[,;·•\n]/).map(s => s.trim()).filter(Boolean).slice(0, 3);
  }
  return [];
}

export default function RoomSelector({ rooms, selectedRoomId, selectedMealPlanCode, onSelect }: RoomSelectorProps) {
  const [expandedRoom, setExpandedRoom] = useState<number | null>(null);
  const [galleryRoomId, setGalleryRoomId] = useState<number | null>(null);
  const galleryRoom = galleryRoomId != null ? rooms.find(r => r.id === galleryRoomId) : null;

  if (!rooms || rooms.length === 0) {
    return (
      <div className="text-center py-10 text-neutral-400">
        <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-40" />
        <p className="text-sm font-medium">No room types available</p>
        <p className="text-xs mt-1 text-neutral-300">Try different dates or fewer rooms</p>
      </div>
    );
  }

  return (
    <>
    <div className="space-y-0 border border-neutral-200 rounded-b-xl overflow-hidden lg:rounded-t-none rounded-t-xl">
      {rooms.map((room, roomIdx) => {
        const isRoomSelected = selectedRoomId === room.id;
        const primaryImage = room.images?.find(i => i.is_primary) ?? room.images?.[0];
        const availCount = room.inventory_remaining ?? room.available_count ?? 0;
        const mealPlans = (room.meal_plans ?? []).filter(mp => mp.is_available !== false);
        const basePrice = parseFloat(String(room.base_price));
        const isFree = room.cancellation_policy === 'free';
        const isExpanded = expandedRoom === room.id;

        return (
          <div
            key={room.id}
            className={[
              'bg-white transition-all duration-200',
              roomIdx > 0 ? 'border-t-2 border-neutral-200' : '',
              isRoomSelected ? 'ring-2 ring-inset ring-primary-400' : '',
            ].join(' ')}
          >
            {/* ── Goibibo 3-column layout: Room Type | Options | Price ── */}
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_200px]">

              {/* ── COL 1: Room image + info ─────────────────────────── */}
              <div className="flex flex-col border-b lg:border-b-0 lg:border-r border-neutral-100">
                {/* Image */}
                <div className="relative h-40 lg:h-44 bg-neutral-100 overflow-hidden">
                  {primaryImage?.url ? (
                    <Image
                      src={primaryImage.url}
                      alt={primaryImage.alt_text || room.name}
                      fill
                      className="object-cover"
                      sizes="(max-width: 1024px) 100vw, 220px"
                      unoptimized={primaryImage.url.startsWith('http')}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-5xl bg-neutral-100">🏨</div>
                  )}
                  {/* Photo count badge */}
                  {(room.images?.length ?? 0) > 1 && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setGalleryRoomId(room.id); }}
                      className="absolute bottom-2 left-2 bg-black/60 text-white text-[10px] font-bold px-2 py-0.5 rounded backdrop-blur-sm hover:bg-black/80 transition-colors cursor-pointer"
                    >
                      📷 {room.images!.length} Photos
                    </button>
                  )}
                  {/* Scarcity badge */}
                  {availCount > 0 && availCount <= 5 && (
                    <div className="absolute top-2 left-2 bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded">
                      Only {availCount} left!
                    </div>
                  )}
                  {availCount === 0 && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                      <span className="text-white font-bold text-sm bg-red-600 px-3 py-1.5 rounded-full">Sold Out</span>
                    </div>
                  )}
                </div>

                {/* Room details below image */}
                <div className="p-3 flex-1">
                  <h4 className="font-bold text-neutral-900 text-sm leading-tight mb-2 font-heading">
                    {room.name}
                  </h4>
                  <div className="space-y-1 text-[11px] text-neutral-500 mb-2">
                    <p className="flex items-center gap-1.5"><Users size={10} className="shrink-0" /> Up to {room.max_occupancy || room.capacity} guests</p>
                    {room.bed_type && <p className="flex items-center gap-1.5"><BedDouble size={10} className="shrink-0" /> {room.bed_type}</p>}
                    {room.room_size && room.room_size > 0 && <p className="flex items-center gap-1.5"><Layers size={10} className="shrink-0" /> {room.room_size} sq ft</p>}
                  </div>
                  {/* Room amenities — compact */}
                  {(room.amenities ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {room.amenities!.slice(0, 4).map((a) => (
                        <span key={a.name} className="flex items-center gap-0.5 text-[10px] text-neutral-500 bg-neutral-50 border border-neutral-100 px-1.5 py-0.5 rounded">
                          {AMENITY_ICON[a.name.toLowerCase()] ?? <Check size={8} className="text-green-500" />}
                          {a.name}
                        </span>
                      ))}
                      {room.amenities!.length > 4 && (
                        <span className="text-[10px] text-neutral-400">+{room.amenities!.length - 4} more</span>
                      )}
                    </div>
                  )}
                  <button
                    onClick={() => setExpandedRoom(isExpanded ? null : room.id)}
                    className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-0.5"
                  >
                    View More Details <ChevronDown size={11} className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </button>
                  {isExpanded && (
                    <div className="mt-2 text-[11px] text-neutral-500 bg-neutral-50 rounded-lg p-2 border border-neutral-100">
                      <p className="font-semibold text-neutral-700 mb-1">Cancellation:</p>
                      <p>{isFree ? '✅ Free cancellation until 24h before check-in' : '❌ Non-refundable'}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* ── COL 2+3: Options rows (spans cols 2 & 3 via sub-grid) ── */}
              <div className="lg:col-span-2">

                {/* No meal plans — single row */}
                {mealPlans.length === 0 && (
                  <div className="grid grid-cols-1 lg:grid-cols-[1fr_200px] h-full">
                    <div className="p-4 flex flex-col justify-center border-b lg:border-b-0 lg:border-r border-neutral-100">
                      <p className="font-semibold text-neutral-800 text-sm mb-1.5">{room.name}</p>
                      <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-semibold w-fit ${isFree ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                        {isFree ? <><Check size={9} strokeWidth={3} /> Free Cancellation</> : <><X size={9} /> Non-Refundable</>}
                      </span>
                    </div>
                    <div className="p-4 flex flex-col items-end justify-center">
                      <p className="text-xl font-black text-neutral-900 font-heading">{fmt(basePrice)}</p>
                      <p className="text-[10px] text-neutral-400">+ taxes · per night</p>
                      <button
                        disabled={availCount === 0}
                        onClick={() => onSelect(room, undefined)}
                        className="mt-2 text-xs font-bold px-5 py-2 rounded-lg transition-all border-2 border-primary-600 text-primary-600 hover:bg-primary-600 hover:text-white disabled:opacity-50 uppercase tracking-wide"
                      >
                        {availCount === 0 ? 'Sold Out' : 'SELECT ROOM'}
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Meal plan rows — Goibibo table layout ──────────── */}
                {mealPlans.map((mp, idx) => {
                  const modifier = parseFloat(String(mp.price_modifier));
                  const totalPrice = basePrice + modifier;
                  const isSelected = isRoomSelected && selectedMealPlanCode === mp.code;
                  const benefits = getMealBenefits(mp);

                  return (
                    <div
                      key={mp.code}
                      className={[
                        'grid grid-cols-1 lg:grid-cols-[1fr_200px] transition-colors',
                        idx < mealPlans.length - 1 ? 'border-b border-neutral-100' : '',
                        isSelected ? 'bg-primary-50' : 'hover:bg-blue-50/30',
                      ].join(' ')}
                    >
                      {/* Benefits column */}
                      <div className="p-4 border-b lg:border-b-0 lg:border-r border-neutral-100">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-bold text-neutral-400">{idx + 1}.</span>
                          <p className="font-semibold text-neutral-800 text-sm">{mp.name}</p>
                          {MEAL_SHORT_CODE[mp.code] && (
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-neutral-100 ${MEAL_SHORT_CODE[mp.code].color}`}>
                              {MEAL_SHORT_CODE[mp.code].short}
                            </span>
                          )}
                        </div>
                        <ul className="space-y-1 mb-2.5 ml-5">
                          {benefits.map((b) => (
                            <li key={b} className="flex items-start gap-1.5 text-[11px] text-neutral-600">
                              <Check size={10} className="text-green-500 shrink-0 mt-0.5" strokeWidth={3} />
                              {b}
                            </li>
                          ))}
                        </ul>
                        <div className="flex items-center gap-2 ml-5">
                          <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                            isFree ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-500 border border-red-100'
                          }`}>
                            {isFree
                              ? <><Check size={8} strokeWidth={3} /> Free Cancellation</>
                              : <><X size={8} /> Non-Refundable</>
                            }
                          </span>
                        </div>
                      </div>

                      {/* Price + CTA column */}
                      <div className="p-4 flex flex-col items-end justify-center gap-1">
                        <p className="text-xl font-black text-neutral-900 font-heading">
                          {fmt(totalPrice)}
                        </p>
                        <p className="text-[10px] text-neutral-400">+ taxes · per night</p>

                        {isSelected ? (
                          <button
                            onClick={() => onSelect(room, mp)}
                            className="mt-1.5 flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg bg-primary-600 text-white border-2 border-primary-600 transition-all uppercase tracking-wide"
                          >
                            <Check size={12} strokeWidth={3} /> SELECTED
                          </button>
                        ) : (
                          <button
                            disabled={availCount === 0}
                            onClick={() => onSelect(room, mp)}
                            className="mt-1.5 flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg transition-all border-2 border-primary-600 text-primary-600 hover:bg-primary-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed uppercase tracking-wide"
                          >
                            {availCount === 0 ? 'SOLD OUT' : 'SELECT ROOM'}
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
      })}
    </div>

    {/* ── Room Gallery Modal ── */}
    {galleryRoom && galleryRoom.images && galleryRoom.images.length > 0 && (
      <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setGalleryRoomId(null)}>
        <div className="relative bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between p-4 border-b border-neutral-100">
            <h3 className="font-bold text-neutral-900 text-sm">{galleryRoom.name} — Photos</h3>
            <button onClick={() => setGalleryRoomId(null)} className="p-1 rounded-full hover:bg-neutral-100 transition-colors">
              <X size={18} />
            </button>
          </div>
          <div className="p-4 overflow-y-auto max-h-[calc(90vh-60px)] grid grid-cols-2 gap-3">
            {galleryRoom.images.map((img, i) => (
              <div key={i} className="relative aspect-video bg-neutral-100 rounded-xl overflow-hidden">
                <Image
                  src={img.url}
                  alt={img.alt_text || `${galleryRoom.name} photo ${i + 1}`}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 400px"
                  unoptimized={img.url.startsWith('http')}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    )}
    </>
  );
}
