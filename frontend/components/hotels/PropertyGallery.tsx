'use client';
import { useState, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, Grid2x2 } from 'lucide-react';
import type { PropertyImage } from '@/types';

// Fallback placeholder shown when an image URL is broken/404
const IMG_FALLBACK = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600"%3E%3Crect fill="%23e0e7f0" width="800" height="600"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-size="80" font-family="sans-serif"%3E🏨%3C/text%3E%3C/svg%3E';

interface PropertyGalleryProps {
  images: PropertyImage[];
  propertyName: string;
}

export default function PropertyGallery({ images, propertyName }: PropertyGalleryProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  // Keyboard navigation in lightbox
  useEffect(() => {
    if (!lightboxOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') prev();
      if (e.key === 'ArrowRight') next();
      if (e.key === 'Escape') setLightboxOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lightboxOpen, activeIndex]);

  // Filter out images with empty/missing URLs — prevents blank white boxes
  const validImages = (images ?? []).filter(img => img.url && img.url.trim() !== '');

  if (validImages.length === 0) {
    return (
      <div className="w-full rounded-2xl bg-gradient-to-br from-primary-100 via-primary-50 to-blue-100 flex flex-col items-center justify-center mb-6 border border-primary-100"
           style={{ height: 280 }}>
        <span className="text-7xl mb-3">🏨</span>
        <p className="text-sm text-primary-400 font-medium">No photos available</p>
      </div>
    );
  }

  // Sort: is_featured first, then by display_order
  const sorted = [...validImages].sort((a, b) => {
    if (a.is_featured && !b.is_featured) return -1;
    if (!a.is_featured && b.is_featured) return 1;
    return a.display_order - b.display_order;
  });

  const main = sorted[0];
  const side = sorted.slice(1, 5);

  const prev = () => setActiveIndex((i) => (i - 1 + sorted.length) % sorted.length);
  const next = () => setActiveIndex((i) => (i + 1) % sorted.length);

  const openLightbox = (index: number) => {
    setActiveIndex(index);
    setLightboxOpen(true);
  };

  return (
    <>
      {/* ── Gallery Grid ─────────────────────────────────────────────── */}
      <div className="gallery-grid rounded-2xl overflow-hidden mb-6">
        {/* Main image */}
        <div
          className="gallery-main overflow-hidden relative cursor-pointer"
          onClick={() => openLightbox(0)}
        >
          <img
            src={main.url}
            alt={main.caption || propertyName}
            className="w-full h-full object-cover hover:scale-105 transition-transform duration-500"
            onError={e => { (e.currentTarget as HTMLImageElement).src = IMG_FALLBACK; }}
            loading="lazy"
          />
          {/* Photo count overlay */}
          <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur-sm text-white text-xs font-semibold px-3 py-1.5 rounded-full flex items-center gap-1.5">
            <Grid2x2 size={12} />
            {sorted.length} photos
          </div>
        </div>

        {/* Side images (up to 4) */}
        {side.map((img, i) => (
          <div
            key={img.id}
            className="overflow-hidden relative cursor-pointer"
            onClick={() => openLightbox(i + 1)}
          >
            <img
              src={img.url}
              alt={img.caption || propertyName}
              className="w-full h-full object-cover hover:scale-105 transition-transform duration-500"
              onError={e => { (e.currentTarget as HTMLImageElement).src = IMG_FALLBACK; }}
              loading="lazy"
            />
            {/* "Show all" overlay on last visible side image */}
            {i === 3 && sorted.length > 5 && (
              <div className="absolute inset-0 bg-black/55 flex flex-col items-center justify-center text-white gap-1 backdrop-blur-sm">
                <Grid2x2 size={22} />
                <span className="text-sm font-bold">+{sorted.length - 5} more</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ── Lightbox ─────────────────────────────────────────────────── */}
      {lightboxOpen && (
        <div
          className="fixed inset-0 z-[100] bg-black/95 flex items-center justify-center"
          onClick={() => setLightboxOpen(false)}
        >
          <div
            className="relative w-full max-w-5xl px-4"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={() => setLightboxOpen(false)}
              className="absolute -top-12 right-4 text-white/70 hover:text-white transition-colors"
            >
              <X size={28} />
            </button>

            {/* Main image */}
            <img
              src={sorted[activeIndex].url}
              alt={sorted[activeIndex].caption || propertyName}
              className="w-full max-h-[72vh] object-contain rounded-xl"
              onError={e => { (e.currentTarget as HTMLImageElement).src = IMG_FALLBACK; }}
            />

            {/* Caption */}
            {sorted[activeIndex].caption && (
              <p className="text-center text-white/60 text-sm mt-2">
                {sorted[activeIndex].caption}
              </p>
            )}

            {/* Prev / Next buttons */}
            {sorted.length > 1 && (
              <>
                <button
                  onClick={prev}
                  className="absolute left-8 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-white hover:bg-white/35 transition-all"
                >
                  <ChevronLeft size={22} />
                </button>
                <button
                  onClick={next}
                  className="absolute right-8 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-white hover:bg-white/35 transition-all"
                >
                  <ChevronRight size={22} />
                </button>
              </>
            )}

            {/* Counter */}
            <p className="text-center text-white/50 text-xs mt-3 font-medium">
              {activeIndex + 1} / {sorted.length}
            </p>

            {/* Thumbnail strip */}
            <div className="flex gap-2 justify-center mt-3 overflow-x-auto pb-1">
              {sorted.map((img, i) => (
                <button
                  key={img.id}
                  onClick={() => setActiveIndex(i)}
                  className={`flex-shrink-0 w-16 h-11 rounded-lg overflow-hidden transition-all border-2 ${
                    i === activeIndex ? 'border-white opacity-100' : 'border-transparent opacity-45 hover:opacity-70'
                  }`}
                >
                  <img src={img.url} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
