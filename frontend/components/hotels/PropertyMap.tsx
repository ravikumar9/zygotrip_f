'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { MapPin, ExternalLink, Map } from 'lucide-react';

interface PropertyMapProps {
  latitude:  string | number;
  longitude: string | number;
  name:      string;
  address?:  string;
}

// ── Dynamic import: Leaflet requires `window` — must be client-only ──────────
const LeafletMap = dynamic(() => import('./LeafletMapInner'), {
  ssr: false,
  loading: () => (
    <div className="w-full animate-pulse bg-neutral-200" style={{ height: 320 }} />
  ),
});

export default function PropertyMap({ latitude, longitude, name, address }: PropertyMapProps) {
  const lat = parseFloat(String(latitude));
  const lng = parseFloat(String(longitude));
  const valid = !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;

  const googleMapsUrl = `https://www.google.com/maps?q=${lat},${lng}`;
  const osmUrl        = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}&zoom=16`;

  if (!valid) {
    return (
      <div className="rounded-2xl bg-neutral-50 border border-neutral-200 flex flex-col items-center justify-center py-12 gap-3">
        <Map size={32} className="text-neutral-300" />
        <p className="text-sm text-neutral-400">Map not available for this property</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl overflow-hidden border border-neutral-200 bg-white shadow-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
        <div className="flex items-center gap-2">
          <MapPin size={15} style={{ color: 'var(--primary)' }} />
          <span className="text-sm font-bold text-neutral-800">Location</span>
          {address && (
            <span className="text-xs text-neutral-400 truncate max-w-[220px]">· {address}</span>
          )}
        </div>
        <a
          href={googleMapsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-bold transition-colors hover:underline"
          style={{ color: 'var(--primary)' }}
        >
          <ExternalLink size={11} />
          Open in Maps
        </a>
      </div>

      {/* Leaflet map — dynamically loaded, no SSR */}
      <LeafletMap lat={lat} lng={lng} name={name} />

      {/* Footer */}
      <div className="px-4 py-2 bg-neutral-50 border-t border-neutral-100 flex items-center justify-between">
        <p className="text-xs text-neutral-400">
          {lat.toFixed(5)}°N, {lng.toFixed(5)}°E
        </p>
        <div className="flex items-center gap-3">
          <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer"
            className="text-xs font-semibold hover:underline" style={{ color: 'var(--primary)' }}>
            Google Maps
          </a>
          <span className="text-neutral-200">·</span>
          <a href={osmUrl} target="_blank" rel="noopener noreferrer"
            className="text-xs font-semibold hover:underline text-neutral-400 hover:text-neutral-600">
            OpenStreetMap
          </a>
        </div>
      </div>
    </div>
  );
}
