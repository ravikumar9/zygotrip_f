'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, SlidersHorizontal, ChevronDown, ChevronUp } from 'lucide-react';
import { clsx } from 'clsx';

export interface FilterState {
  minPrice: number;
  maxPrice: number;
  starRatings: number[];
  guestRating: number;         // minimum (0 = any)
  amenities: string[];
  propertyTypes: string[];
  freeCancellation: boolean;
  payAtHotel: boolean;
}

export const DEFAULT_FILTERS: FilterState = {
  minPrice: 0,
  maxPrice: 20000,
  starRatings: [],
  guestRating: 0,
  amenities: [],
  propertyTypes: [],
  freeCancellation: false,
  payAtHotel: false,
};

const PRICE_CHIPS = [
  { label: 'Under ₹1,500', min: 0, max: 1500 },
  { label: '₹1,500–₹3,000', min: 1500, max: 3000 },
  { label: '₹3,000–₹6,000', min: 3000, max: 6000 },
  { label: '₹6,000+', min: 6000, max: 20000 },
];

const PROPERTY_TYPES = ['Hotel', 'Hostel', 'Apartment', 'Villa', 'Resort', 'Homestay', 'Guest House'];

const COMMON_AMENITIES = [
  'Free WiFi', 'Swimming Pool', 'Parking', 'Restaurant',
  'Gym / Fitness', 'Air Conditioning', 'Spa', 'Bar / Lounge',
  'Airport Shuttle', 'Breakfast Included', 'Pet Friendly', '24h Front Desk',
];

interface FilterBottomSheetProps {
  open: boolean;
  onClose: () => void;
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  resultCount?: number;
}

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-neutral-100 last:border-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between py-4 text-left"
      >
        <span className="text-sm font-bold text-neutral-800">{title}</span>
        {open ? (
          <ChevronUp size={16} className="text-neutral-400" />
        ) : (
          <ChevronDown size={16} className="text-neutral-400" />
        )}
      </button>
      {open && <div className="pb-4">{children}</div>}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm text-neutral-700">{label}</span>
      <div
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative w-10 h-5.5 rounded-full transition-colors',
          checked ? 'bg-primary-600' : 'bg-neutral-200',
        )}
        style={{ width: 40, height: 22 }}
      >
        <span
          className="absolute top-0.5 left-0.5 w-4.5 h-4.5 bg-white rounded-full shadow transition-transform"
          style={{
            width: 18,
            height: 18,
            transform: checked ? 'translateX(18px)' : 'translateX(0)',
          }}
        />
      </div>
    </label>
  );
}

