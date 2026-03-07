'use client';

import { useState } from 'react';
import { MapPin, ExternalLink, Map } from 'lucide-react';

interface PropertyMapProps {
  latitude:  string | number;
  longitude: string | number;
  name:      string;
  address?:  string;
}

/**
 * Zero-dependency OpenStreetMap embed via <iframe>.
 * Uses OSM's public export endpoint — no API key required.
 */
export default function PropertyMap({ latitude, longitude, name, address }: PropertyMapProps) {
  const [loaded, setLoaded] = useState(false);
  const [error,  setError]  = useState(false);

  const lat = parseFloat(String(latitude));
  const lng = parseFloat(String(longitude));

  // Validate coordinates
  const valid = !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;

  if (!valid) {
    return (
      <div className="rounded-2xl bg-neutral-50 border border-neutral-200 flex flex-col items-center justify-center py-12 gap-3">
        <Map size={32} className="text-neutral-300" />
        <p className="text-sm text-neutral-400">Map not available for this property</p>
      </div>
    );
  }

  // Bounding box: ±0.006° (~650 m) around the point
  const delta  = 0.006;
  const bbox   = `${lng - delta},${lat - delta},${lng + delta},${lat + delta}`;
  const iframeUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  const osmLink   = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}&zoom=16`;

  return (
    <div className="rounded-2xl overflow-hidden border border-neutral-200 bg-white shadow-card">

      {/* Map header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
        <div className="flex items-center gap-2">
          <MapPin size={15} style={{ color: 'var(--primary)' }} />
          <span className="text-sm font-bold text-neutral-800">Location</span>
          {address && (
            <span className="text-xs text-neutral-400 truncate max-w-[220px]">
              · {address}
            </span>
          )}
        </div>
        <a
          href={osmLink}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-bold transition-colors hover:underline"
          style={{ color: 'var(--primary)' }}
        >
          <ExternalLink size={11} />
          Open map
        </a>
      </div>

      {/* iframe embed */}
      <div className="relative" style={{ height: 320 }}>
        {/* Loading skeleton */}
        {!loaded && !error && (
          <div className="absolute inset-0 skeleton z-10" />
        )}

        {/* Error fallback */}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-50 gap-3 z-10">
            <Map size={28} className="text-neutral-300" />
            <p className="text-xs text-neutral-400">Could not load map</p>
            <a
              href={osmLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold hover:underline"
              style={{ color: 'var(--primary)' }}
            >
              View on OpenStreetMap →
            </a>
          </div>
        )}

        <iframe
          title={`Map – ${name}`}
          src={iframeUrl}
          width="100%"
          height="320"
          style={{
            border: 'none',
            display: error ? 'none' : 'block',
            opacity: loaded ? 1 : 0,
            transition: 'opacity 0.3s ease',
          }}
          loading="lazy"
          referrerPolicy="no-referrer"
          sandbox="allow-scripts allow-same-origin"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
      </div>

      {/* Coordinates caption */}
      <div className="px-4 py-2 bg-neutral-50 border-t border-neutral-100">
        <p className="text-xs text-neutral-400">
          {lat.toFixed(5)}°N, {lng.toFixed(5)}°E ·{' '}
          <a
            href={osmLink}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
            style={{ color: 'var(--primary)' }}
          >
            View on OpenStreetMap
          </a>
        </p>
      </div>
    </div>
  );
}
