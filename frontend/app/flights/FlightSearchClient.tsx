'use client';

import { useState, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Search, Plane, Clock, ArrowRight, Filter, ChevronDown,
  Loader2, ArrowUpDown, Luggage, RefreshCw, X,
} from 'lucide-react';
import { useFlightSearch } from '@/hooks/useFlights';
import { getAirportSuggestions } from '@/services/flights';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { useDebounce } from '@/hooks/useDebounce';
import { format, addDays } from 'date-fns';
import type { FlightSearchParams, FlightResult, FlightSegment } from '@/types/flights';

function formatDuration(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m > 0 ? `${m}m` : ''}` : `${m}m`;
}

function formatTime(dateStr: string): string {
  try { return format(new Date(dateStr), 'HH:mm'); } catch { return dateStr?.slice(11, 16) || '--:--'; }
}

function FlightCard({ flight, onSelect }: { flight: FlightResult; onSelect: () => void }) {
  const { formatPrice } = useFormatPrice();
  const firstSeg = flight.segments[0];
  const lastSeg = flight.segments[flight.segments.length - 1];

  return (
    <div className="bg-white rounded-xl border border-neutral-100 shadow-sm hover:shadow-md transition-shadow p-4">
      <div className="flex items-center gap-4">
        {/* Airline */}
        <div className="flex items-center gap-3 w-32 shrink-0">
          <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center text-lg">
            {firstSeg?.airline_logo ? (
              <img src={firstSeg.airline_logo} alt={firstSeg.airline} className="w-8 h-8 object-contain" />
            ) : '✈️'}
          </div>
          <div>
            <p className="text-xs font-semibold text-neutral-800">{firstSeg?.airline}</p>
            <p className="text-[10px] text-neutral-400">{firstSeg?.flight_number}</p>
          </div>
        </div>

        {/* Times */}
        <div className="flex items-center gap-3 flex-1">
          <div className="text-center">
            <p className="text-lg font-black text-neutral-900">{formatTime(firstSeg?.departure_time)}</p>
            <p className="text-xs text-neutral-500">{firstSeg?.departure_airport?.code}</p>
          </div>

          <div className="flex-1 text-center">
            <p className="text-[10px] text-neutral-400">{formatDuration(flight.total_duration_minutes)}</p>
            <div className="flex items-center gap-1 justify-center">
              <div className="h-px flex-1 bg-neutral-200" />
              <Plane size={12} className="text-neutral-400" />
              <div className="h-px flex-1 bg-neutral-200" />
            </div>
            <p className="text-[10px] text-neutral-400 font-medium">
              {flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`}
            </p>
          </div>

          <div className="text-center">
            <p className="text-lg font-black text-neutral-900">{formatTime(lastSeg?.arrival_time)}</p>
            <p className="text-xs text-neutral-500">{lastSeg?.arrival_airport?.code}</p>
          </div>
        </div>

        {/* Price + book */}
        <div className="text-right w-32 shrink-0">
          <p className="text-lg font-black text-neutral-900">{formatPrice(flight.price_adult)}</p>
          <p className="text-[10px] text-neutral-400">per adult</p>
          <button
            onClick={onSelect}
            className="mt-2 text-xs font-bold text-white px-4 py-2 rounded-lg transition-colors"
            style={{ background: 'var(--primary)' }}
          >
            Book Now
          </button>
        </div>
      </div>

      {/* Details strip */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-neutral-50 text-[10px] text-neutral-400">
        <span className="flex items-center gap-1"><Luggage size={10} /> {flight.baggage_included || '15kg'}</span>
        {flight.meal_included && <span>🍽️ Meal included</span>}
        <span className={flight.refundable ? 'text-green-600 font-semibold' : 'text-red-500'}>
          {flight.refundable ? 'Refundable' : 'Non-refundable'}
        </span>
        {flight.seats_available > 0 && flight.seats_available <= 5 && (
          <span className="text-orange-600 font-bold">Only {flight.seats_available} seats left!</span>
        )}
      </div>
    </div>
  );
}

