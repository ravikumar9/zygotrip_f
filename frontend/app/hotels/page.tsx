import type { Metadata } from 'next';
import { Suspense } from 'react';
import dynamic from 'next/dynamic';

const HotelListingPage = dynamic(() => import('./HotelListingPage'), {
  loading: () => (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="h-12 bg-neutral-100 rounded-2xl animate-pulse mb-6" />
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white rounded-2xl overflow-hidden shadow-sm border border-neutral-100">
            <div className="h-52 bg-neutral-100 animate-pulse" />
            <div className="p-4 space-y-2">
              <div className="h-4 bg-neutral-100 rounded animate-pulse w-2/3" />
              <div className="h-3 bg-neutral-100 rounded animate-pulse w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  ),
  ssr: false,
});

export const metadata: Metadata = {
  title: 'Hotels — Find & Book the Best Hotels',
  description: 'Search and compare hotels across India. Best prices, free cancellation, and instant confirmation.',
};

export default function Page() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-neutral-500">Loading hotels...</div>}>
      <HotelListingPage />
    </Suspense>
  );
}
