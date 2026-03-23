'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, ArrowRight, MapPin, Users, Clock, Wifi, Zap,
  Snowflake, Shield, ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';
import { getBusDetail } from '@/services/buses';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type { Bus, BusSeat } from '@/types/buses';

/* ── Helpers ──────────────────────────────────────────────────────── */

function formatTime(time: string) {
  if (!time) return '--:--';
  const [h, m] = time.split(':');
  const hour = parseInt(h, 10);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const h12 = hour % 12 || 12;
  return `${h12}:${m} ${ampm}`;
}

function getJourneyDuration(dep: string, arr: string): string {
  if (!dep || !arr) return '';
  try {
    const [dh, dm] = dep.split(':').map(Number);
    const [ah, am] = arr.split(':').map(Number);
    let mins = (ah * 60 + am) - (dh * 60 + dm);
    if (mins < 0) mins += 24 * 60;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h > 0 ? `${h}h ${m > 0 ? m + 'm' : ''}` : `${m}m`;
  } catch { return ''; }
}

const AMENITY_ICONS: Record<string, React.ElementType> = {
  wifi: Wifi,
  charging: Zap,
  ac: Snowflake,
};

/* ── Seat colour map ──────────────────────────────────────────────── */

const SEAT_STYLES: Record<string, { bg: string; border: string; text: string; label: string }> = {
  available:  { bg: 'bg-green-50',  border: 'border-green-400', text: 'text-green-700', label: 'Available' },
  selected:   { bg: 'bg-blue-500',  border: 'border-blue-600',  text: 'text-white',     label: 'Selected' },
  booked:     { bg: 'bg-neutral-200', border: 'border-neutral-300', text: 'text-neutral-400', label: 'Booked' },
  ladies:     { bg: 'bg-pink-50',   border: 'border-pink-400',  text: 'text-pink-700',  label: 'Ladies' },
};

/* ── Seat Component ───────────────────────────────────────────────── */

function SeatButton({
  seat, isSelected, onToggle,
}: {
  seat: BusSeat;
  isSelected: boolean;
  onToggle: (seat: BusSeat) => void;
}) {
  const state = isSelected ? 'selected' : !seat.is_available ? 'booked' : seat.is_ladies_seat ? 'ladies' : 'available';
  const style = SEAT_STYLES[state];
  const isClickable = seat.is_available;

  return (
    <button
      type="button"
      disabled={!isClickable}
      onClick={() => isClickable && onToggle(seat)}
      title={`Seat ${seat.seat_number}${!seat.is_available ? ' (Booked)' : seat.is_ladies_seat ? ' (Ladies)' : ''}`}
      className={`
        w-9 h-9 rounded-md border-2 text-[10px] font-bold transition-all flex items-center justify-center
        ${style.bg} ${style.border} ${style.text}
        ${isClickable ? 'cursor-pointer hover:scale-110 hover:shadow-md active:scale-95' : 'cursor-not-allowed opacity-70'}
      `}
    >
      {seat.seat_number}
    </button>
  );
}

/* ── Seat Legend ───────────────────────────────────────────────────── */

