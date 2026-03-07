'use client';
/**
 * DestinationsSection — Popular Destinations grid on home page.
 *
 * All hotel counts come from the backend aggregations API.
 * Never hardcoded. SSR-safe (shows skeleton count until hydrated).
 */
import { useEffect, useState } from 'react';
import Link from 'next/link';

// Visual config: gradients & taglines are frontend-only display concerns.
// Hotel counts are always fetched from backend.
const DESTINATIONS = [
  { name: 'Goa',       slug: 'Goa',       tagline: 'Beach Paradise',     gradient: 'linear-gradient(135deg,#f093fb 0%,#f5576c 100%)' },
  { name: 'Mumbai',    slug: 'Mumbai',    tagline: 'City of Dreams',      gradient: 'linear-gradient(135deg,#4facfe 0%,#00f2fe 100%)' },
  { name: 'Coorg',     slug: 'Coorg',     tagline: 'Scotland of India',   gradient: 'linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)' },
  { name: 'Jaipur',    slug: 'Jaipur',    tagline: 'Pink City',           gradient: 'linear-gradient(135deg,#a18cd1 0%,#fbc2eb 100%)' },
  { name: 'Bangalore', slug: 'Bangalore', tagline: 'Garden City',         gradient: 'linear-gradient(135deg,#ffecd2 0%,#fcb69f 100%)' },
  { name: 'Hyderabad', slug: 'Hyderabad', tagline: 'City of Pearls',      gradient: 'linear-gradient(135deg,#667eea 0%,#764ba2 100%)' },
  { name: 'Chennai',   slug: 'Chennai',   tagline: "Marina Beach City",   gradient: 'linear-gradient(135deg,#0fd850 0%,#f9f047 100%)' },
  { name: 'Delhi',     slug: 'Delhi',     tagline: 'Capital City',        gradient: 'linear-gradient(135deg,#f7971e 0%,#ffd200 100%)' },
] as const;

interface CityAggregation {
  name: string;
  count: number;
  slug: string;
}

export default function DestinationsSection() {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch('/api/v1/hotels/aggregations')   // no trailing slash — APPEND_SLASH=False in Django
      .then(r => r.json())
      .then(data => {
        const cities: CityAggregation[] = data?.data?.cities ?? [];
        const map: Record<string, number> = {};
        for (const c of cities) {
          map[c.name.toLowerCase()] = c.count;
        }
        setCounts(map);
        setLoaded(true);
      })
      .catch(() => setLoaded(true)); // silently fail — shows '0' for all
  }, []);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {DESTINATIONS.map(dest => {
        const count = counts[dest.name.toLowerCase()] ?? 0;

        return (
          <Link
            key={dest.name}
            href={`/hotels?location=${encodeURIComponent(dest.slug)}`}
            className="relative rounded-2xl overflow-hidden group"
            style={{ background: dest.gradient, minHeight: 130 }}
          >
            {/* Dark overlay for text readability */}
            <div
              className="absolute inset-0"
              style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0) 55%)' }}
            />
            {/* Content */}
            <div className="relative p-4 flex flex-col justify-end" style={{ minHeight: 130 }}>
              <h3
                className="font-black text-white text-lg leading-tight group-hover:scale-105 transition-transform duration-200 origin-bottom-left font-heading"
              >
                {dest.name}
              </h3>
              <p className="text-white/75 text-xs font-semibold mt-0.5">{dest.tagline}</p>
              <p className="text-white/55 text-xs mt-0.5">
                {!loaded ? (
                  <span className="inline-block w-16 h-3 rounded bg-white/20 animate-pulse" />
                ) : (
                  `${count} hotels`
                )}
              </p>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
