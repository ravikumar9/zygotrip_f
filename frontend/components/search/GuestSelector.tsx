'use client';
import { useState } from 'react';
import { Users, Minus, Plus } from 'lucide-react';

interface GuestSelectorProps {
  adults: number;
  children?: number;
  rooms: number;
  onAdultsChange: (val: number) => void;
  onChildrenChange?: (val: number) => void;
  onRoomsChange: (val: number) => void;
  compact?: boolean;
}

/**
 * Reusable guest & room selector component.
 * Extracted from inline implementations in search bars and booking panels.
 * Provides increment/decrement controls for adults, children, and rooms.
 */
export default function GuestSelector({
  adults,
  children = 0,
  rooms,
  onAdultsChange,
  onChildrenChange,
  onRoomsChange,
  compact = false,
}: GuestSelectorProps) {
  const [open, setOpen] = useState(false);

  const summary = `${adults} Adult${adults !== 1 ? 's' : ''}${children > 0 ? `, ${children} Child${children !== 1 ? 'ren' : ''}` : ''}, ${rooms} Room${rooms !== 1 ? 's' : ''}`;

  if (compact) {
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="field-group flex items-center gap-2 w-full text-left"
        >
          <Users size={16} className="text-primary-500 shrink-0" />
          <div>
            <span className="field-label">Guests & Rooms</span>
            <p className="text-sm font-bold text-neutral-900">{summary}</p>
          </div>
        </button>

        {open && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white/80 rounded-xl shadow-modal border border-neutral-200 p-4 z-50 animate-slide-down">
            <CounterRow label="Adults" value={adults} min={1} max={12} onChange={onAdultsChange} />
            {onChildrenChange && (
              <CounterRow label="Children" sublabel="0–12 yrs" value={children} min={0} max={6} onChange={onChildrenChange} />
            )}
            <CounterRow label="Rooms" value={rooms} min={1} max={8} onChange={onRoomsChange} />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-full mt-3 btn-primary text-xs py-2"
            >
              Done
            </button>
          </div>
        )}
      </div>
    );
  }

  // Inline variant — no dropdown
  return (
    <div className="space-y-3">
      <CounterRow label="Adults" value={adults} min={1} max={12} onChange={onAdultsChange} />
      {onChildrenChange && (
        <CounterRow label="Children" sublabel="0–12 yrs" value={children} min={0} max={6} onChange={onChildrenChange} />
      )}
      <CounterRow label="Rooms" value={rooms} min={1} max={8} onChange={onRoomsChange} />
    </div>
  );
}

function CounterRow({
  label,
  sublabel,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  sublabel?: string;
  value: number;
  min: number;
  max: number;
  onChange: (val: number) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-neutral-100 last:border-b-0">
      <div>
        <p className="text-sm font-semibold text-neutral-800">{label}</p>
        {sublabel && <p className="text-xs text-neutral-400">{sublabel}</p>}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={value <= min}
          onClick={() => onChange(Math.max(min, value - 1))}
          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center hover:border-primary-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Minus size={12} />
        </button>
        <span className="w-6 text-center text-sm font-bold text-neutral-900 tabular-nums">
          {value}
        </span>
        <button
          type="button"
          disabled={value >= max}
          onClick={() => onChange(Math.min(max, value + 1))}
          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center hover:border-primary-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Plus size={12} />
        </button>
      </div>
    </div>
  );
}
