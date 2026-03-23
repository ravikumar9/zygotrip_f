import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Press & Media | ZygoTrip',
  description:
    'ZygoTrip press releases, media kit, and contact information for journalists and media organisations.',
};

const PRESS_RELEASES = [
  {
    date:  'March 2026',
    title: 'ZygoTrip Crosses 2 Million Bookings Milestone',
    desc:  'India\'s fast-growing travel platform announces 2M+ confirmed bookings and expansion to 500+ cities.',
  },
  {
    date:  'January 2026',
    title: 'ZygoTrip Launches Holiday Packages with AI-Powered Demand Forecasting',
    desc:  'New travel packages product integrates holiday intelligence engine to optimise pricing around Indian festivals and peak seasons.',
  },
  {
    date:  'November 2025',
    title: 'ZygoTrip Raises Series A Funding',
    desc:  'ZygoTrip announces a Series A funding round to accelerate growth across hotels, buses, cabs, and packages.',
  },
];

export default function PressPage() {
  return (
    <main className="min-h-screen page-listing-bg">
      {/* Header */}
      <section className="bg-gradient-to-br from-neutral-900 to-neutral-700 text-white py-16 px-4 text-center">
        <h1 className="text-4xl font-black font-heading mb-3">Press &amp; Media</h1>
        <p className="text-white/70 max-w-lg mx-auto text-sm">
          Latest news, press releases, and media resources from ZygoTrip.
        </p>
      </section>

      <div className="max-w-4xl mx-auto px-4 py-14 space-y-10">

        {/* Media Contact */}
        <div className="bg-primary-50 border border-primary-100 rounded-2xl p-6">
          <h2 className="text-base font-bold text-primary-900 mb-1">Media Contact</h2>
          <p className="text-sm text-primary-800">
            For press enquiries, interview requests, or media kit downloads, please reach out:
          </p>
          <div className="mt-3 text-sm font-semibold text-primary-700">
            📬{' '}
            <a href="mailto:press@zygotrip.com" className="underline">
              press@zygotrip.com
            </a>
          </div>
        </div>

        {/* Press Releases */}
        <div>
          <h2 className="text-xl font-bold text-neutral-900 mb-6">Latest Press Releases</h2>
          <div className="space-y-4">
            {PRESS_RELEASES.map((pr) => (
              <div
                key={pr.title}
                className="bg-white/80 border border-neutral-200 rounded-2xl p-5 hover:shadow-md transition-shadow"
              >
                <span className="text-xs text-neutral-400 font-medium">{pr.date}</span>
                <h3 className="text-sm font-bold text-neutral-900 mt-1 mb-2">{pr.title}</h3>
                <p className="text-sm text-neutral-500">{pr.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Brand Assets */}
        <div>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">Brand Assets</h2>
          <p className="text-sm text-neutral-600 mb-4">
            Download official ZygoTrip logos, brand guidelines, and screenshots for editorial use.
            Please do not alter colours, proportions, or wording of ZygoTrip branding assets.
          </p>
          <a
            href="mailto:press@zygotrip.com?subject=Media Kit Request"
            className="inline-block bg-neutral-900 text-white text-sm font-semibold px-6 py-3 rounded-xl hover:bg-neutral-700 transition-colors"
          >
            Request Media Kit
          </a>
        </div>

        {/* Boilerplate */}
        <div className="bg-page rounded-2xl border border-neutral-100 p-6">
          <h2 className="text-base font-bold text-neutral-900 mb-3">About ZygoTrip (Boilerplate)</h2>
          <p className="text-sm text-neutral-600 leading-relaxed">
            ZygoTrip Technologies Pvt. Ltd. is India&apos;s fast-growing online travel platform,
            offering hotels, buses, cabs, holiday packages, and activities through a single booking
            experience. Founded in 2023 and headquartered in Bengaluru, ZygoTrip serves 2M+ travellers
            across 500+ cities with a commitment to transparent pricing, instant confirmation, and
            zero hidden charges. ZygoTrip is available on web and mobile (iOS and Android).
          </p>
        </div>
      </div>
    </main>
  );
}
