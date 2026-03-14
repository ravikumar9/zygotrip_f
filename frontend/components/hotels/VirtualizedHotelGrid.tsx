'use client';

/**
 * VirtualizedHotelGrid — windowed rendering for large hotel result sets.
 *
 * Uses react-window v2 for DOM-level virtualization, only rendering rows
 * visible in the viewport + overscan. Designed for 100+ hotel result sets.
 *
 * For smaller result sets, the main listing page uses CSS content-visibility
 * optimization + IntersectionObserver infinite scroll, which is sufficient.
 */

import { useRef, useState, useEffect } from 'react';
// react-window v2 — types are loaded from dist/react-window.d.ts
import * as ReactWindow from 'react-window';
import HotelCard from '@/components/hotels/HotelCard';
import type { Property } from '@/types';

// v2 API: List is exported directly
const WindowList = ReactWindow.List as React.ComponentType<{
  height: number;
  rowCount: number;
  rowHeight: number | ((index: number) => number);
  rowComponent: React.ComponentType<{
    index: number;
    style: React.CSSProperties;
    [key: string]: unknown;
  }>;
  rowProps?: Record<string, unknown>;
  overscanCount?: number;
  children?: React.ReactNode;
}>;

interface VirtualizedHotelGridProps {
  hotels: Property[];
  checkin?: string;
  checkout?: string;
  adults?: number;
  rooms?: number;
  location?: string;
}

/** Detect number of columns based on container width */
function useColumns(containerRef: React.RefObject<HTMLDivElement | null>): number {
  const [cols, setCols] = useState(1);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const update = () => {
      const w = el.clientWidth;
      if (w >= 1280) setCols(3);
      else if (w >= 640) setCols(2);
      else setCols(1);
    };
    update();

    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [containerRef]);

  return cols;
}

const ROW_HEIGHT = 420;
const GAP = 20;

/** Single row renderer for react-window v2 */
function RowRenderer({ index, style, ...extra }: {
  index: number;
  style: React.CSSProperties;
  [key: string]: unknown;
}) {
  const hotels = extra.hotels as Property[];
  const cols = extra.cols as number;
  const checkin = extra.checkin as string | undefined;
  const checkout = extra.checkout as string | undefined;
  const adults = extra.adults as number | undefined;
  const rooms = extra.rooms as number | undefined;
  const location = extra.location as string | undefined;
  const start = index * cols;
  const rowHotels = hotels.slice(start, start + cols);

  return (
    <div
      style={{
        ...style,
        paddingBottom: GAP,
        display: 'grid',
        gap: GAP,
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
      }}
    >
      {rowHotels.map((hotel) => (
        <HotelCard
          key={hotel.id}
          hotel={hotel}
          checkin={checkin}
          checkout={checkout}
          adults={adults}
          rooms={rooms}
          location={location}
        />
      ))}
    </div>
  );
}

export default function VirtualizedHotelGrid({
  hotels,
  checkin,
  checkout,
  adults,
  rooms,
  location,
}: VirtualizedHotelGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cols = useColumns(containerRef);
  const rowCount = Math.ceil(hotels.length / cols);

  const [listHeight, setListHeight] = useState(800);
  useEffect(() => {
    setListHeight(Math.max(400, window.innerHeight - 200));
  }, []);

  return (
    <div ref={containerRef}>
      <WindowList
        height={listHeight}
        rowCount={rowCount}
        rowHeight={ROW_HEIGHT + GAP}
        rowComponent={RowRenderer}
        rowProps={{ hotels, cols, checkin, checkout, adults, rooms, location }}
        overscanCount={3}
      />
    </div>
  );
}
