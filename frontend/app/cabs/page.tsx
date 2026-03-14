import type { Metadata } from 'next';
import { Suspense } from 'react';
import dynamic from 'next/dynamic';

const CabSearchClient = dynamic(() => import('./CabSearchClient'), {
  loading: () => (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="h-12 bg-neutral-100 rounded-2xl animate-pulse mb-6" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white rounded-2xl border border-neutral-100 overflow-hidden animate-pulse">
            <div className="h-48 bg-neutral-100" />
            <div className="p-4 space-y-3">
              <div className="h-4 bg-neutral-100 rounded w-2/3" />
              <div className="h-3 bg-neutral-100 rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  ),
  ssr: false,
});

export const metadata: Metadata = {
  title: 'Cab Bookings — Rent Cars, Airport Transfers & Outstation | ZygoTrip',
  description: 'Book cabs, car rentals and airport transfers across India. Hatchbacks, sedans, SUVs and luxury vehicles at the best prices.',
};

export default function CabsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-neutral-500">Loading cab search...</div>}>
      <CabSearchClient />
    </Suspense>
  );
}
