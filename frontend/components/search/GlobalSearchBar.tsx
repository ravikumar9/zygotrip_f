'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { MapPin, Calendar, Users, Search, Building2, Map, Loader2, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { fetchAutosuggest } from '@/services/apiClient';
import { useDebounce } from '@/hooks/useDebounce';

// ── Types ────────────────────────────────────────────────────────────────────
interface SuggestionItem {
  type: 'city' | 'area' | 'property';
  id?: number | string | null;
  label: string;
  sublabel?: string;
  slug?: string | null;
  count?: number | null;
}

interface GlobalSearchBarProps {
  /** Control visual layout: hero (homepage), inline (listing page), compact (detail page) */
  variant?: 'hero' | 'inline' | 'compact';
  initialLocation?: string;
  initialCheckin?: string;
  initialCheckout?: string;
  initialGuests?: number;
  initialRooms?: number;
  /** Show horizontal tab row (Hotels/Buses/Cabs/Packages) */
  showTabs?: boolean;
  className?: string;
}

// ── Config ───────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'hotels',   label: 'Hotels',   emoji: '🏨' },
  { id: 'buses',    label: 'Buses',    emoji: '🚌' },
  { id: 'cabs',     label: 'Cabs',     emoji: '🚕' },
  { id: 'packages', label: 'Packages', emoji: '🌴' },
] as const;

type TabId = (typeof TABS)[number]['id'];

const ICON_MAP: Record<string, React.ReactNode> = {
  city:     <Map size={14} className="text-primary-500 shrink-0" />,
  area:     <MapPin size={14} className="text-accent-500 shrink-0" />,
  property: <Building2 size={14} className="text-neutral-400 shrink-0" />,
};

const RECENT_SEARCHES_KEY = 'zygo_recent_searches';
const MAX_RECENT = 5;

function getRecentSearches(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || '[]').slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string) {
  if (typeof window === 'undefined' || !query.trim()) return;
  try {
    const existing = getRecentSearches().filter(s => s !== query);
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify([query, ...existing].slice(0, MAX_RECENT)));
  } catch {
    // ignore storage errors
  }
}

/**
 * GlobalSearchBar — unified OTA search component.
 * Merges functionality from HeroSearch, OtaHeroSearch, and SearchBar.
 * Reusable across homepage, listing page, and hotel detail page.
 *
 * Features:
 * - Location autocomplete with city/area/property suggestions
 * - Date range picker (check-in / check-out)
 * - Guest count selector
 * - Recent searches (localStorage)
 * - Multi-tab support (Hotels/Buses/Cabs/Packages)
 * - Three visual variants: hero, inline, compact
 */
