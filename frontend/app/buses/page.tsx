import type { Metadata } from 'next';
import { Suspense } from 'react';
import dynamic from 'next/dynamic';

const BusSearchClient = dynamic(() => import('./BusSearchClient'), {
  loading: () => (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="h-12 bg-neutral-100 rounded-2xl animate-pulse mb-6" />
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-white/80 rounded-2xl border border-neutral-100 p-5 animate-pulse">
            <div className="h-4 bg-neutral-100 rounded w-1/3 mb-3" />
            <div className="h-5 bg-neutral-100 rounded w-2/3 mb-3" />
            <div className="h-3 bg-neutral-100 rounded w-1/4" />
          </div>
        ))}
      </div>
    </div>
  ),
  ssr: false,
});

export const metadata: Metadata = {
  title: 'Bus Tickets — Book AC, Sleeper & Volvo Buses | ZygoTrip',
  description: 'Search and book bus tickets across India. Compare schedules, select seats, and get instant confirmation at the best prices.',
};

export default function BusesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-neutral-500">Loading bus search...</div>}>
      <BusSearchClient />
    </Suspense>
  );
}
