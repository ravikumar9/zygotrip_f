'use client';

/**
 * CurrencyPicker — dropdown to switch display currency, stored in localStorage.
 * Use inside any header/navbar — reads from CurrencyContext.
 */

import React, { useState, useRef, useEffect } from 'react';
import { useCurrency } from '../../contexts/CurrencyContext';

const FLAG_MAP: Record<string, string> = {
  INR: '🇮🇳', USD: '🇺🇸', EUR: '🇪🇺', GBP: '🇬🇧', AED: '🇦🇪',
  SGD: '🇸🇬', THB: '🇹🇭', MYR: '🇲🇾', AUD: '🇦🇺', CAD: '🇨🇦',
  JPY: '🇯🇵', KRW: '🇰🇷', SAR: '🇸🇦', QAR: '🇶🇦', BDT: '🇧🇩',
  LKR: '🇱🇰', NPR: '🇳🇵',
};

export default function CurrencyPicker() {
  const { currency, setCurrency, currencies, loading } = useCurrency();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (loading || currencies.length === 0) {
    return (
      <div className="flex items-center gap-1 px-2 py-1.5 bg-gray-100 rounded-lg text-sm text-gray-400">
        <span>💱</span>
        <span>INR</span>
      </div>
    );
  }

  const current = currencies.find((c) => c.code === currency);
  const flag = FLAG_MAP[currency] || '🌍';

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm"
        aria-label="Select currency"
      >
        <span>{flag}</span>
        <span>{currency}</span>
        <svg
          className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-56 max-h-72 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg z-50">
          <div className="p-2">
            {currencies.map((c) => (
              <button
                key={c.code}
                onClick={() => {
                  setCurrency(c.code);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  c.code === currency
                    ? 'bg-blue-50 text-blue-700 font-semibold'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <span className="text-base">{FLAG_MAP[c.code] || '🌍'}</span>
                <span className="flex-1 text-left">
                  <span className="font-medium">{c.code}</span>
                  <span className="text-gray-400 ml-1.5">{c.symbol}</span>
                </span>
                <span className="text-xs text-gray-400 truncate max-w-[100px]">{c.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