function SeatLegend() {
  return (
    <div className="flex items-center gap-4 flex-wrap text-xs">
      {Object.entries(SEAT_STYLES).map(([key, s]) => (
        <div key={key} className="flex items-center gap-1.5">
          <div className={`w-5 h-5 rounded border-2 ${s.bg} ${s.border}`} />
          <span className="text-neutral-600 font-medium">{s.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Visual Seat Map ──────────────────────────────────────────────── */

function SeatMap({
  seatMap,
  selectedIds,
  onToggle,
}: {
  seatMap: Record<string, BusSeat[]>;
  selectedIds: Set<number>;
  onToggle: (seat: BusSeat) => void;
}) {
  // seatMap keys are deck names like "lower" / "upper" or row labels
  const decks = Object.entries(seatMap);

  if (decks.length === 0) {
    return (
      <div className="text-center py-10 text-neutral-400 text-sm">
        Seat map not available for this bus.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {decks.map(([deckName, seats]) => {
        // Group seats by row for grid layout
        const rowMap = new Map<string, BusSeat[]>();
        seats.forEach((s) => {
          const row = s.row || '0';
          if (!rowMap.has(row)) rowMap.set(row, []);
          rowMap.get(row)!.push(s);
        });

        // Sort rows
        const sortedRows = Array.from(rowMap.entries()).sort(
          ([a], [b]) => parseInt(a) - parseInt(b)
        );

        // Determine max columns for grid
        const maxCols = Math.max(...seats.map((s) => s.column || 0), 4);

        return (
          <div key={deckName}>
            {decks.length > 1 && (
              <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-3">
                {deckName} Deck
              </h4>
            )}

            {/* Bus frame visual */}
            <div className="relative bg-page rounded-2xl border-2 border-neutral-200 p-4 pt-10">
              {/* Steering indicator */}
              <div className="absolute top-2 right-4 flex items-center gap-1.5 text-[10px] text-neutral-400 font-bold uppercase tracking-wider">
                <div className="w-6 h-6 rounded-full border-2 border-neutral-300 flex items-center justify-center text-neutral-300">
                  <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2}>
                    <circle cx="12" cy="12" r="9" />
                    <circle cx="12" cy="12" r="3" />
                    <line x1="12" y1="3" x2="12" y2="9" />
                    <line x1="3" y1="12" x2="9" y2="12" />
                    <line x1="12" y1="15" x2="12" y2="21" />
                  </svg>
                </div>
                Driver
              </div>

              {/* Seat grid */}
              <div className="space-y-2">
                {sortedRows.map(([rowLabel, rowSeats]) => {
                  // Sort seats by column
                  const sortedSeats = [...rowSeats].sort((a, b) => a.column - b.column);

                  // Create columns array with gaps for aisle
                  const cells: (BusSeat | null)[] = [];
                  for (let c = 0; c <= maxCols; c++) {
                    const seat = sortedSeats.find((s) => s.column === c);
                    cells.push(seat || null);
                  }

                  // Insert aisle gap after column 1 (between 2-seater left and right)
                  const aislePosition = Math.floor((maxCols + 1) / 2);

                  return (
                    <div key={rowLabel} className="flex items-center gap-1.5">
                      {cells.map((cell, idx) => (
                        <div key={idx} className="flex items-center">
                          {idx === aislePosition && (
                            <div className="w-6 shrink-0" /> /* Aisle gap */
                          )}
                          {cell ? (
                            <SeatButton
                              seat={cell}
                              isSelected={selectedIds.has(cell.id)}
                              onToggle={onToggle}
                            />
                          ) : (
                            <div className="w-9 h-9" /> /* Empty slot */
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN BUS DETAIL CLIENT
═══════════════════════════════════════════════════════════════════ */

export default function BusDetailClient() {
  const { formatPrice } = useFormatPrice();
  const params = useParams();
  const router = useRouter();
  const busId = Number(params.id);

  const [bus, setBus] = useState<(Bus & { seat_map: Record<string, BusSeat[]> }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedSeats, setSelectedSeats] = useState<BusSeat[]>([]);
  const [showAmenities, setShowAmenities] = useState(false);
  const [boarding, setBoarding] = useState('');

  const selectedIds = useMemo(() => new Set(selectedSeats.map((s) => s.id)), [selectedSeats]);

  // ── Load bus ────────────────────────────────────────────────────
  useEffect(() => {
    if (!busId) return;

    const load = async () => {
      try {
        setLoading(true);
        const data = await getBusDetail(busId);
        setBus(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load bus details');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [busId]);

  // ── Seat toggle ─────────────────────────────────────────────────
  const toggleSeat = useCallback((seat: BusSeat) => {
    setSelectedSeats((prev) => {
      const exists = prev.find((s) => s.id === seat.id);
      if (exists) return prev.filter((s) => s.id !== seat.id);
      if (prev.length >= 6) return prev; // Max 6 seats
      return [...prev, seat];
    });
  }, []);

  // ── Pricing ─────────────────────────────────────────────────────
  const totalPrice = useMemo(() => {
    return selectedSeats.length * (bus?.price_per_seat || 0);
  }, [selectedSeats, bus?.price_per_seat]);

  // ── Loading ─────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen page-listing-bg flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={32} className="animate-spin text-neutral-400 mx-auto mb-3" />
          <p className="text-neutral-500 text-sm">Loading bus details...</p>
        </div>
      </div>
    );
  }

  if (error || !bus) {
    return (
      <div className="min-h-screen page-listing-bg flex items-center justify-center">
        <div className="bg-white/80 rounded-2xl shadow-lg p-8 max-w-md text-center">
          <div className="text-5xl mb-4">🚌</div>
          <h2 className="text-xl font-bold text-neutral-900 mb-2">Bus Not Found</h2>
          <p className="text-neutral-500 text-sm mb-6">{error || 'This bus is no longer available.'}</p>
          <Link
            href="/buses"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-white font-bold text-sm"
            style={{ background: 'var(--primary)' }}
          >
            <ArrowLeft size={16} /> Back to Search
          </Link>
        </div>
      </div>
    );
  }

  const duration = getJourneyDuration(bus.departure_time, bus.arrival_time);
  const availableCount = bus.available_seats ?? 0;

  return (
    <div className="min-h-screen page-listing-bg">
      {/* ── Top bar ──────────────────────────────────────────────── */}
      <div className="bg-white/80 border-b sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link
            href="/buses"
            className="text-neutral-400 hover:text-neutral-700 transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold text-neutral-900 truncate">
              {bus.operator_name} — {bus.from_city} → {bus.to_city}
            </h1>
            <p className="text-xs text-neutral-400">
              {bus.journey_date} · {bus.bus_type}
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* ── Route Summary ────────────────────────────────────── */}
        <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm p-5 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            {/* Operator */}
            <div className="flex items-center gap-3 shrink-0">
              <div className="w-12 h-12 rounded-xl bg-neutral-100 flex items-center justify-center text-2xl">
                🚌
              </div>
              <div>
                <h2 className="font-bold text-neutral-900">{bus.operator_name}</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-neutral-100 text-neutral-500">
                    {bus.bus_type}
                  </span>
                  {bus.is_ac && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-green-50 text-green-600">
                      AC
                    </span>
                  )}
                  {bus.is_sleeper && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-purple-50 text-purple-600">
                      Sleeper
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Route timeline */}
            <div className="flex-1 flex items-center gap-3 sm:justify-center">
              <div className="text-center">
                <p className="font-black text-xl text-neutral-900">{formatTime(bus.departure_time)}</p>
                <p className="text-xs text-neutral-400">{bus.from_city}</p>
              </div>
              <div className="flex-1 max-w-48 flex flex-col items-center gap-0.5 px-2">
                {duration && (
                  <span className="text-[10px] font-bold text-neutral-400">{duration}</span>
                )}
                <div className="flex items-center gap-1 w-full">
                  <div className="w-2.5 h-2.5 rounded-full border-2 border-green-400" />
                  <div className="h-px flex-1 bg-neutral-200" />
                  <ArrowRight size={12} className="text-neutral-300 shrink-0" />
                  <div className="h-px flex-1 bg-neutral-200" />
                  <div className="w-2.5 h-2.5 rounded-full border-2 border-red-400" />
                </div>
              </div>
              <div className="text-center">
                <p className="font-black text-xl text-neutral-900">{formatTime(bus.arrival_time)}</p>
                <p className="text-xs text-neutral-400">{bus.to_city}</p>
              </div>
            </div>

            {/* Price */}
            <div className="text-right shrink-0">
              <p className="text-2xl font-black text-neutral-900">{formatPrice(bus.price_per_seat)}</p>
              <p className="text-xs text-neutral-400">per seat</p>
            </div>
          </div>

          {/* Amenities toggle */}
          {bus.amenities && bus.amenities.length > 0 && (
            <div className="mt-4 border-t border-neutral-100 pt-3">
              <button
                onClick={() => setShowAmenities(!showAmenities)}
                className="flex items-center gap-1 text-xs font-bold text-neutral-500 hover:text-neutral-700 transition-colors"
              >
                {bus.amenities.length} amenities
                {showAmenities ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {showAmenities && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {bus.amenities.map((a) => {
                    const Icon = AMENITY_ICONS[a.toLowerCase()] || Shield;
                    return (
                      <span key={a} className="inline-flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-full bg-blue-50 text-blue-600 font-medium">
                        <Icon size={12} /> {a}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Main grid: Seat map + Booking sidebar ───────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Seat Map */}
          <div className="lg:col-span-2">
            <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-neutral-900 font-heading">Select Your Seats</h3>
                <span className={`text-xs font-bold ${availableCount <= 5 ? 'text-orange-500' : 'text-green-600'}`}>
                  <Users size={12} className="inline mr-0.5" />
                  {availableCount} available
                </span>
              </div>

              <SeatLegend />

              <div className="mt-5">
                <SeatMap
                  seatMap={bus.seat_map || {}}
                  selectedIds={selectedIds}
                  onToggle={toggleSeat}
                />
              </div>

              {/* Selected seats list */}
              {selectedSeats.length > 0 && (
                <div className="mt-5 pt-4 border-t border-neutral-100">
                  <p className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">
                    Selected Seats ({selectedSeats.length})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selectedSeats.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => toggleSeat(s)}
                        className="inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                      >
                        Seat {s.seat_number}
                        <span className="text-blue-400 ml-0.5">✕</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Cancellation info */}
            <div className="mt-4 bg-white/80 rounded-2xl border border-neutral-100 shadow-sm p-5">
              <h4 className="font-bold text-neutral-900 text-sm mb-2">Cancellation Policy</h4>
              <div className="space-y-2 text-xs text-neutral-500">
                <div className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-1.5 shrink-0" />
                  <p>Free cancellation up to 24 hours before departure</p>
                </div>
                <div className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 mt-1.5 shrink-0" />
                  <p>50% refund for cancellation 6-24 hours before departure</p>
                </div>
                <div className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 shrink-0" />
                  <p>No refund within 6 hours of departure</p>
                </div>
              </div>
            </div>
          </div>

          {/* Booking Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white/80 rounded-2xl border border-neutral-100 shadow-card p-5 sticky top-20">
              <h3 className="font-bold text-neutral-900 mb-1 font-heading">Booking Summary</h3>
              <p className="text-xs text-neutral-400 mb-4">
                {bus.from_city} → {bus.to_city} · {bus.journey_date}
              </p>

              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-600">Operator</span>
                  <span className="font-medium text-neutral-900">{bus.operator_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Departure</span>
                  <span className="font-medium text-neutral-900">{formatTime(bus.departure_time)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Arrival</span>
                  <span className="font-medium text-neutral-900">{formatTime(bus.arrival_time)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Bus Type</span>
                  <span className="font-medium text-neutral-900">{bus.bus_type}</span>
                </div>

                {selectedSeats.length > 0 && (
                  <>
                    <div className="border-t border-neutral-100 pt-2.5">
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Seats</span>
                        <span className="font-medium text-neutral-900">
                          {selectedSeats.map((s) => s.seat_number).join(', ')}
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-600">Price per seat</span>
                      <span className="font-medium">{formatPrice(bus.price_per_seat)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-600">Quantity</span>
                      <span className="font-medium">× {selectedSeats.length}</span>
                    </div>
                  </>
                )}

                <div className="border-t-2 border-neutral-200 pt-3 flex justify-between font-bold text-neutral-900 text-base">
                  <span>Total</span>
                  <span className="text-xl font-black">
                    {selectedSeats.length > 0 ? formatPrice(totalPrice) : formatPrice(0)}
                  </span>
                </div>
              </div>

              {/* Book CTA */}
              <button
                disabled={selectedSeats.length === 0}
                onClick={() => {
                  // Navigate to checkout with seat info
                  const seatIds = selectedSeats.map((s) => s.id).join(',');
                  router.push(`/checkout?type=bus&bus_id=${bus.id}&seats=${seatIds}&total=${totalPrice}`);
                }}
                className="mt-5 w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-white font-bold text-sm transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: 'var(--primary)' }}
              >
                {selectedSeats.length > 0 ? (
                  <>Book {selectedSeats.length} Seat{selectedSeats.length > 1 ? 's' : ''} <ArrowRight size={16} /></>
                ) : (
                  'Select seats to continue'
                )}
              </button>

              {selectedSeats.length > 0 && (
                <p className="text-center text-[10px] text-neutral-400 mt-2">
                  Seats held for 15 minutes after booking starts
                </p>
              )}

              {/* Max seats warning */}
              {selectedSeats.length >= 6 && (
                <div className="mt-3 bg-amber-50 border border-amber-200 rounded-xl p-2 text-xs text-amber-700 text-center">
                  Maximum 6 seats per booking
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
