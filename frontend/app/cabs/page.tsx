import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Cab Bookings — ZygoTrip',
  description: 'Book cabs, car rentals and airport transfers across India.',
};

export default function CabsPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center max-w-lg">
        <div className="text-7xl mb-6">🚕</div>
        <h1 className="text-3xl font-black text-neutral-900 mb-3">Cab Bookings</h1>
        <p className="text-neutral-500 mb-2 text-lg">
          Book cabs, car rentals and airport transfers.
        </p>
        <p className="text-neutral-400 text-sm mb-8">
          This feature is coming soon. Get ready for one-way trips, round trips, and hourly
          rentals from trusted drivers across India.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link
            href="/hotels"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-white font-bold text-sm"
            style={{ background: 'var(--primary)' }}
          >
            🏨 Browse Hotels
          </Link>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm border-2 border-neutral-200 text-neutral-700 hover:border-neutral-300 transition-colors"
          >
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
