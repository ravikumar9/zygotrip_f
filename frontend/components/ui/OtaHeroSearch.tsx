'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { MapPin, Calendar, Users, Search, Building2, Map } from 'lucide-react';
import { clsx } from 'clsx';
import { fetchAutosuggest } from '@/services/apiClient';

// ── Types ────────────────────────────────────────────────────────────────────
interface SuggestionItem {
  type: 'city' | 'area' | 'property';
  id: number | string | null | undefined;
  label: string;
  sublabel?: string;
  slug?: string | null;
  count?: number | null;
}

// ── Debounce ─────────────────────────────────────────────────────────────────
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ── Config ───────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'hotels',   label: 'Hotels',   emoji: '🏨' },
  { id: 'buses',    label: 'Buses',    emoji: '🚌' },
  { id: 'cabs',     label: 'Cabs',     emoji: '🚕' },
  { id: 'packages', label: 'Packages', emoji: '🌴' },
] as const;

type TabId = (typeof TABS)[number]['id'];

const ICON_MAP = {
  city:     <Map size={14} className="text-primary-500 shrink-0" />,
  area:     <MapPin size={14} className="text-accent-500 shrink-0" />,
  property: <Building2 size={14} className="text-neutral-400 shrink-0" />,
};

// ── Component ─────────────────────────────────────────────────────────────────
export default function OtaHeroSearch() {
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<TabId>('hotels');
  const [city,     setCity]     = useState('');
  const [checkIn,  setCheckIn]  = useState(() => new Date().toISOString().split('T')[0]);
  const [checkOut, setCheckOut] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().split('T')[0];
  });
  const [guests,   setGuests]   = useState(2);

  const [suggestions,    setSuggestions]    = useState<SuggestionItem[]>([]);
  const [showSuggestions,setShowSuggestions]= useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);

  const suggestRef = useRef<HTMLDivElement>(null);
  const debouncedCity = useDebounce(city, 250);

  // Fetch suggestions
  useEffect(() => {
    if (!debouncedCity || debouncedCity.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    setSuggestLoading(true);
    fetchAutosuggest(debouncedCity, 8).then(res => {
      setSuggestions(res as SuggestionItem[]);
      setShowSuggestions(res.length > 0);
      setSuggestLoading(false);
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
    if (city)     params.set('location', city);
    if (checkIn)  params.set('checkin',  checkIn);
    if (checkOut) params.set('checkout', checkOut);
    if (guests > 1) params.set('adults', String(guests));
    router.push(`/${activeTab}?${params.toString()}`);
    setShowSuggestions(false);
  };

  const today    = new Date().toISOString().split('T')[0];
  const minOut   = checkIn || today;

  return (
    <div className="w-full max-w-4xl mx-auto">

      {/* ── Service Tabs ──────────────────────────────────────── */}
      <div className="flex items-center gap-1 flex-wrap">
        {TABS.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={clsx('search-tab', activeTab === tab.id && 'active')}
            style={activeTab !== tab.id ? { color: 'rgba(255,255,255,0.65)' } : undefined}
          >
            <span className="text-base leading-none">{tab.emoji}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Search Card ──────────────────────────────────────── */}
      <form
        onSubmit={handleSearch}
        className="bg-white rounded-b-2xl rounded-tr-2xl p-4 sm:p-5"
        style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.22)' }}
      >
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">

          {/* Destination */}
          <div className="flex-1 relative" ref={suggestRef}>
            <div className="field-group h-full">
              <span className="field-label flex items-center gap-1.5">
                <MapPin size={10} style={{ color: 'var(--primary)' }} />
                Where do you want to go?
              </span>
              <input
                type="text"
                placeholder="City, area or property"
                value={city}
                onChange={e => { setCity(e.target.value); setShowSuggestions(true); }}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                className="field-main bg-transparent outline-none w-full"
                style={{ fontSize: 20 }}
                autoComplete="off"
                spellCheck={false}
              />
              <p className="field-sub">
                {suggestLoading ? 'Searching…' : city ? 'Enter city, area or hotel name' : 'e.g. Coorg, Goa, Hyderabad'}
              </p>
            </div>

            {/* Autosuggest dropdown — min-width 400px so city names never truncate */}
            {showSuggestions && suggestions.length > 0 && (
              <div
                className="absolute top-full left-0 mt-1.5 z-[9999] bg-white rounded-2xl border border-neutral-100 shadow-modal overflow-hidden animate-slide-down"
                style={{ minWidth: '400px', width: 'max(100%, 400px)' }}
              >
                <div className="px-4 py-2 bg-neutral-50 border-b border-neutral-100">
                  <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Suggestions</p>
                </div>
                {suggestions.map((item, i) => (
                  <button
                    key={`${item.type}-${item.id ?? i}`}
                    type="button"
                    onClick={() => handleSelect(item)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-primary-50 transition-colors text-left border-b border-neutral-50 last:border-0"
                  >
                    {/* Icon circle — matches HeroSearch style */}
                    <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center shrink-0">
                      {ICON_MAP[item.type] ?? ICON_MAP.city}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-neutral-800 truncate">{item.label}</p>
                      {item.sublabel && (
                        <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>
                      )}
                    </div>
                    {item.count != null && item.count > 0 && (
                      <span className="text-xs bg-neutral-100 text-neutral-500 font-medium px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap">
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

          {/* Check-in */}
          <div className="flex-1">
            <div className="field-group h-full">
              <span className="field-label flex items-center gap-1.5">
                <Calendar size={10} style={{ color: 'var(--accent)' }} />
                Check-in
              </span>
              <input
                type="date"
                value={checkIn}
                min={today}
                onChange={e => {
                  setCheckIn(e.target.value);
                  if (checkOut && e.target.value >= checkOut) setCheckOut('');
                }}
                className="field-main bg-transparent outline-none w-full cursor-pointer"
                style={{ fontSize: 18, colorScheme: 'light' }}
              />
              <p className="field-sub">{checkIn ? 'Check-in date' : 'Select date'}</p>
            </div>
          </div>

          {/* Check-out */}
          <div className="flex-1">
            <div className="field-group h-full">
              <span className="field-label flex items-center gap-1.5">
                <Calendar size={10} style={{ color: 'var(--accent)' }} />
                Check-out
              </span>
              <input
                type="date"
                value={checkOut}
                min={minOut}
                onChange={e => setCheckOut(e.target.value)}
                className="field-main bg-transparent outline-none w-full cursor-pointer"
                style={{ fontSize: 18, colorScheme: 'light' }}
              />
              <p className="field-sub">{checkOut ? 'Check-out date' : 'Select date'}</p>
            </div>
          </div>

          {/* Guests */}
          <div>
            <div className="field-group h-full">
              <span className="field-label flex items-center gap-1.5">
                <Users size={10} style={{ color: 'var(--primary)' }} />
                Guests
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setGuests(Math.max(1, guests - 1))}
                  className="w-7 h-7 rounded-full flex items-center justify-center font-black text-base leading-none select-none"
                  style={{ background: '#f3f4f6' }}
                  aria-label="Decrease guests"
                >−</button>
                <span className="field-main w-7 text-center" style={{ fontSize: 20 }}>
                  {guests}
                </span>
                <button
                  type="button"
                  onClick={() => setGuests(Math.min(20, guests + 1))}
                  className="w-7 h-7 rounded-full flex items-center justify-center font-black text-base leading-none select-none text-white"
                  style={{ background: 'var(--primary)' }}
                  aria-label="Increase guests"
                >+</button>
              </div>
              <p className="field-sub">Adults</p>
            </div>
          </div>

          {/* Search Button */}
          <button
            type="submit"
            className="btn-search px-7 py-4 text-sm shrink-0 self-stretch sm:self-auto"
            style={{ borderRadius: 14, minWidth: 130 }}
          >
            <Search size={16} />
            SEARCH
          </button>

        </div>
      </form>
    </div>
  );
}
