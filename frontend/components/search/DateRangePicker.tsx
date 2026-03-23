'use client';
import { Calendar } from 'lucide-react';
import { format, addDays, isAfter, isBefore, parseISO, isValid } from 'date-fns';

interface DateRangePickerProps {
  checkIn: string;
  checkOut: string;
  onCheckInChange: (date: string) => void;
  onCheckOutChange: (date: string) => void;
  variant?: 'inline' | 'stacked';
  minDate?: string;
}

/**
 * Reusable date range picker for check-in / check-out.
 * Extracted from search bars and booking panels.
 * Enforces check-out > check-in business rule.
 */
export default function DateRangePicker({
  checkIn,
  checkOut,
  onCheckInChange,
  onCheckOutChange,
  variant = 'inline',
  minDate,
}: DateRangePickerProps) {
  const today = new Date();
  const minDateValue = minDate || format(today, 'yyyy-MM-dd');

  const handleCheckInChange = (val: string) => {
    onCheckInChange(val);
    // Auto-advance checkout if it's before/equal to new check-in
    if (checkOut && val) {
      try {
        const ciDate = parseISO(val);
        const coDate = parseISO(checkOut);
        if (isValid(ciDate) && isValid(coDate) && !isAfter(coDate, ciDate)) {
          onCheckOutChange(format(addDays(ciDate, 1), 'yyyy-MM-dd'));
        }
      } catch {
        // ignore parse errors
      }
    }
  };

  const handleCheckOutChange = (val: string) => {
    if (checkIn && val) {
      try {
        const ciDate = parseISO(checkIn);
        const coDate = parseISO(val);
        if (isValid(ciDate) && isValid(coDate) && isBefore(coDate, addDays(ciDate, 1))) {
          return; // Don't allow checkout before/equal to check-in
        }
      } catch {
        // ignore
      }
    }
    onCheckOutChange(val);
  };

  if (variant === 'stacked') {
    return (
      <div className="grid grid-cols-2 gap-2">
        <DateField
          label="Check-in"
          value={checkIn}
          min={minDateValue}
          onChange={handleCheckInChange}
        />
        <DateField
          label="Check-out"
          value={checkOut}
          min={checkIn || minDateValue}
          onChange={handleCheckOutChange}
        />
      </div>
    );
  }

  // Inline variant — horizontal with field-group styling
  return (
    <div className="flex gap-1 flex-1">
      <div className="field-group flex-1">
        <span className="field-label">Check-in</span>
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-primary-500 shrink-0" />
          <input
            type="date"
            value={checkIn}
            min={minDateValue}
            onChange={(e) => handleCheckInChange(e.target.value)}
            className="bg-transparent text-sm font-bold text-neutral-900 outline-none w-full"
          />
        </div>
      </div>
      <div className="field-group flex-1">
        <span className="field-label">Check-out</span>
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-primary-500 shrink-0" />
          <input
            type="date"
            value={checkOut}
            min={checkIn || minDateValue}
            onChange={(e) => handleCheckOutChange(e.target.value)}
            className="bg-transparent text-sm font-bold text-neutral-900 outline-none w-full"
          />
        </div>
      </div>
    </div>
  );
}

function DateField({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: string;
  min: string;
  onChange: (val: string) => void;
}) {
  return (
    <div>
      <label className="text-xs font-semibold text-neutral-500 block mb-1">{label}</label>
      <div className="flex items-center gap-1 bg-page rounded-xl px-2.5 py-2.5 border border-neutral-200 focus-within:border-primary-400">
        <Calendar size={12} className="text-neutral-400 shrink-0" />
        <input
          type="date"
          value={value}
          min={min}
          onChange={(e) => onChange(e.target.value)}
          className="bg-transparent text-xs font-semibold text-neutral-700 outline-none w-full"
        />
      </div>
    </div>
  );
}