export default function FlightSearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { formatPrice } = useFormatPrice();

  const [origin, setOrigin] = useState(searchParams.get('origin') || '');
  const [destination, setDestination] = useState(searchParams.get('destination') || '');
  const [departDate, setDepartDate] = useState(searchParams.get('date') || format(addDays(new Date(), 7), 'yyyy-MM-dd'));
  const [returnDate, setReturnDate] = useState(searchParams.get('return') || '');
  const [tripType, setTripType] = useState<'one_way' | 'round_trip'>(searchParams.get('return') ? 'round_trip' : 'one_way');
  const [cabinClass, setCabinClass] = useState<'economy' | 'premium_economy' | 'business' | 'first'>('economy');
  const [adults, setAdults] = useState(1);
  const [sortBy, setSortBy] = useState<'price' | 'duration' | 'departure'>('price');
  const [maxStops, setMaxStops] = useState<number | undefined>();

  // Autocomplete
  const [originSuggestions, setOriginSuggestions] = useState<{ code: string; name: string; city: string }[]>([]);
  const [destSuggestions, setDestSuggestions] = useState<{ code: string; name: string; city: string }[]>([]);

  const [params, setParams] = useState<FlightSearchParams | null>(
    origin && destination ? {
      origin, destination, departure_date: departDate,
      return_date: returnDate || undefined,
      adults, children: 0, infants: 0,
      cabin_class: cabinClass, trip_type: tripType,
      sort: sortBy, max_stops: maxStops,
    } : null
  );

  const { data, isLoading, error } = useFlightSearch(params);

  const handleSearch = () => {
    if (!origin || !destination || !departDate) return;
    setParams({
      origin, destination, departure_date: departDate,
      return_date: tripType === 'round_trip' ? returnDate || undefined : undefined,
      adults, children: 0, infants: 0,
      cabin_class: cabinClass, trip_type: tripType,
      sort: sortBy, max_stops: maxStops,
    });
  };

  const handleAirportSearch = async (query: string, setter: (v: { code: string; name: string; city: string }[]) => void) => {
    if (query.length < 2) { setter([]); return; }
    try {
      const results = await getAirportSuggestions(query);
      setter(results);
    } catch { setter([]); }
  };

  // Sort results
  const sortedResults = useMemo(() => {
    if (!data?.results) return [];
    const sorted = [...data.results];
    if (sortBy === 'price') sorted.sort((a, b) => a.price_adult - b.price_adult);
    else if (sortBy === 'duration') sorted.sort((a, b) => a.total_duration_minutes - b.total_duration_minutes);
    else if (sortBy === 'departure') sorted.sort((a, b) => (a.segments[0]?.departure_time || '').localeCompare(b.segments[0]?.departure_time || ''));
    if (maxStops != null) return sorted.filter(f => f.stops <= maxStops);
    return sorted;
  }, [data?.results, sortBy, maxStops]);

  return (
    <div className="min-h-screen page-listing-bg">
      {/* Search bar */}
      <div className="bg-gradient-to-r from-[#1a1a2e] to-[#0f3460] py-6">
        <div className="max-w-5xl mx-auto px-4">
          <h1 className="text-white text-xl font-black font-heading mb-4">Search Flights</h1>

          {/* Trip type */}
          <div className="flex items-center gap-3 mb-3">
            {(['one_way', 'round_trip'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTripType(t)}
                className={`text-xs px-3 py-1.5 rounded-full font-semibold ${
                  tripType === t ? 'bg-white text-neutral-800' : 'text-white/70 border border-white/20'
                }`}
              >
                {t === 'one_way' ? 'One Way' : 'Round Trip'}
              </button>
            ))}
          </div>

          <div className="bg-white rounded-2xl p-4 shadow-lg">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_auto_auto] gap-3">
              {/* Origin */}
              <div className="relative">
                <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">From</label>
                <input
                  type="text"
                  value={origin}
                  onChange={(e) => { setOrigin(e.target.value); handleAirportSearch(e.target.value, setOriginSuggestions); }}
                  placeholder="City or airport"
                  className="w-full text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 focus:border-primary-400"
                />
                {originSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 bg-white shadow-lg rounded-lg mt-1 z-50 border border-neutral-200 max-h-48 overflow-auto">
                    {originSuggestions.map((s) => (
                      <button
                        key={s.code}
                        onClick={() => { setOrigin(s.code); setOriginSuggestions([]); }}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-neutral-50"
                      >
                        <span className="font-bold">{s.code}</span> — {s.name}, {s.city}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Swap button */}
              <div className="flex items-end">
                <div className="relative w-full">
                  <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">To</label>
                  <input
                    type="text"
                    value={destination}
                    onChange={(e) => { setDestination(e.target.value); handleAirportSearch(e.target.value, setDestSuggestions); }}
                    placeholder="City or airport"
                    className="w-full text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 focus:border-primary-400"
                  />
                  {destSuggestions.length > 0 && (
                    <div className="absolute top-full left-0 right-0 bg-white shadow-lg rounded-lg mt-1 z-50 border border-neutral-200 max-h-48 overflow-auto">
                      {destSuggestions.map((s) => (
                        <button
                          key={s.code}
                          onClick={() => { setDestination(s.code); setDestSuggestions([]); }}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-neutral-50"
                        >
                          <span className="font-bold">{s.code}</span> — {s.name}, {s.city}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Date */}
              <div>
                <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">Depart</label>
                <input type="date" value={departDate} onChange={(e) => setDepartDate(e.target.value)}
                  className="text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 w-full focus:border-primary-400" />
              </div>

              {tripType === 'round_trip' && (
                <div>
                  <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">Return</label>
                  <input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)}
                    min={departDate}
                    className="text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 w-full focus:border-primary-400" />
                </div>
              )}

              {/* Search */}
              <div className="flex items-end">
                <button
                  onClick={handleSearch}
                  className="btn-primary px-6 py-2.5 text-sm w-full md:w-auto flex items-center justify-center gap-2"
                >
                  <Search size={14} /> Search
                </button>
              </div>
            </div>

            {/* Extra options */}
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-neutral-100 flex-wrap">
              <select value={cabinClass} onChange={(e) => setCabinClass(e.target.value as typeof cabinClass)}
                className="text-xs bg-neutral-50 border border-neutral-200 rounded-lg px-2 py-1.5 outline-none">
                <option value="economy">Economy</option>
                <option value="premium_economy">Premium Economy</option>
                <option value="business">Business</option>
                <option value="first">First Class</option>
              </select>
              <select value={adults} onChange={(e) => setAdults(Number(e.target.value))}
                className="text-xs bg-neutral-50 border border-neutral-200 rounded-lg px-2 py-1.5 outline-none">
                {[1, 2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n} Adult{n > 1 ? 's' : ''}</option>)}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Sort / Filter bar */}
        {data && (
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-neutral-500">{sortedResults.length} flights found</p>
            <div className="flex items-center gap-2">
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="text-xs bg-white border border-neutral-200 rounded-lg px-2 py-1.5 outline-none">
                <option value="price">Cheapest</option>
                <option value="duration">Fastest</option>
                <option value="departure">Earliest</option>
              </select>
              <select value={maxStops ?? ''} onChange={(e) => setMaxStops(e.target.value ? Number(e.target.value) : undefined)}
                className="text-xs bg-white border border-neutral-200 rounded-lg px-2 py-1.5 outline-none">
                <option value="">Any stops</option>
                <option value="0">Non-stop</option>
                <option value="1">Max 1 stop</option>
                <option value="2">Max 2 stops</option>
              </select>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={28} className="animate-spin text-neutral-400" />
            <span className="ml-3 text-neutral-500 text-sm">Searching flights...</span>
          </div>
        )}

        {error && (
          <div className="text-center py-12 text-red-500 text-sm">Failed to search flights. Please try again.</div>
        )}

        {!isLoading && !error && !data && (
          <div className="text-center py-16">
            <Plane size={40} className="mx-auto text-neutral-300 mb-3" />
            <h2 className="text-lg font-bold text-neutral-700 mb-1">Search for flights</h2>
            <p className="text-sm text-neutral-400">Enter your travel details above to find the best deals.</p>
          </div>
        )}

        {sortedResults.length > 0 && (
          <div className="space-y-3">
            {sortedResults.map((flight) => (
              <FlightCard
                key={flight.id}
                flight={flight}
                onSelect={() => router.push(`/flights/${flight.id}`)}
              />
            ))}
          </div>
        )}

        {data && sortedResults.length === 0 && (
          <div className="text-center py-12">
            <Plane size={40} className="mx-auto text-neutral-300 mb-3" />
            <h2 className="text-lg font-bold text-neutral-700 mb-1">No flights found</h2>
            <p className="text-sm text-neutral-400">Try different dates or airports.</p>
          </div>
        )}
      </div>
    </div>
  );
}