export default function FilterBottomSheet({
  open,
  onClose,
  filters,
  onApply,
  resultCount,
}: FilterBottomSheetProps) {
  const [local, setLocal] = useState<FilterState>(filters);

  // Sync when props change
  useEffect(() => {
    setLocal(filters);
  }, [filters]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  const update = useCallback(<K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setLocal((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toggleArray = useCallback(<T,>(arr: T[], value: T): T[] => {
    return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
  }, []);

  const activeCount = [
    local.starRatings.length > 0,
    local.guestRating > 0,
    local.amenities.length > 0,
    local.propertyTypes.length > 0,
    local.freeCancellation,
    local.payAtHotel,
    local.minPrice > 0 || local.maxPrice < 20000,
  ].filter(Boolean).length;

  const handleReset = () => setLocal(DEFAULT_FILTERS);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40 md:hidden"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="fixed inset-x-0 bottom-0 z-50 md:hidden bg-white rounded-t-2xl shadow-2xl max-h-[90vh] flex flex-col animate-slide-up">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1 shrink-0">
          <div className="w-10 h-1 bg-neutral-200 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-neutral-100 shrink-0">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={18} className="text-neutral-600" />
            <h3 className="font-bold text-neutral-900">Filters</h3>
            {activeCount > 0 && (
              <span className="bg-primary-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
                {activeCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              className="text-xs font-semibold text-primary-600 hover:text-primary-800"
            >
              Reset all
            </button>
            <button onClick={onClose} className="p-1.5 rounded-full hover:bg-neutral-100">
              <X size={18} className="text-neutral-500" />
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-5">

          {/* ── Price ── */}
          <Section title="Price per night">
            {/* Quick chips */}
            <div className="flex flex-wrap gap-2 mb-3">
              {PRICE_CHIPS.map((chip) => {
                const active = local.minPrice === chip.min && local.maxPrice === chip.max;
                return (
                  <button
                    key={chip.label}
                    onClick={() => {
                      update('minPrice', chip.min);
                      update('maxPrice', chip.max);
                    }}
                    className={clsx(
                      'text-xs font-semibold px-3 py-1.5 rounded-full border transition-all',
                      active
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-400',
                    )}
                  >
                    {chip.label}
                  </button>
                );
              })}
            </div>
            {/* Range display */}
            <div className="flex items-center justify-between text-xs text-neutral-500 mb-2">
              <span>₹{local.minPrice.toLocaleString('en-IN')}</span>
              <span>₹{local.maxPrice.toLocaleString('en-IN')}</span>
            </div>
            {/* Dual slider approximation with two inputs */}
            <div className="space-y-2">
              <div>
                <label className="text-xs text-neutral-400 block mb-1">Min price</label>
                <input
                  type="range"
                  min={0}
                  max={20000}
                  step={500}
                  value={local.minPrice}
                  onChange={(e) => {
                    const v = Math.min(Number(e.target.value), local.maxPrice - 500);
                    update('minPrice', v);
                  }}
                  className="w-full accent-primary-600"
                />
              </div>
              <div>
                <label className="text-xs text-neutral-400 block mb-1">Max price</label>
                <input
                  type="range"
                  min={0}
                  max={20000}
                  step={500}
                  value={local.maxPrice}
                  onChange={(e) => {
                    const v = Math.max(Number(e.target.value), local.minPrice + 500);
                    update('maxPrice', v);
                  }}
                  className="w-full accent-primary-600"
                />
              </div>
            </div>
          </Section>

          {/* ── Star Rating ── */}
          <Section title="Star Category">
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((star) => {
                const active = local.starRatings.includes(star);
                return (
                  <button
                    key={star}
                    onClick={() => update('starRatings', toggleArray(local.starRatings, star))}
                    className={clsx(
                      'flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-full border transition-all',
                      active
                        ? 'bg-amber-400 text-white border-amber-400'
                        : 'bg-white text-neutral-600 border-neutral-200 hover:border-amber-400',
                    )}
                  >
                    {'★'.repeat(star)}
                  </button>
                );
              })}
            </div>
          </Section>

          {/* ── Guest Rating ── */}
          <Section title="Guest Rating">
            <div className="flex flex-wrap gap-2">
              {[
                { label: 'Any', value: 0 },
                { label: '3.0+', value: 3 },
                { label: '3.5+', value: 3.5 },
                { label: '4.0+', value: 4 },
                { label: '4.5+', value: 4.5 },
              ].map(({ label, value }) => (
                <button
                  key={value}
                  onClick={() => update('guestRating', value)}
                  className={clsx(
                    'text-xs font-bold px-3 py-1.5 rounded-full border transition-all',
                    local.guestRating === value
                      ? 'bg-green-600 text-white border-green-600'
                      : 'bg-white text-neutral-600 border-neutral-200 hover:border-green-400',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </Section>

          {/* ── Amenities ── */}
          <Section title="Amenities" defaultOpen={false}>
            <div className="grid grid-cols-2 gap-2">
              {COMMON_AMENITIES.map((a) => {
                const active = local.amenities.includes(a);
                return (
                  <label
                    key={a}
                    className={clsx(
                      'flex items-center gap-2 px-3 py-2 rounded-xl border cursor-pointer transition-all text-xs font-medium',
                      active
                        ? 'border-primary-400 bg-primary-50 text-primary-700'
                        : 'border-neutral-200 text-neutral-600 hover:border-primary-300',
                    )}
                  >
                    <input
                      type="checkbox"
                      className="hidden"
                      checked={active}
                      onChange={() => update('amenities', toggleArray(local.amenities, a))}
                    />
                    <span
                      className={clsx(
                        'w-3.5 h-3.5 rounded border-2 shrink-0 flex items-center justify-center',
                        active ? 'bg-primary-600 border-primary-600' : 'border-neutral-300',
                      )}
                    >
                      {active && (
                        <svg viewBox="0 0 10 8" fill="none" className="w-2 h-2">
                          <path d="M1 4l3 3 5-6" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </span>
                    {a}
                  </label>
                );
              })}
            </div>
          </Section>

          {/* ── Property Type ── */}
          <Section title="Property Type" defaultOpen={false}>
            <div className="flex flex-wrap gap-2">
              {PROPERTY_TYPES.map((t) => {
                const active = local.propertyTypes.includes(t);
                return (
                  <button
                    key={t}
                    onClick={() => update('propertyTypes', toggleArray(local.propertyTypes, t))}
                    className={clsx(
                      'text-xs font-semibold px-3 py-1.5 rounded-full border transition-all',
                      active
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-400',
                    )}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
          </Section>

          {/* ── Booking Policy ── */}
          <Section title="Booking Policy" defaultOpen={false}>
            <div className="space-y-4">
              <Toggle
                label="Free cancellation only"
                checked={local.freeCancellation}
                onChange={(v) => update('freeCancellation', v)}
              />
              <Toggle
                label="Pay at hotel"
                checked={local.payAtHotel}
                onChange={(v) => update('payAtHotel', v)}
              />
            </div>
          </Section>
        </div>

        {/* Sticky footer */}
        <div className="shrink-0 px-5 py-4 border-t border-neutral-100 bg-white">
          <button
            onClick={() => {
              onApply(local);
              onClose();
            }}
            className="w-full py-3 rounded-2xl font-black text-white text-sm transition-colors"
            style={{ background: 'var(--primary)' }}
          >
            Show {resultCount !== undefined ? `${resultCount} ` : ''}Properties
          </button>
        </div>
      </div>
    </>
  );
}
