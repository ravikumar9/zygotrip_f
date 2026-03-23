'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  MapPin, Calendar, Users, Search, Building2, Map, Loader2, Clock,
  TrendingUp, Minus, Plus, Landmark, Bus, Car, Package, ArrowLeftRight,
  IndianRupee, Timer,
} from 'lucide-react';
import { clsx } from 'clsx';
import { fetchAutosuggest } from '@/services/apiClient';
import { useDebounce } from '@/hooks/useDebounce';

// ── Types ────────────────────────────────────────────────────────────────────
interface SuggestionItem {
  type: 'city' | 'area' | 'property' | 'landmark' | 'bus_city' | 'cab_city';
  id?: number | string | null;
  label: string;
  sublabel?: string;
  slug?: string | null;
  count?: number | null;
  place_id?: string;
  source?: 'local' | 'google';
}

interface GlobalSearchBarProps {
  variant?: 'hero' | 'inline' | 'compact';
  initialLocation?: string;
  initialCheckin?: string;
  initialCheckout?: string;
  initialGuests?: number;
  initialRooms?: number;
  showTabs?: boolean;
  className?: string;
}

// ── Config ───────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'hotels',   label: 'Hotels',   icon: Building2 },
  { id: 'buses',    label: 'Buses',    icon: Bus },
  { id: 'cabs',     label: 'Cabs',     icon: Car },
  { id: 'packages', label: 'Packages', icon: Package },
] as const;

type TabId = (typeof TABS)[number]['id'];
type ActiveField = 'hotel-location' | 'bus-from' | 'bus-to' | 'cab-from' | 'cab-to' | 'pkg-destination' | null;

const DURATION_OPTIONS = [
  { value: '',     label: 'Any Duration' },
  { value: '1-3',  label: '1–3 Days' },
  { value: '4-6',  label: '4–6 Days' },
  { value: '7-10', label: '7–10 Days' },
  { value: '10-30', label: '10+ Days' },
];

const BUDGET_OPTIONS = [
  { value: '',             label: 'Any Budget' },
  { value: '0-10000',     label: 'Under ₹10,000' },
  { value: '10000-25000', label: '₹10k – ₹25k' },
  { value: '25000-50000', label: '₹25k – ₹50k' },
  { value: '50000-500000', label: '₹50,000+' },
];

// ── Per-vertical icon maps ───────────────────────────────────────────────────
const HOTEL_ICON_MAP: Record<string, React.ReactNode> = {
  city:     <Map size={14} className="text-primary-500 shrink-0" />,
  area:     <MapPin size={14} className="text-accent-500 shrink-0" />,
  property: <Building2 size={14} className="text-neutral-400 shrink-0" />,
  landmark: <Landmark size={14} className="text-amber-500 shrink-0" />,
  bus_city: <Bus size={14} className="text-blue-500 shrink-0" />,
  cab_city: <Car size={14} className="text-yellow-600 shrink-0" />,
};

// ── Per-vertical popular suggestions (completely independent data) ────────────
const POPULAR_HOTEL_DESTINATIONS: SuggestionItem[] = [
  { type: 'city', label: 'Goa',       sublabel: 'Goa, India' },
  { type: 'city', label: 'Jaipur',    sublabel: 'Jaipur, Rajasthan' },
  { type: 'city', label: 'Manali',    sublabel: 'Manali, Himachal Pradesh' },
  { type: 'city', label: 'Mumbai',    sublabel: 'Mumbai, Maharashtra' },
  { type: 'city', label: 'Bangalore', sublabel: 'Bangalore, Karnataka' },
  { type: 'city', label: 'Udaipur',   sublabel: 'Udaipur, Rajasthan' },
];

const POPULAR_BUS_CITIES: SuggestionItem[] = [
  { type: 'city', label: 'Delhi',      sublabel: 'Delhi, India' },
  { type: 'city', label: 'Mumbai',     sublabel: 'Mumbai, Maharashtra' },
  { type: 'city', label: 'Bangalore',  sublabel: 'Bangalore, Karnataka' },
  { type: 'city', label: 'Hyderabad',  sublabel: 'Hyderabad, Telangana' },
  { type: 'city', label: 'Chennai',    sublabel: 'Chennai, Tamil Nadu' },
  { type: 'city', label: 'Pune',       sublabel: 'Pune, Maharashtra' },
];

