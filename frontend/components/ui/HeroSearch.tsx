'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { MapPin, Calendar, Users, Search, Building2, Map } from 'lucide-react';
import { fetchAutosuggest } from '@/services/apiClient';

// ── Autosuggest types ──────────────────────────────────────────────────────
interface SuggestionItem {
  type: 'city' | 'area' | 'property';
  id: number | string | null | undefined;
  label: string;
  sublabel?: string;
  slug?: string | null;
  count?: number | null;
}

// ── Debounce hook ──────────────────────────────────────────────────────────
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

const ICON_MAP = {
  city:     <Map size={14} className="text-primary-500 shrink-0" />,
  area:     <MapPin size={14} className="text-accent-500 shrink-0" />,
  property: <Building2 size={14} className="text-neutral-400 shrink-0" />,
};

export default function HeroSearch() {
  const router = useRouter();
  const [city, setCity] = useState('');
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');
  const [guests, setGuests] = useState(2);

  // Autosuggest state
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const suggestRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedCity = useDebounce(city, 250);

  // Fetch suggestions when query changes
  useEffect(() => {
    if (!debouncedCity || debouncedCity.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    fetchAutosuggest(debouncedCity, 8).then(res => {
      setSuggestions(res as SuggestionItem[]);
      setShowSuggestions(res.length > 0);
      setLoading(false);
    });
  }, [debouncedCity]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (suggestRef.current && !suggestRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelect = useCallback((item: SuggestionItem) => {
    if (item.type === 'property' && item.slug) {
      router.push(`/hotels/${item.slug}`);
    } else {
      setCity(item.label);
    }
    setShowSuggestions(false);
  }, [router]);

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    const params = new URLSearchParams();
    if (city) params.set('location', city);
    if (checkIn) params.set('checkin', checkIn);
    if (checkOut) params.set('checkout', checkOut);
    params.set('adults', String(guests)); // always preserve guest count
    router.push(`/hotels?${params.toString()}`);
    setShowSuggestions(false);
  };

  const today = new Date().toISOString().split('T')[0];

  return (
    <form onSubmit={handleSearch}
      className="hero-search-bar p-2 sm:p-3 flex flex-col md:flex-row gap-1 w-full max-w-5xl mx-auto">

      {/* ── Destination ─────────────────────────────────────── */}
      <div className="flex-[2] relative min-w-0" ref={suggestRef}>
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-gray-50 transition-colors">
          <MapPin size={18} className="text-secondary-500 shrink-0" />
          <div className="flex-1 text-left min-w-0">
            <label className="text-xs font-semibold text-gray-500 block">Destination</label>
            <input
              ref={inputRef}
              type="text"
              placeholder="City, area or property"
              value={city}
              onChange={e => { setCity(e.target.value); setShowSuggestions(true); }}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              className="w-full text-sm font-semibold text-gray-800 bg-transparent outline-none placeholder-gray-400"
              autoComplete="off"
            />
          </div>
          {loading && (
            <svg className="animate-spin w-3.5 h-3.5 text-neutral-400 shrink-0" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z"/>
            </svg>
          )}
        </div>

        {/* Dropdown — wider than the input, positioned below */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 mt-2 z-[9999] bg-white rounded-2xl border border-neutral-200 shadow-2xl overflow-hidden"
               style={{ minWidth: '360px', width: 'max(100%, 360px)' }}>
            <div className="px-4 py-2 bg-neutral-50 border-b border-neutral-100">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Suggestions</p>
            </div>
            {suggestions.map((item, i) => (
              <button
                key={`${item.type}-${item.id ?? i}`}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); handleSelect(item); }}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-primary-50 transition-colors text-left border-b border-neutral-50 last:border-0"
              >
                <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center shrink-0">
                  {ICON_MAP[item.type] ?? ICON_MAP.city}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-neutral-800 truncate">{item.label}</p>
                  {item.sublabel && (
                    <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>
                  )}
                </div>
                {item.count != null && item.count > 0 && (
                  <span className="text-xs bg-neutral-100 text-neutral-500 font-medium px-2 py-0.5 rounded-full shrink-0">
                    {item.count} hotels
                  </span>
                )}
                {item.type === 'property' && (
                  <span className="text-xs bg-primary-100 text-primary-700 font-medium px-2 py-0.5 rounded-full shrink-0">Hotel</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="hidden md:block w-px bg-gray-200 my-2" />

      {/* ── Check-in ─────────────────────────────────────────── */}
      <div className="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-gray-50 transition-colors">
        <Calendar size={18} className="text-accent-500 shrink-0" />
        <div className="flex-1 text-left">
          <label className="text-xs font-semibold text-gray-500 block">Check-in</label>
          <input
            type="date"
            value={checkIn}
            min={today}
            onChange={e => setCheckIn(e.target.value)}
            className="w-full text-sm font-semibold text-gray-800 bg-transparent outline-none"
          />
        </div>
      </div>

      <div className="hidden md:block w-px bg-gray-200 my-2" />

      {/* ── Check-out ─────────────────────────────────────────── */}
      <div className="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-gray-50 transition-colors">
        <Calendar size={18} className="text-accent-500 shrink-0" />
        <div className="flex-1 text-left">
          <label className="text-xs font-semibold text-gray-500 block">Check-out</label>
          <input
            type="date"
            value={checkOut}
            min={checkIn || today}
            onChange={e => setCheckOut(e.target.value)}
            className="w-full text-sm font-semibold text-gray-800 bg-transparent outline-none"
          />
        </div>
      </div>

      <div className="hidden md:block w-px bg-gray-200 my-2" />

      {/* ── Guests ───────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-gray-50 transition-colors">
        <Users size={18} className="text-primary-500 shrink-0" />
        <div>
          <label className="text-xs font-semibold text-gray-500 block">Guests</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setGuests(Math.max(1, guests - 1))}
              className="w-5 h-5 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center text-xs font-bold"
            >
              −
            </button>
            <span className="text-sm font-bold text-gray-800 w-4 text-center">{guests}</span>
            <button
              type="button"
              onClick={() => setGuests(guests + 1)}
              className="w-5 h-5 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center text-xs font-bold"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* ── Search Button ────────────────────────────────────── */}
      <button
        type="submit"
        className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-white font-bold text-sm transition-all shrink-0"
        style={{ background: 'linear-gradient(135deg, #eb5757, #c0392b)', minWidth: 120 }}
      >
        <Search size={16} />
        Search
      </button>
    </form>
  );
}
