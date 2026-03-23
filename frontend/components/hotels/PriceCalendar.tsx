'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  ChevronLeft, ChevronRight, Loader2, AlertCircle
} from 'lucide-react';
import {
  format, addMonths, startOfMonth, endOfMonth, eachDayOfInterval,
  isToday, isBefore, startOfDay, getDay
} from 'date-fns';
import api from '@/services/api';
import { useFormatPrice } from '@/hooks/useFormatPrice';

// ── Types ─────────────────────────────────────────────────────────────────────

interface PriceDay {
  date: string;
  base_price: number;
  seasonal_price: number;
  discount: number;
  final_price: number;
  availability: number;
  season_type: string | null;   // 'peak' | 'high' | 'shoulder' | 'low' | 'event' | null
  is_weekend: boolean;
  is_holiday: boolean;
  holiday_name: string | null;
  demand_mult: number;
  // Legacy shape support
  price?: number;
  available?: boolean;
  min_stay?: number;
}

interface PriceCalendarProps {
  propertyId: number | string;
  roomTypeId?: number;
  onDateSelect?: (checkIn: string, checkOut: string) => void;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SEASON_BG: Record<string, string> = {
  peak:     'bg-rose-50   ring-1 ring-rose-200',
  event:    'bg-purple-50 ring-1 ring-purple-200',
  high:     'bg-orange-50 ring-1 ring-orange-200',
  shoulder: 'bg-amber-50',
  low:      'bg-emerald-50',
};

function priceColor(price: number, minP: number, maxP: number): string {
  if (maxP === minP) return 'text-green-600';
  const r = (price - minP) / (maxP - minP);
  if (r < 0.33) return 'text-green-600';
  if (r < 0.66) return 'text-amber-600';
  return 'text-rose-600';
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function PriceCalendar({
  propertyId, roomTypeId, onDateSelect, className = ''
}: PriceCalendarProps) {
  const { formatPrice } = useFormatPrice();
  const [currentMonth, setCurrentMonth] = useState(startOfMonth(new Date()));
  const [prices, setPrices]       = useState<Record<string, PriceDay>>({});
  const [loading, setLoading]     = useState(false);
  const [hasError, setHasError]   = useState(false);
  const [checkIn,  setCheckIn]    = useState<string | null>(null);
  const [checkOut, setCheckOut]   = useState<string | null>(null);
  const [hovered, setHovered]     = useState<string | null>(null);

  const fetchPrices = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    setHasError(false);
    try {
      const params: Record<string, string | number> = {
        property_id: propertyId,
        start_date:  format(startOfMonth(currentMonth), 'yyyy-MM-dd'),
        end_date:    format(endOfMonth(addMonths(currentMonth, 1)), 'yyyy-MM-dd'),
      };
      if (roomTypeId) params.room_type_id = roomTypeId;

      const { data } = await api.get('/properties/price-calendar/', { params });
      const map: Record<string, PriceDay> = {};
      (data.dates || data || []).forEach((d: PriceDay) => { map[d.date] = d; });
      setPrices(map);
    } catch {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  }, [propertyId, roomTypeId, currentMonth]);

  useEffect(() => { fetchPrices(); }, [fetchPrices]);

  const handleDayClick = (ds: string) => {
    if (!checkIn || (checkIn && checkOut)) {
      setCheckIn(ds); setCheckOut(null);
    } else {
      if (ds > checkIn) {
        setCheckOut(ds);
        onDateSelect?.(checkIn, ds);
      } else {
        setCheckIn(ds); setCheckOut(null);
      }
    }
  };

  const renderMonth = (monthStart: Date) => {
    const days   = eachDayOfInterval({ start: startOfMonth(monthStart), end: endOfMonth(monthStart) });
    const offset = getDay(startOfMonth(monthStart));
    const today  = startOfDay(new Date());

    const monthPrices = days
      .map(d => {
        const pd = prices[format(d, 'yyyy-MM-dd')];
        return pd?.final_price ?? pd?.price ?? 0;
      })
      .filter(p => p > 0);
    const minP = monthPrices.length ? Math.min(...monthPrices) : 0;
    const maxP = monthPrices.length ? Math.max(...monthPrices) : 0;

    return (
      <div>
        <h4 className="text-sm font-bold text-neutral-800 text-center mb-3 font-heading">
          {format(monthStart, 'MMMM yyyy')}
        </h4>
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(d => (
            <div key={d} className="text-[10px] font-bold text-neutral-400 py-1">{d}</div>
          ))}
          {Array.from({ length: offset }).map((_, i) => <div key={`e${i}`} />)}

          {days.map(day => {
            const ds        = format(day, 'yyyy-MM-dd');
            const pd        = prices[ds];
            const isPast    = isBefore(day, today);
            const isCI      = checkIn  === ds;
            const isCO      = checkOut === ds;
            const inRange   = !!(checkIn && checkOut && ds > checkIn && ds < checkOut);
            const inHover   = !!(checkIn && !checkOut && hovered && ds > checkIn && ds <= hovered);
            const avail     = pd ? (pd.availability ?? (pd.available !== false ? 1 : 0)) : 0;
            const isSold    = pd ? avail === 0 : false;
            const displayP  = pd?.final_price ?? pd?.price ?? 0;
            const seasonBg  = (!isPast && !isCI && !isCO && pd?.season_type)
                                ? SEASON_BG[pd.season_type] || '' : '';

            const cellCls = [
              'relative py-1.5 rounded-lg text-xs transition-all group select-none',
              isCI || isCO ? 'bg-primary-600 text-white shadow-md scale-105 z-10'
              : inRange    ? 'bg-primary-100 text-primary-800'
              : inHover    ? 'bg-primary-50 text-primary-700'
              : isPast     ? 'text-neutral-300 cursor-not-allowed opacity-50'
              : isSold     ? 'text-neutral-300 cursor-not-allowed opacity-60'
              :              `hover:bg-neutral-100 text-neutral-700 cursor-pointer ${seasonBg}`,
              isToday(day) && !isCI && !isCO ? 'ring-1 ring-primary-400' : '',
            ].join(' ');

            return (
              <button
                key={ds}
                disabled={isPast || isSold}
                onClick={() => { if (!isPast && !isSold) handleDayClick(ds); }}
                onMouseEnter={() => setHovered(ds)}
                onMouseLeave={() => setHovered(null)}
                title={pd?.holiday_name || undefined}
                className={cellCls}
              >
                {/* Holiday purple dot */}
                {pd?.is_holiday && !isPast && (
                  <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-purple-500" />
                )}
                {/* Weekend amber dot (only if not holiday) */}
                {pd?.is_weekend && !pd?.is_holiday && !isPast && (
                  <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-amber-400" />
                )}

                {/* Day number */}
                <span className="block font-semibold leading-tight">{format(day, 'd')}</span>

                {/* Price */}
                {pd && avail > 0 && !isPast && displayP > 0 && (
                  <span className={`block text-[9px] font-bold leading-none mt-0.5 ${
                    isCI || isCO ? 'text-white/80' : priceColor(displayP, minP, maxP)
                  }`}>
                    {formatPrice(displayP).replace(/\.00$/, '')}
                  </span>
                )}

                {/* Sold out badge */}
                {isSold && !isPast && (
                  <span className="block text-[8px] text-red-400 leading-none mt-0.5">Sold</span>
                )}

                {/* Holiday tooltip */}
                {pd?.holiday_name && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-30
                                  hidden group-hover:block whitespace-nowrap pointer-events-none
                                  bg-neutral-900 text-white text-[10px] rounded px-2 py-0.5 shadow-lg">
                    {pd.holiday_name}
                    {pd.demand_mult > 1 && (
                      <span className="ml-1 text-amber-300">×{pd.demand_mult}</span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={`bg-white/80 rounded-2xl shadow-card p-5 ${className}`}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-neutral-800 text-sm font-heading">Price Calendar</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentMonth(addMonths(currentMonth, -1))}
            disabled={isBefore(addMonths(currentMonth, -1), startOfMonth(new Date()))}
            className="p-1.5 rounded-lg hover:bg-neutral-100 disabled:opacity-30 transition-colors"
            aria-label="Previous month"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
            aria-label="Next month"
          >
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      {/* ── Selection banner ────────────────────────────────────────────────── */}
      {checkIn && (
        <div className="flex items-center gap-2 mb-3 text-xs bg-primary-50 rounded-lg px-3 py-2 border border-primary-100">
          <span className="font-semibold text-primary-700">
            {checkOut
              ? `${checkIn} → ${checkOut}`
              : `Check-in: ${checkIn} — select check-out date`}
          </span>
          <button
            onClick={() => { setCheckIn(null); setCheckOut(null); }}
            className="ml-auto text-primary-400 hover:text-primary-600 font-bold text-sm leading-none"
            aria-label="Clear selection"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Error banner ─────────────────────────────────────────────────────── */}
      {hasError && (
        <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 mb-3">
          <AlertCircle size={13} />
          <span>Prices temporarily unavailable.</span>
        </div>
      )}

      {/* ── Loading ───────────────────────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-10">
          <Loader2 size={20} className="animate-spin text-neutral-400" />
        </div>
      )}

      {/* ── Calendar grid ─────────────────────────────────────────────────────── */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {renderMonth(currentMonth)}
          {renderMonth(addMonths(currentMonth, 1))}
        </div>
      )}

      {/* ── Legend ────────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-4 pt-3 border-t border-neutral-100
                      text-[10px] text-neutral-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Low price</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" />Medium</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500" />High demand</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />Holiday</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" />Weekend</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-neutral-300" />Sold out</span>
      </div>
    </div>
  );
}
