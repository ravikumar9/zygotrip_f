import type { Metadata } from 'next';
import { Suspense } from 'react';
import dynamic from 'next/dynamic';

const BusDetailClient = dynamic(() => import('./BusDetailClient'), {
  loading: () => (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="h-8 bg-neutral-100 rounded-xl animate-pulse mb-6 w-1/3" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-neutral-100 p-6 animate-pulse">
          <div className="h-6 bg-neutral-100 rounded w-1/2 mb-4" />
          <div className="grid grid-cols-10 gap-2">
            {Array.from({ length: 40 }).map((_, i) => (
              <div key={i} className="w-8 h-8 bg-neutral-100 rounded" />
            ))}
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-neutral-100 p-6 animate-pulse">
          <div className="h-6 bg-neutral-100 rounded w-2/3 mb-4" />
          <div className="space-y-3">
            <div className="h-4 bg-neutral-100 rounded w-full" />
            <div className="h-4 bg-neutral-100 rounded w-3/4" />
            <div className="h-4 bg-neutral-100 rounded w-1/2" />
          </div>
        </div>
      </div>
    </div>
  ),
  ssr: false,
});

export const metadata: Metadata = {
  title: 'Select Seats — Bus Booking | ZygoTrip',
  description: 'Choose your seats and complete your bus booking on ZygoTrip.',
};

export default function BusDetailPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-neutral-500">Loading bus details...</div>}>
      <BusDetailClient />
    </Suspense>
  );
}