export default function GlobalSearchBar({
  variant = 'hero',
  initialLocation = '',
  initialCheckin,
  initialCheckout,
  initialGuests = 2,
  initialRooms = 1,
  showTabs = false,
  className,
}: GlobalSearchBarProps) {
  const router = useRouter();
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const dayAfter = new Date(today);
  dayAfter.setDate(dayAfter.getDate() + 2);

  const todayStr = today.toISOString().split('T')[0];
  const tomorrowStr = tomorrow.toISOString().split('T')[0];
  const dayAfterStr = dayAfter.toISOString().split('T')[0];

  const [activeTab, setActiveTab] = useState<TabId>('hotels');
  const [location, setLocation] = useState(initialLocation);
  const [checkIn, setCheckIn] = useState(initialCheckin || tomorrowStr);
  const [checkOut, setCheckOut] = useState(initialCheckout || dayAfterStr);
  const [guests, setGuests] = useState(initialGuests);
  const [rooms, setRooms] = useState(initialRooms);

  // Autosuggest state
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedLocation = useDebounce(location, 250);

  // Load recent searches
  useEffect(() => {
    setRecentSearches(getRecentSearches());
  }, []);

  // Fetch suggestions
  useEffect(() => {
    if (!debouncedLocation || debouncedLocation.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    fetchAutosuggest(debouncedLocation, 8)
      .then((res) => {
        setSuggestions(res as SuggestionItem[]);
        setShowSuggestions(res.length > 0);
      })
      .finally(() => setLoading(false));
  }, [debouncedLocation]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
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
      setLocation(item.label);
      saveRecentSearch(item.label);
    }
    setShowSuggestions(false);
  }, [router]);

  const handleRecentSelect = (query: string) => {
    setLocation(query);
    setShowSuggestions(false);
  };

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    const params = new URLSearchParams();
    if (location) {
      params.set('location', location);
      saveRecentSearch(location);
    }
    if (checkIn)  params.set('checkin', checkIn);
    if (checkOut) params.set('checkout', checkOut);
    params.set('adults', String(guests));
    if (rooms > 1) params.set('rooms', String(rooms));

    const base = activeTab === 'hotels' ? '/hotels' :
                 activeTab === 'buses' ? '/buses' :
                 activeTab === 'cabs' ? '/cabs' : '/packages';

    router.push(`${base}?${params.toString()}`);
    setShowSuggestions(false);
  };

  const handleCheckInChange = (val: string) => {
    setCheckIn(val);
    if (checkOut && val >= checkOut) {
      const next = new Date(val);
      next.setDate(next.getDate() + 1);
      setCheckOut(next.toISOString().split('T')[0]);
    }
  };

  const showRecent = !debouncedLocation && recentSearches.length > 0;
  const showDropdown = showSuggestions || (showRecent && showSuggestions !== false && location === '');

  // ── Variant styles ─────────────────────────────────────────────
  const isHero = variant === 'hero';
  const isInline = variant === 'inline';
  const isCompact = variant === 'compact';

  return (
    <div className={clsx('w-full', className)} ref={containerRef}>
      {/* Tab row (optional) */}
      {showTabs && (
        <div className="flex items-center gap-1 mb-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={clsx('search-tab', activeTab === tab.id && 'active')}
            >
              <span>{tab.emoji}</span>
              {tab.label}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={handleSearch}
        className={clsx(
          'flex gap-1 w-full',
          isHero && 'hero-search-bar p-2 sm:p-3 flex-col md:flex-row max-w-5xl mx-auto',
          isInline && 'bg-white/10 backdrop-blur-sm rounded-2xl p-2 flex-col sm:flex-row items-stretch',
          isCompact && 'bg-white rounded-xl shadow-sm border border-neutral-200 p-1.5 flex-row items-stretch',
        )}
      >
        {/* Location field with autosuggest */}
        <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[2]')}>
          <div className={clsx(
            'field-group flex items-center gap-2',
            isInline && 'bg-white/90 border-white/30',
          )}>
            <MapPin size={16} className="text-primary-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="field-label">{isCompact ? 'Where' : 'Destination'}</span>
              <input
                ref={inputRef}
                type="text"
                value={location}
                onChange={(e) => { setLocation(e.target.value); setShowSuggestions(true); }}
                onFocus={() => {
                  if (suggestions.length > 0) setShowSuggestions(true);
                  else if (!location && recentSearches.length > 0) setShowSuggestions(true);
                }}
                placeholder="City, area or hotel name"
                className={clsx(
                  'w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400',
                  isCompact ? 'text-xs font-semibold' : 'text-sm font-bold',
                )}
                autoComplete="off"
              />
            </div>
            {loading && <Loader2 size={14} className="animate-spin text-neutral-400" />}
          </div>

          {/* Suggestions dropdown */}
          {(showSuggestions || (showRecent && !location)) && (
            <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-modal border border-neutral-200 z-50 max-h-80 overflow-y-auto animate-slide-down min-w-[360px] w-full">
              {/* Recent searches */}
              {showRecent && !location && (
                <div className="p-2 border-b border-neutral-100">
                  <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider px-2 mb-1">Recent Searches</p>
                  {recentSearches.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleRecentSelect(q)}
                      className="flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg hover:bg-neutral-50 transition-colors"
                    >
                      <Clock size={13} className="text-neutral-300 shrink-0" />
                      <span className="text-sm text-neutral-700">{q}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Autosuggest results */}
              {suggestions.map((item, idx) => (
                <button
                  key={`${item.type}-${item.label}-${idx}`}
                  type="button"
                  onClick={() => handleSelect(item)}
                  className="flex items-start gap-2.5 w-full text-left px-3 py-2.5 hover:bg-primary-50 transition-colors"
                >
                  {ICON_MAP[item.type] ?? <MapPin size={14} className="text-neutral-300 shrink-0 mt-0.5" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-neutral-800 truncate">{item.label}</p>
                    {item.sublabel && (
                      <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>
                    )}
                  </div>
                  {item.count != null && (
                    <span className="text-xs text-neutral-400 shrink-0 mt-0.5">{item.count} stays</span>
                  )}
                </button>
              ))}

              {loading && suggestions.length === 0 && (
                <div className="flex items-center justify-center gap-2 py-4 text-neutral-400">
                  <Loader2 size={14} className="animate-spin" />
                  <span className="text-xs">Searching…</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Check-in */}
        <div className={clsx(isCompact ? 'flex-1' : 'flex-1')}>
          <div className={clsx(
            'field-group',
            isInline && 'bg-white/90 border-white/30',
          )}>
            <span className="field-label">Check-in</span>
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-primary-500 shrink-0" />
              <input
                type="date"
                value={checkIn}
                min={todayStr}
                onChange={(e) => handleCheckInChange(e.target.value)}
                className={clsx(
                  'bg-transparent outline-none w-full text-neutral-900',
                  isCompact ? 'text-xs font-semibold' : 'text-sm font-bold',
                )}
              />
            </div>
          </div>
        </div>

        {/* Check-out */}
        <div className={clsx(isCompact ? 'flex-1' : 'flex-1')}>
          <div className={clsx(
            'field-group',
            isInline && 'bg-white/90 border-white/30',
          )}>
            <span className="field-label">Check-out</span>
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-primary-500 shrink-0" />
              <input
                type="date"
                value={checkOut}
                min={checkIn || todayStr}
                onChange={(e) => setCheckOut(e.target.value)}
                className={clsx(
                  'bg-transparent outline-none w-full text-neutral-900',
                  isCompact ? 'text-xs font-semibold' : 'text-sm font-bold',
                )}
              />
            </div>
          </div>
        </div>

        {/* Guests */}
        {!isCompact && (
          <div className="flex-1">
            <div className={clsx(
              'field-group',
              isInline && 'bg-white/90 border-white/30',
            )}>
              <span className="field-label">Guests</span>
              <div className="flex items-center gap-2">
                <Users size={14} className="text-primary-500 shrink-0" />
                <select
                  value={guests}
                  onChange={(e) => setGuests(Number(e.target.value))}
                  className="bg-transparent outline-none w-full text-sm font-bold text-neutral-900 cursor-pointer"
                >
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>{n} Guest{n > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Search button */}
        <button
          type="submit"
          className={clsx(
            'btn-search shrink-0',
            isHero && 'px-8 py-4 text-base rounded-xl',
            isInline && 'px-6 py-3 rounded-xl',
            isCompact && 'px-4 py-2 rounded-lg text-xs',
          )}
        >
          <Search size={isCompact ? 14 : 18} />
          {!isCompact && <span>Search</span>}
        </button>
      </form>
    </div>
  );
}
