'use client';

import { useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Search, MapPin, Clock, Star, Users, Calendar,
  Loader2, Check, Filter, ChevronDown, Compass,
} from 'lucide-react';
import { useActivitySearch } from '@/hooks/useActivities';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { format, addDays } from 'date-fns';
import type { ActivitySearchParams, Activity } from '@/types/activities';

function ActivityCard({ activity, onClick }: { activity: Activity; onClick: () => void }) {
  const { formatPrice } = useFormatPrice();

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl border border-neutral-100 shadow-sm hover:shadow-md transition-all cursor-pointer overflow-hidden group"
    >
      <div className="relative h-48 bg-neutral-100 overflow-hidden">
        {activity.primary_image ? (
          <img src={activity.primary_image} alt={activity.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl">🎯</div>
        )}
        <span className="absolute top-3 left-3 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-white/90 backdrop-blur-sm text-neutral-700">
          {activity.category}
        </span>
        {activity.is_free_cancellation && (
          <span className="absolute top-3 right-3 text-[10px] font-bold px-2 py-1 rounded-full bg-green-500 text-white">
            Free Cancel
          </span>
        )}
      </div>
      <div className="p-4">
        <div className="flex items-center gap-1.5 text-xs text-neutral-400 mb-1">
          <MapPin size={10} /> {activity.city}
          {activity.duration_display && (
            <><span className="mx-1">·</span><Clock size={10} /> {activity.duration_display}</>
          )}
        </div>
        <h3 className="font-bold text-neutral-900 text-sm leading-tight mb-2 line-clamp-2">{activity.name}</h3>
        <p className="text-xs text-neutral-500 line-clamp-2 mb-3">{activity.short_description}</p>

        {activity.highlights && activity.highlights.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap mb-3">
            {activity.highlights.slice(0, 3).map((h, i) => (
              <span key={i} className="text-[10px] bg-neutral-50 text-neutral-600 px-2 py-0.5 rounded-full border border-neutral-100">
                {h}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-neutral-50">
          <div className="flex items-center gap-2">
            {activity.rating > 0 && (
              <div className="flex items-center gap-1 text-xs">
                <Star size={10} fill="#f59e0b" stroke="none" />
                <span className="font-semibold text-neutral-700">{activity.rating.toFixed(1)}</span>
                {activity.review_count > 0 && <span className="text-neutral-400">({activity.review_count})</span>}
              </div>
            )}
            {activity.is_instant_confirm && (
              <span className="flex items-center gap-0.5 text-[10px] text-green-600 font-semibold">
                <Check size={8} /> Instant
              </span>
            )}
          </div>
          <div className="text-right">
            <p className="text-lg font-black text-neutral-900">{formatPrice(activity.price_adult)}</p>
            <p className="text-[10px] text-neutral-400">per person</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ActivitySearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { formatPrice } = useFormatPrice();

  const [city, setCity] = useState(searchParams.get('city') || '');
  const [category, setCategory] = useState(searchParams.get('category') || '');
  const [date, setDate] = useState(searchParams.get('date') || '');
  const [sortBy, setSortBy] = useState(searchParams.get('sort') || 'popular');

  const [params, setParams] = useState<ActivitySearchParams | null>(
    city ? { city, category: category || undefined, date: date || undefined, sort: sortBy as ActivitySearchParams['sort'] } : null
  );

  const { data, isLoading, error } = useActivitySearch(params);

  const handleSearch = () => {
    if (!city) return;
    setParams({
      city,
      category: category || undefined,
      date: date || undefined,
      sort: sortBy as ActivitySearchParams['sort'],
    });
  };

  const CATEGORIES = [
    'All', 'Adventure', 'Culture', 'Food & Drink', 'Nature', 'Water Sports',
    'City Tours', 'Day Trips', 'Nightlife', 'Wellness', 'Classes',
  ];

  return (
    <div className="min-h-screen page-listing-bg">
      {/* Search */}
      <div className="bg-gradient-to-r from-[#1a1a2e] to-[#0f3460] py-6">
        <div className="max-w-5xl mx-auto px-4">
          <h1 className="text-white text-xl font-black font-heading mb-4">Things to Do</h1>
          <div className="bg-white rounded-2xl p-4 shadow-lg">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-3">
              <div>
                <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">City</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Where are you going?"
                  className="w-full text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 focus:border-primary-400"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-neutral-400 uppercase block mb-1">Date</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  min={format(new Date(), 'yyyy-MM-dd')}
                  className="text-sm font-semibold text-neutral-800 outline-none border-b border-neutral-200 pb-1 w-full focus:border-primary-400"
                />
              </div>
              <div className="flex items-end">
                <button onClick={handleSearch} className="btn-primary px-6 py-2.5 text-sm flex items-center gap-2">
                  <Search size={14} /> Search
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Category filter */}
        <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => { setCategory(cat === 'All' ? '' : cat); handleSearch(); }}
              className={`text-xs px-3 py-2 rounded-full border font-semibold transition-all shrink-0 ${
                (cat === 'All' && !category) || category === cat
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-300'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Sort */}
        {data && (
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-neutral-500">{data.total || data.results?.length || 0} activities found</p>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
              className="text-xs bg-white border border-neutral-200 rounded-lg px-2 py-1.5 outline-none">
              <option value="popular">Most Popular</option>
              <option value="price_asc">Price: Low → High</option>
              <option value="price_desc">Price: High → Low</option>
              <option value="rating">Highest Rated</option>
              <option value="duration">Duration</option>
            </select>
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={28} className="animate-spin text-neutral-400" />
          </div>
        )}

        {!isLoading && !data && (
          <div className="text-center py-16">
            <Compass size={40} className="mx-auto text-neutral-300 mb-3" />
            <h2 className="text-lg font-bold text-neutral-700 mb-1">Discover activities</h2>
            <p className="text-sm text-neutral-400">Enter a city to find tours, experiences, and things to do.</p>
          </div>
        )}

        {data && data.results && data.results.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.results.map((activity) => (
              <ActivityCard
                key={activity.id}
                activity={activity}
                onClick={() => router.push(`/activities/${activity.slug}`)}
              />
            ))}
          </div>
        )}

        {data && (!data.results || data.results.length === 0) && (
          <div className="text-center py-12">
            <Compass size={40} className="mx-auto text-neutral-300 mb-3" />
            <h2 className="text-lg font-bold text-neutral-700 mb-1">No activities found</h2>
            <p className="text-sm text-neutral-400">Try a different city or category.</p>
          </div>
        )}
      </div>
    </div>
  );
}