const POPULAR_CAB_CITIES: SuggestionItem[] = [
  { type: 'city', label: 'Delhi',      sublabel: 'Delhi NCR' },
  { type: 'city', label: 'Mumbai',     sublabel: 'Mumbai, Maharashtra' },
  { type: 'city', label: 'Bangalore',  sublabel: 'Bangalore, Karnataka' },
  { type: 'city', label: 'Jaipur',     sublabel: 'Jaipur, Rajasthan' },
  { type: 'city', label: 'Goa',        sublabel: 'Goa, India' },
  { type: 'city', label: 'Hyderabad',  sublabel: 'Hyderabad, Telangana' },
];

const POPULAR_PKG_DESTINATIONS: SuggestionItem[] = [
  { type: 'city', label: 'Goa',        sublabel: 'Beaches & Nightlife' },
  { type: 'city', label: 'Manali',     sublabel: 'Mountains & Adventure' },
  { type: 'city', label: 'Kerala',     sublabel: 'Backwaters & Ayurveda' },
  { type: 'city', label: 'Ladakh',     sublabel: 'Scenic & Adventure' },
  { type: 'city', label: 'Rajasthan',  sublabel: 'Heritage & Culture' },
  { type: 'city', label: 'Andaman',    sublabel: 'Islands & Diving' },
];

// ── Per-vertical recent searches (separate localStorage keys) ────────────────
const RECENT_KEYS: Record<TabId, string> = {
  hotels:   'zygo_recent_hotels',
  buses:    'zygo_recent_buses',
  cabs:     'zygo_recent_cabs',
  packages: 'zygo_recent_packages',
};
const MAX_RECENT = 5;

function getRecentSearches(tab: TabId): string[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEYS[tab]) || '[]').slice(0, MAX_RECENT);
  } catch { return []; }
}

