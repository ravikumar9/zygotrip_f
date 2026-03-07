import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Holiday Packages — ZygoTrip',
  description: 'Discover curated holiday packages across India. Hotels, transport and experiences bundled at the best price.',
};

export default function PackagesPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center max-w-lg">
        <div className="text-7xl mb-6">🌴</div>
        <h1 className="text-3xl font-black text-neutral-900 mb-3">Holiday Packages</h1>
        <p className="text-neutral-500 mb-2 text-lg">
          Curated holiday packages with hotels, transport & experiences.
        </p>
        <p className="text-neutral-400 text-sm mb-8">
          This feature is coming soon. Discover handcrafted packages for popular destinations
          across India — all inclusive at unbeatable prices.
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
