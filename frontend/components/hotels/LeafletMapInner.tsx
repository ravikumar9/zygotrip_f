'use client';

/**
 * LeafletMapInner — actual Leaflet map component.
 *
 * This file is NEVER imported directly. It's loaded only via dynamic()
 * in PropertyMap.tsx with ssr:false, keeping Leaflet out of the server bundle.
 *
 * Tiles: CARTO Voyager (free, no API key, higher rate limits than OSM embed)
 * Fallback: OSM standard tiles
 */

import { MapContainer, TileLayer, Marker, Popup, ZoomControl } from 'react-leaflet';
import L from 'leaflet';

// Fix Leaflet's default marker icon in Next.js / Webpack environments
// (the icon images are not bundled by default)
const DefaultIcon = L.icon({
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize:      [25, 41],
  iconAnchor:    [12, 41],
  popupAnchor:   [1, -34],
  shadowSize:    [41, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

interface Props {
  lat:  number;
  lng:  number;
  name: string;
}

export default function LeafletMapInner({ lat, lng, name }: Props) {
  return (
    <MapContainer
      center={[lat, lng]}
      zoom={15}
      style={{ height: 320, width: '100%' }}
      zoomControl={false}      // we add our own positioned below
      scrollWheelZoom={false}  // prevent page scroll hijack
      attributionControl={true}
    >
      {/* CARTO Voyager tiles — free, no API key, designed for app embeds */}
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        maxZoom={19}
        subdomains="abcd"
      />

      {/* Zoom controls — placed bottom-right away from the header */}
      <ZoomControl position="bottomright" />

      {/* Property pin */}
      <Marker position={[lat, lng]}>
        <Popup>
          <strong style={{ fontSize: 13 }}>{name}</strong>
          <br />
          <span style={{ fontSize: 11, color: '#666' }}>
            {lat.toFixed(5)}°N, {lng.toFixed(5)}°E
          </span>
        </Popup>
      </Marker>
    </MapContainer>
  );
}