function saveRecentSearch(tab: TabId, query: string) {
  if (typeof window === 'undefined' || !query.trim()) return;
  try {
    const existing = getRecentSearches(tab).filter(s => s !== query);
    localStorage.setItem(RECENT_KEYS[tab], JSON.stringify([query, ...existing].slice(0, MAX_RECENT)));
  } catch {}
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Determine which vertical a field belongs to */
function fieldToTab(field: ActiveField): TabId {
  if (!field) return 'hotels';
  if (field.startsWith('hotel')) return 'hotels';
  if (field.startsWith('bus'))   return 'buses';
  if (field.startsWith('cab'))   return 'cabs';
  return 'packages';
}

/** Get the right popular list per vertical */
function getPopularForTab(tab: TabId): SuggestionItem[] {
  switch (tab) {
    case 'hotels':   return POPULAR_HOTEL_DESTINATIONS;
    case 'buses':    return POPULAR_BUS_CITIES;
    case 'cabs':     return POPULAR_CAB_CITIES;
    case 'packages': return POPULAR_PKG_DESTINATIONS;
  }
}

/** Filter API results per vertical — hotels get everything, others get relevant types */
function filterSuggestionsForTab(items: SuggestionItem[], tab: TabId): SuggestionItem[] {
  if (tab === 'hotels') return items; // all types allowed
  if (tab === 'buses') return items.filter(i => ['city', 'bus_city'].includes(i.type));
  if (tab === 'cabs') return items.filter(i => ['city', 'cab_city'].includes(i.type));
  // packages — cities + areas
  return items.filter(i => ['city', 'area'].includes(i.type));
}

/** Label for the popular heading per vertical */
function getPopularLabel(tab: TabId): string {
  switch (tab) {
    case 'hotels':   return 'Popular Destinations';
    case 'buses':    return 'Popular Bus Cities';
    case 'cabs':     return 'Popular Cab Cities';
    case 'packages': return 'Popular Destinations';
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
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

  const todayStr = today.toISOString().split('T')[0];
  const tomorrowStr = tomorrow.toISOString().split('T')[0];

  const [activeTab, setActiveTab] = useState<TabId>('hotels');

  // ── Hotel state ── (check-in = today, check-out = tomorrow)
  const [location, setLocation] = useState(initialLocation);
  const [checkIn, setCheckIn] = useState(initialCheckin || todayStr);
  const [checkOut, setCheckOut] = useState(initialCheckout || tomorrowStr);
  const [guests, setGuests] = useState(initialGuests);
  const [rooms, setRooms] = useState(initialRooms);
  const [guestDropdownOpen, setGuestDropdownOpen] = useState(false);

  // ── Bus state ──
  const [busFrom, setBusFrom] = useState('');
  const [busTo, setBusTo] = useState('');
  const [busDate, setBusDate] = useState(todayStr);

  // ── Cab state (from/to) ──
  const [cabFrom, setCabFrom] = useState('');
  const [cabTo, setCabTo] = useState('');
  const [cabDate, setCabDate] = useState(todayStr);

  // ── Package state ──
  const [pkgDestination, setPkgDestination] = useState('');
  const [pkgDuration, setPkgDuration] = useState('');
  const [pkgBudget, setPkgBudget] = useState('');

  // ── Autosuggest state (isolated per active field) ──
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  // ── Field value helpers ──
  const getFieldValue = useCallback((field: ActiveField): string => {
    switch (field) {
      case 'hotel-location': return location;
      case 'bus-from': return busFrom;
      case 'bus-to': return busTo;
      case 'cab-from': return cabFrom;
      case 'cab-to': return cabTo;
      case 'pkg-destination': return pkgDestination;
      default: return '';
    }
  }, [location, busFrom, busTo, cabFrom, cabTo, pkgDestination]);

  const setFieldValue = useCallback((field: ActiveField, value: string) => {
    switch (field) {
      case 'hotel-location': setLocation(value); break;
      case 'bus-from': setBusFrom(value); break;
      case 'bus-to': setBusTo(value); break;
      case 'cab-from': setCabFrom(value); break;
      case 'cab-to': setCabTo(value); break;
      case 'pkg-destination': setPkgDestination(value); break;
    }
  }, []);

  const currentQuery = activeField ? getFieldValue(activeField) : '';
  const debouncedQuery = useDebounce(currentQuery, 250);

  // Load recent searches when tab changes
  useEffect(() => {
    setRecentSearches(getRecentSearches(activeTab));
  }, [activeTab]);

  // Clear suggestions & dropdown when switching tabs
  useEffect(() => {
    setSuggestions([]);
    setShowSuggestions(false);
    setActiveField(null);
    setHighlightedIndex(-1);
  }, [activeTab]);

  // Fetch suggestions — filter per vertical
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2 || !activeField) {
      setSuggestions([]);
      return;
    }
    const tab = fieldToTab(activeField);
    setLoading(true);
    fetchAutosuggest(debouncedQuery, 12)
      .then((res) => {
        const filtered = filterSuggestionsForTab(res as SuggestionItem[], tab);
        setSuggestions(filtered);
        if (filtered.length > 0) setShowSuggestions(true);
      })
      .finally(() => setLoading(false));
  }, [debouncedQuery, activeField]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
        setActiveField(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Navigation helper — builds correct URL per tab ──
  const navigateToSearch = useCallback((selectedValue: string, field: ActiveField) => {
    const params = new URLSearchParams();
    const tab = fieldToTab(field);

    if (tab === 'hotels') {
      const loc = field === 'hotel-location' ? selectedValue : location;
      if (loc) { params.set('location', loc); saveRecentSearch('hotels', loc); }
      if (checkIn) params.set('checkin', checkIn);
      if (checkOut) params.set('checkout', checkOut);
      params.set('adults', String(guests));
      if (rooms > 1) params.set('rooms', String(rooms));
      router.push(`/hotels?${params.toString()}`);
    } else if (tab === 'buses') {
      const from = field === 'bus-from' ? selectedValue : busFrom;
      const to = field === 'bus-to' ? selectedValue : busTo;
      if (from) { params.set('from', from); saveRecentSearch('buses', from); }
      if (to) { params.set('to', to); saveRecentSearch('buses', to); }
      if (busDate) params.set('date', busDate);
      router.push(`/buses?${params.toString()}`);
    } else if (tab === 'cabs') {
      const from = field === 'cab-from' ? selectedValue : cabFrom;
      const to = field === 'cab-to' ? selectedValue : cabTo;
      if (from) { params.set('from', from); saveRecentSearch('cabs', from); }
      if (to) { params.set('to', to); saveRecentSearch('cabs', to); }
      if (cabDate) params.set('date', cabDate);
      router.push(`/cabs?${params.toString()}`);
    } else {
      const dest = field === 'pkg-destination' ? selectedValue : pkgDestination;
      if (dest) { params.set('destination', dest); saveRecentSearch('packages', dest); }
      if (pkgDuration) params.set('duration', pkgDuration);
      if (pkgBudget) params.set('budget', pkgBudget);
      router.push(`/packages?${params.toString()}`);
    }
  }, [location, checkIn, checkOut, guests, rooms, busFrom, busTo, busDate, cabFrom, cabTo, cabDate, pkgDestination, pkgDuration, pkgBudget, router]);

  // ── Selection handlers ──
  const handleSelect = useCallback((item: SuggestionItem) => {
    // Only hotels can navigate to property detail
    if (activeTab === 'hotels' && item.type === 'property' && item.slug) {
      router.push(`/hotels/${item.slug}`);
      setShowSuggestions(false);
      setActiveField(null);
      return;
    }
    const field = activeField;
    if (field) {
      setFieldValue(field, item.label);
      saveRecentSearch(activeTab, item.label);
    }
    setShowSuggestions(false);
    setHighlightedIndex(-1);
    if (field) navigateToSearch(item.label, field);
    setActiveField(null);
  }, [activeField, activeTab, setFieldValue, router, navigateToSearch]);

  const handleRecentSelect = useCallback((query: string) => {
    const field = activeField;
    if (field) setFieldValue(field, query);
    setShowSuggestions(false);
    setHighlightedIndex(-1);
    if (field) navigateToSearch(query, field);
    setActiveField(null);
  }, [activeField, setFieldValue, navigateToSearch]);

  // ── Keyboard navigation ──
  const getSelectableItems = useCallback((): SuggestionItem[] => {
    if (suggestions.length > 0) return suggestions;
    const q = activeField ? getFieldValue(activeField) : '';
    if (!q && recentSearches.length > 0) {
      return recentSearches.map((r) => ({ type: 'city' as const, label: r }));
    }
    if (!q) return getPopularForTab(activeTab);
    return [];
  }, [suggestions, activeField, getFieldValue, recentSearches, activeTab]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const items = getSelectableItems();
    if (!items.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < items.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : items.length - 1));
    } else if (e.key === 'Enter' && highlightedIndex >= 0 && highlightedIndex < items.length) {
      e.preventDefault();
      handleSelect(items[highlightedIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setHighlightedIndex(-1);
      setActiveField(null);
    }
  }, [getSelectableItems, highlightedIndex, handleSelect]);

  useEffect(() => { setHighlightedIndex(-1); }, [suggestions]);

  // ── Form submit (Search button) ──
  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    const params = new URLSearchParams();
    if (activeTab === 'hotels') {
      if (location) { params.set('location', location); saveRecentSearch('hotels', location); }
      if (checkIn) params.set('checkin', checkIn);
      if (checkOut) params.set('checkout', checkOut);
      params.set('adults', String(guests));
      if (rooms > 1) params.set('rooms', String(rooms));
      router.push(`/hotels?${params.toString()}`);
    } else if (activeTab === 'buses') {
      if (busFrom) { params.set('from', busFrom); saveRecentSearch('buses', busFrom); }
      if (busTo) { params.set('to', busTo); saveRecentSearch('buses', busTo); }
      if (busDate) params.set('date', busDate);
      router.push(`/buses?${params.toString()}`);
    } else if (activeTab === 'cabs') {
      if (cabFrom) { params.set('from', cabFrom); saveRecentSearch('cabs', cabFrom); }
      if (cabTo) { params.set('to', cabTo); saveRecentSearch('cabs', cabTo); }
      if (cabDate) params.set('date', cabDate);
      router.push(`/cabs?${params.toString()}`);
    } else {
      if (pkgDestination) { params.set('destination', pkgDestination); saveRecentSearch('packages', pkgDestination); }
      if (pkgDuration) params.set('duration', pkgDuration);
      if (pkgBudget) params.set('budget', pkgBudget);
      router.push(`/packages?${params.toString()}`);
    }
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

  // ═══════════════════════════════════════════════════════════════════════════
  // DROPDOWN RENDERERS — completely separate per vertical
  // ═══════════════════════════════════════════════════════════════════════════

  /** Hotels dropdown — shows cities, areas, properties, landmarks with hotel counts */
  const renderHotelDropdown = (field: ActiveField) => {
    if (activeField !== field || !showSuggestions) return null;
    const q = getFieldValue(field);
    const showRecent = !q && recentSearches.length > 0;
    const showPopular = !q && recentSearches.length === 0;
    if (!suggestions.length && !showRecent && !showPopular && !loading) return null;

    return (
      <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-modal border border-neutral-200 z-[9999] max-h-96 overflow-y-auto animate-slide-down w-full min-w-0" role="listbox">
        {showRecent && (
          <div className="p-2 border-b border-neutral-100">
            <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider px-2 mb-1">Recent Hotel Searches</p>
            {recentSearches.map((r, idx) => (
              <button key={r} id={`sg-${idx}`} type="button" onClick={() => handleRecentSelect(r)}
                className={clsx('flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg transition-colors', highlightedIndex === idx ? 'bg-primary-50 text-primary-700' : 'hover:bg-page')}
                role="option" aria-selected={highlightedIndex === idx}>
                <Clock size={13} className="text-neutral-300 shrink-0" />
                <span className="text-sm text-neutral-700">{r}</span>
              </button>
            ))}
          </div>
        )}
        {showPopular && (
          <div className="p-2">
            <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider px-2 mb-1 flex items-center gap-1">
              <TrendingUp size={11} /> Popular Destinations
            </p>
            {POPULAR_HOTEL_DESTINATIONS.map((item, idx) => (
              <button key={item.label} id={`sg-${idx}`} type="button" onClick={() => handleSelect(item)}
                className={clsx('flex items-start gap-2.5 w-full text-left px-2 py-2 rounded-lg transition-colors', highlightedIndex === idx ? 'bg-primary-50' : 'hover:bg-primary-50')}
                role="option" aria-selected={highlightedIndex === idx}>
                {HOTEL_ICON_MAP[item.type]}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-neutral-800">{item.label}</p>
                  <p className="text-xs text-neutral-400">{item.sublabel}</p>
                </div>
              </button>
            ))}
          </div>
        )}
        {suggestions.map((item, idx) => (
          <button key={`${item.type}-${item.label}-${idx}`} id={`sg-${idx}`} type="button" onClick={() => handleSelect(item)}
            className={clsx('flex items-center gap-2.5 w-full text-left px-3 py-2.5 transition-colors', highlightedIndex === idx ? 'bg-primary-50' : 'hover:bg-primary-50')}
            role="option" aria-selected={highlightedIndex === idx}>
            <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
              item.type === 'city' ? 'bg-primary-50' : item.type === 'area' ? 'bg-accent-50' : item.type === 'landmark' ? 'bg-amber-50' : item.type === 'bus_city' ? 'bg-blue-50' : item.type === 'cab_city' ? 'bg-yellow-50' : 'bg-neutral-100')}>
              {HOTEL_ICON_MAP[item.type] ?? <MapPin size={14} className="text-neutral-300" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-neutral-800 truncate">{item.label}</p>
              <div className="flex items-center gap-1.5">
                {item.sublabel && <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>}
                {item.type !== 'property' && (
                  <span className="text-[10px] font-bold text-neutral-400 bg-neutral-100 px-1.5 py-0.5 rounded uppercase shrink-0">{item.type}</span>
                )}
              </div>
            </div>
            {item.count != null && item.count > 0 && (
              <span className="text-[10px] font-bold text-primary-600 bg-primary-50 px-2 py-1 rounded-lg shrink-0 whitespace-nowrap">
                {item.count} {item.type === 'bus_city' ? (item.count === 1 ? 'route' : 'routes') : item.type === 'cab_city' ? (item.count === 1 ? 'cab' : 'cabs') : (item.count === 1 ? 'hotel' : 'hotels')}
              </span>
            )}
          </button>
        ))}
        {loading && suggestions.length === 0 && (
          <div className="flex items-center justify-center gap-2 py-4 text-neutral-400">
            <Loader2 size={14} className="animate-spin" /><span className="text-xs">Searching…</span>
          </div>
        )}
      </div>
    );
  };

  /** City-only dropdown — used for Buses, Cabs, Packages (no area/property/landmarks, no hotel counts) */
  const renderCityDropdown = (field: ActiveField, verticalIcon: React.ReactNode, verticalColor: string) => {
    if (activeField !== field || !showSuggestions) return null;
    const tab = fieldToTab(field);
    const q = getFieldValue(field);
    const showRecent = !q && recentSearches.length > 0;
    const showPopular = !q && recentSearches.length === 0;
    if (!suggestions.length && !showRecent && !showPopular && !loading) return null;

    const popular = getPopularForTab(tab);
    const label = getPopularLabel(tab);
    const recentLabel = tab === 'buses' ? 'Recent Bus Searches' : tab === 'cabs' ? 'Recent Cab Searches' : 'Recent Searches';

    return (
      <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-modal border border-neutral-200 z-[9999] max-h-80 overflow-y-auto animate-slide-down w-full min-w-0" role="listbox">
        {showRecent && (
          <div className="p-2 border-b border-neutral-100">
            <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider px-2 mb-1">{recentLabel}</p>
            {recentSearches.map((r, idx) => (
              <button key={r} id={`sg-${idx}`} type="button" onClick={() => handleRecentSelect(r)}
                className={clsx('flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg transition-colors', highlightedIndex === idx ? 'bg-primary-50 text-primary-700' : 'hover:bg-page')}
                role="option" aria-selected={highlightedIndex === idx}>
                <Clock size={13} className="text-neutral-300 shrink-0" />
                <span className="text-sm text-neutral-700">{r}</span>
              </button>
            ))}
          </div>
        )}
        {showPopular && (
          <div className="p-2">
            <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider px-2 mb-1 flex items-center gap-1">
              <TrendingUp size={11} /> {label}
            </p>
            {popular.map((item, idx) => (
              <button key={item.label} id={`sg-${idx}`} type="button" onClick={() => handleSelect(item)}
                className={clsx('flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg transition-colors', highlightedIndex === idx ? 'bg-primary-50' : 'hover:bg-primary-50')}
                role="option" aria-selected={highlightedIndex === idx}>
                <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center shrink-0', verticalColor)}>
                  {verticalIcon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-neutral-800">{item.label}</p>
                  <p className="text-xs text-neutral-400">{item.sublabel}</p>
                </div>
              </button>
            ))}
          </div>
        )}
        {suggestions.map((item, idx) => (
          <button key={`city-${item.label}-${idx}`} id={`sg-${idx}`} type="button" onClick={() => handleSelect(item)}
            className={clsx('flex items-center gap-2.5 w-full text-left px-3 py-2.5 transition-colors', highlightedIndex === idx ? 'bg-primary-50' : 'hover:bg-primary-50')}
            role="option" aria-selected={highlightedIndex === idx}>
            <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
              item.type === 'bus_city' ? 'bg-blue-50' : item.type === 'cab_city' ? 'bg-yellow-50' : verticalColor)}>
              {HOTEL_ICON_MAP[item.type] ?? verticalIcon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-neutral-800 truncate">{item.label}</p>
              {item.sublabel && <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>}
            </div>
            {item.count != null && item.count > 0 && (
              <span className="text-[10px] font-bold text-primary-600 bg-primary-50 px-2 py-1 rounded-lg shrink-0">
                {item.count} {item.type === 'bus_city' ? 'routes' : item.type === 'cab_city' ? 'cabs' : 'options'}
              </span>
            )}
          </button>
        ))}
        {loading && suggestions.length === 0 && (
          <div className="flex items-center justify-center gap-2 py-4 text-neutral-400">
            <Loader2 size={14} className="animate-spin" /><span className="text-xs">Searching…</span>
          </div>
        )}
      </div>
    );
  };

  // ── Variant styles ──
  const isHero = variant === 'hero';
  const isInline = variant === 'inline';
  const isCompact = variant === 'compact';

  return (
    <div className={clsx('w-full', className)} ref={containerRef}>
      {/* ── Tab row — aligned with search bar ── */}
      {showTabs && (
        <div className="max-w-5xl mx-auto mb-3">
          <div className="flex items-center gap-0.5 bg-neutral-100/80 rounded-xl p-1 w-full sm:w-fit overflow-x-auto scrollbar-none">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 sm:px-5 py-2 sm:py-2.5 rounded-lg font-bold text-xs sm:text-sm cursor-pointer transition-all duration-200 whitespace-nowrap',
                    isActive
                      ? 'bg-white text-primary-600 shadow-sm'
                      : 'text-neutral-500 hover:text-neutral-700 hover:bg-white',
                  )}
                >
                  <Icon size={16} className={isActive ? 'text-primary-500' : 'text-neutral-400'} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <form
        onSubmit={handleSearch}
        className={clsx(
          'flex gap-1 w-full',
          isHero && 'hero-search-bar p-2 sm:p-3 flex-col md:flex-row max-w-5xl mx-auto',
          isInline && 'bg-white backdrop-blur-sm rounded-2xl p-2 flex-col sm:flex-row items-stretch',
          isCompact && 'bg-white rounded-xl shadow-sm border border-neutral-200 p-1.5 flex-row items-stretch',
        )}
      >
        {/* ═══════════════════════════════════════════════════════
            HOTELS TAB
           ═══════════════════════════════════════════════════════ */}
        {activeTab === 'hotels' && (
          <>
            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[2]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-primary-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">{isCompact ? 'Where' : 'Destination'}</span>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => { setLocation(e.target.value); setActiveField('hotel-location'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('hotel-location'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="City, area or hotel name"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off"
                    role="combobox"
                    aria-expanded={showSuggestions && activeField === 'hotel-location'}
                    aria-haspopup="listbox"
                    aria-activedescendant={highlightedIndex >= 0 ? `sg-${highlightedIndex}` : undefined}
                  />
                </div>
                {loading && activeField === 'hotel-location' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderHotelDropdown('hotel-location')}
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Check-in</span>
                <div className="flex items-center gap-2">
                  <Calendar size={14} className="text-primary-500 shrink-0" />
                  <input type="date" value={checkIn} min={todayStr} onChange={(e) => handleCheckInChange(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')} />
                </div>
              </div>
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Check-out</span>
                <div className="flex items-center gap-2">
                  <Calendar size={14} className="text-primary-500 shrink-0" />
                  <input type="date" value={checkOut} min={checkIn || todayStr} onChange={(e) => setCheckOut(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')} />
                </div>
              </div>
            </div>

            {!isCompact && (
              <div className="flex-1 relative">
                <button type="button" onClick={() => setGuestDropdownOpen(!guestDropdownOpen)}
                  className={clsx('field-group w-full text-left', isInline && 'bg-white border-white/30')}>
                  <span className="field-label">Guests & Rooms</span>
                  <div className="flex items-center gap-2">
                    <Users size={14} className="text-primary-500 shrink-0" />
                    <span className="text-sm font-bold text-neutral-900">{guests} Guest{guests > 1 ? 's' : ''}, {rooms} Room{rooms > 1 ? 's' : ''}</span>
                  </div>
                </button>
                {guestDropdownOpen && (
                  <div className="absolute top-full right-0 mt-1 bg-white rounded-xl shadow-modal border border-neutral-200 z-[9999] p-4 w-72 max-w-[calc(100vw-2rem)] animate-slide-down">
                    <div className="flex items-center justify-between py-2">
                      <div><p className="text-sm font-bold text-neutral-800">Adults</p><p className="text-2xs text-neutral-400">Age 13+</p></div>
                      <div className="flex items-center gap-3">
                        <button type="button" onClick={() => setGuests(Math.max(1, guests - 1))} disabled={guests <= 1}
                          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center text-neutral-600 hover:border-primary-300 hover:text-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><Minus size={14} /></button>
                        <span className="w-6 text-center font-bold text-sm">{guests}</span>
                        <button type="button" onClick={() => setGuests(Math.min(12, guests + 1))} disabled={guests >= 12}
                          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center text-neutral-600 hover:border-primary-300 hover:text-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><Plus size={14} /></button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between py-2 border-t border-neutral-100">
                      <div><p className="text-sm font-bold text-neutral-800">Rooms</p><p className="text-2xs text-neutral-400">Max 8 rooms</p></div>
                      <div className="flex items-center gap-3">
                        <button type="button" onClick={() => setRooms(Math.max(1, rooms - 1))} disabled={rooms <= 1}
                          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center text-neutral-600 hover:border-primary-300 hover:text-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><Minus size={14} /></button>
                        <span className="w-6 text-center font-bold text-sm">{rooms}</span>
                        <button type="button" onClick={() => setRooms(Math.min(8, rooms + 1))} disabled={rooms >= 8}
                          className="w-8 h-8 rounded-full border border-neutral-300 flex items-center justify-center text-neutral-600 hover:border-primary-300 hover:text-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"><Plus size={14} /></button>
                      </div>
                    </div>
                    <button type="button" onClick={() => setGuestDropdownOpen(false)}
                      className="w-full mt-3 py-2 bg-primary-500 text-white text-xs font-bold rounded-lg hover:bg-primary-600 transition-colors">Done</button>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ═══════════════════════════════════════════════════════
            BUSES TAB — from + to + date (cities only)
           ═══════════════════════════════════════════════════════ */}
        {activeTab === 'buses' && (
          <>
            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[1.5]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-green-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">From</span>
                  <input type="text" value={busFrom}
                    onChange={(e) => { setBusFrom(e.target.value); setActiveField('bus-from'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('bus-from'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="Departure city"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off" />
                </div>
                {loading && activeField === 'bus-from' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderCityDropdown('bus-from', <Bus size={14} className="text-green-500" />, 'bg-green-50')}
            </div>

            {!isCompact && (
              <button type="button" onClick={() => { const t = busFrom; setBusFrom(busTo); setBusTo(t); }}
                className="self-center w-9 h-9 rounded-full border-2 border-neutral-200 bg-white flex items-center justify-center text-neutral-400 hover:text-primary-500 hover:border-primary-300 transition-colors -mx-1 z-10 shrink-0"
                title="Swap cities">
                <ArrowLeftRight size={14} />
              </button>
            )}

            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[1.5]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-red-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">To</span>
                  <input type="text" value={busTo}
                    onChange={(e) => { setBusTo(e.target.value); setActiveField('bus-to'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('bus-to'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="Arrival city"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off" />
                </div>
                {loading && activeField === 'bus-to' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderCityDropdown('bus-to', <Bus size={14} className="text-red-500" />, 'bg-red-50')}
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Travel Date</span>
                <div className="flex items-center gap-2">
                  <Calendar size={14} className="text-primary-500 shrink-0" />
                  <input type="date" value={busDate} min={todayStr} onChange={(e) => setBusDate(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')} />
                </div>
              </div>
            </div>
          </>
        )}

        {/* ═══════════════════════════════════════════════════════
            CABS TAB — from + to + date (cities only)
           ═══════════════════════════════════════════════════════ */}
        {activeTab === 'cabs' && (
          <>
            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[1.5]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-green-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">From</span>
                  <input type="text" value={cabFrom}
                    onChange={(e) => { setCabFrom(e.target.value); setActiveField('cab-from'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('cab-from'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="Pickup city"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off" />
                </div>
                {loading && activeField === 'cab-from' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderCityDropdown('cab-from', <Car size={14} className="text-green-500" />, 'bg-green-50')}
            </div>

            {!isCompact && (
              <button type="button" onClick={() => { const t = cabFrom; setCabFrom(cabTo); setCabTo(t); }}
                className="self-center w-9 h-9 rounded-full border-2 border-neutral-200 bg-white flex items-center justify-center text-neutral-400 hover:text-primary-500 hover:border-primary-300 transition-colors -mx-1 z-10 shrink-0"
                title="Swap cities">
                <ArrowLeftRight size={14} />
              </button>
            )}

            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[1.5]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-red-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">To</span>
                  <input type="text" value={cabTo}
                    onChange={(e) => { setCabTo(e.target.value); setActiveField('cab-to'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('cab-to'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="Drop-off city"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off" />
                </div>
                {loading && activeField === 'cab-to' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderCityDropdown('cab-to', <Car size={14} className="text-red-500" />, 'bg-red-50')}
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Pickup Date</span>
                <div className="flex items-center gap-2">
                  <Calendar size={14} className="text-primary-500 shrink-0" />
                  <input type="date" value={cabDate} min={todayStr} onChange={(e) => setCabDate(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')} />
                </div>
              </div>
            </div>
          </>
        )}

        {/* ═══════════════════════════════════════════════════════
            PACKAGES TAB — destination + duration + budget (cities only)
           ═══════════════════════════════════════════════════════ */}
        {activeTab === 'packages' && (
          <>
            <div className={clsx('relative', isCompact ? 'flex-1' : 'flex-[2]')}>
              <div className={clsx('field-group flex items-center gap-2', isInline && 'bg-white border-white/30')}>
                <MapPin size={16} className="text-primary-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="field-label">Destination</span>
                  <input type="text" value={pkgDestination}
                    onChange={(e) => { setPkgDestination(e.target.value); setActiveField('pkg-destination'); setShowSuggestions(true); }}
                    onFocus={() => { setActiveField('pkg-destination'); setShowSuggestions(true); }}
                    onKeyDown={handleKeyDown}
                    placeholder="Where do you want to go?"
                    className={clsx('w-full bg-transparent outline-none text-neutral-900 placeholder:text-neutral-400', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}
                    autoComplete="off" />
                </div>
                {loading && activeField === 'pkg-destination' && <Loader2 size={14} className="animate-spin text-neutral-400" />}
              </div>
              {renderCityDropdown('pkg-destination', <Package size={14} className="text-primary-500" />, 'bg-primary-50')}
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Duration</span>
                <div className="flex items-center gap-2">
                  <Timer size={14} className="text-primary-500 shrink-0" />
                  <select value={pkgDuration} onChange={(e) => setPkgDuration(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900 cursor-pointer', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}>
                    {DURATION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
              </div>
            </div>

            <div className="flex-1">
              <div className={clsx('field-group', isInline && 'bg-white border-white/30')}>
                <span className="field-label">Budget</span>
                <div className="flex items-center gap-2">
                  <IndianRupee size={14} className="text-primary-500 shrink-0" />
                  <select value={pkgBudget} onChange={(e) => setPkgBudget(e.target.value)}
                    className={clsx('bg-transparent outline-none w-full text-neutral-900 cursor-pointer', isCompact ? 'text-xs font-semibold' : 'text-sm font-bold')}>
                    {BUDGET_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── Search button ── */}
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
