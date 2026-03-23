import type { Metadata } from 'next';
import Link from 'next/link';
import GlobalSearchBar from '@/components/search/GlobalSearchBar';
import DestinationsSection from '@/components/home/DestinationsSection';
import OffersSection from '@/components/home/OffersSection';
import RecentlyViewed from '@/components/home/RecentlyViewed';
import { WebSiteJsonLd, OrganizationJsonLd } from '@/components/seo/JsonLd';

export const metadata: Metadata = {
  title: 'ZygoTrip — Hotels, Buses, Cabs & Packages at Best Prices',
  description:
    'Book hotels, buses, cabs and holiday packages across India. Best prices guaranteed, free cancellation on most bookings.',
};

// ── Static data ───────────────────────────────────────────────────────────────

// Destinations are rendered dynamically by DestinationsSection (hotel counts from API)

const WHY = [
  {
    icon:  '🛡️',
    stat:  '100% Safe',
    title: 'Secure Payments',
    desc:  'Bank-grade 256-bit SSL encryption on every transaction.',
  },
  {
    icon:  '🔄',
    stat:  '5,000+ Hotels',
    title: 'Free Cancellation',
    desc:  'Cancel free up to 24 hrs before check-in on most bookings.',
  },
  {
    icon:  '💬',
    stat:  '< 2 min Response',
    title: '24/7 Support',
    desc:  'Dedicated travel experts available round the clock for you.',
  },
  {
    icon:  '💰',
    stat:  'Price Match',
    title: 'Best Price Guarantee',
    desc:  "Found a lower price? We'll match it and refund the difference.",
  },
] as const;

// ── Page ──────────────────────────────────────────────────────────────────────
export default function HomePage() {
  return (
    <div className="min-h-screen page-listing-bg">
      {/* Schema.org structured data for homepage SEO */}
      <WebSiteJsonLd />
      <OrganizationJsonLd />
      {/* ════════════════════════════════════════════════════════
          HERO SECTION
      ════════════════════════════════════════════════════════ */}
      {/*
        overflow-hidden is intentionally on a child wrapper, NOT on this section.
        Reason: overflow:hidden on a positioned ancestor clips absolute-positioned
        descendants regardless of z-index — including the autosuggest dropdown.
        Decorative backgrounds are wrapped in their own overflow-hidden div so
        they are clipped without affecting interactive components.
      */}
      <section
        className="relative"
        style={{
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%)',
          paddingTop: 68,
          paddingBottom: 0,
        }}
      >
        {/* Decorative backgrounds — clipped within their own absolute container */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {/* Red radial glow at bottom */}
          <div
            className="absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 70% 60% at 50% 110%, rgba(235,32,38,0.28) 0%, transparent 65%)',
            }}
          />
          {/* Subtle top-right accent */}
          <div
            className="absolute -top-24 -right-24 w-80 h-80 rounded-full opacity-20"
            style={{ background: 'radial-gradient(circle, #FF6B35, transparent 70%)' }}
          />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center pb-8">
          {/* Trust badge */}
          <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 text-white/80 text-xs font-bold px-4 py-1.5 rounded-full mb-5 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Trusted by travellers across India
          </div>

          {/* Headline */}
          <h1
            className="text-4xl sm:text-5xl font-black text-white leading-tight mb-3 font-heading tracking-tighter"
          >
            Travel India,{' '}
            <span style={{ color: 'var(--primary-light)' }}>Your Way</span>
          </h1>

          <p className="text-base sm:text-lg mb-8 max-w-xl mx-auto" style={{ color: 'rgba(255,255,255,0.55)' }}>
            Hotels · Buses · Cabs · Packages — all at the best prices.
            <br className="hidden sm:block" />
            Instant confirmation. Free cancellation. Zero hassle.
          </p>
        </div>

        {/* Floating search widget */}
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <GlobalSearchBar showTabs variant="hero" />
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          FARE BANNER — dynamic, shows only when offer is live
      ════════════════════════════════════════════════════════ */}
      <div className="fare-banner">
        <p className="text-white text-xs font-semibold truncate pr-4">
          🎉{' '}
          <span className="font-black">SPECIAL OFFER:</span> Great deals on
          hotels across India — Book now &amp; save
        </p>
        <Link
          href="/hotels"
          className="shrink-0 bg-white/80 text-xs font-black px-4 py-1.5 rounded-full transition-opacity hover:opacity-90"
          style={{ color: 'var(--primary)' }}
        >
          VIEW DEALS →
        </Link>
      </div>

      {/* ════════════════════════════════════════════════════════
          HOTEL HIGHLIGHTS — Primary product focus
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-end justify-between mb-5">
          <div>
            <h2 className="text-xl font-black text-neutral-900 font-heading">
              Top Hotel Deals
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Handpicked stays with unbeatable prices
            </p>
          </div>
          <Link
            href="/hotels"
            className="text-xs font-bold hover:underline"
            style={{ color: 'var(--primary)' }}
          >
            View all hotels →
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { city: 'Goa', tag: 'From ₹899', emoji: '🏖️', color: 'bg-orange-50' },
            { city: 'Jaipur', tag: 'From ₹699', emoji: '🏰', color: 'bg-pink-50' },
            { city: 'Manali', tag: 'From ₹999', emoji: '🏔️', color: 'bg-blue-50' },
            { city: 'Mumbai', tag: 'From ₹1,199', emoji: '🌆', color: 'bg-purple-50' },
          ].map(item => (
            <Link
              key={item.city}
              href={`/hotels?location=${item.city}`}
              className="group rounded-2xl border border-neutral-100 bg-white/80 p-4 hover:shadow-md transition-all text-center"
            >
              <div className={`w-12 h-12 ${item.color} rounded-xl flex items-center justify-center text-2xl mx-auto mb-2 group-hover:scale-110 transition-transform`}>
                {item.emoji}
              </div>
              <h3 className="font-black text-neutral-900 text-sm">{item.city}</h3>
              <p className="text-2xs text-primary-600 font-bold mt-0.5">{item.tag}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          MORE SERVICES — Buses, Cabs, Packages (secondary)
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Link
            href="/buses"
            className="group relative rounded-2xl overflow-hidden border border-neutral-100 shadow-sm hover:shadow-md transition-shadow bg-white/80 p-6 flex items-center gap-4"
          >
            <div className="shrink-0 w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
              🚌
            </div>
            <div>
              <h3 className="font-black text-neutral-900 text-sm mb-0.5">Bus Tickets</h3>
              <p className="text-xs text-neutral-400">AC, Sleeper &amp; Volvo buses across India</p>
            </div>
          </Link>
          <Link
            href="/cabs"
            className="group relative rounded-2xl overflow-hidden border border-neutral-100 shadow-sm hover:shadow-md transition-shadow bg-white/80 p-6 flex items-center gap-4"
          >
            <div className="shrink-0 w-14 h-14 rounded-2xl bg-green-50 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
              🚕
            </div>
            <div>
              <h3 className="font-black text-neutral-900 text-sm mb-0.5">Cab Rentals</h3>
              <p className="text-xs text-neutral-400">Airport transfers, outstation &amp; hourly</p>
            </div>
          </Link>
          <Link
            href="/packages"
            className="group relative rounded-2xl overflow-hidden border border-neutral-100 shadow-sm hover:shadow-md transition-shadow bg-white/80 p-6 flex items-center gap-4"
          >
            <div className="shrink-0 w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
              🌴
            </div>
            <div>
              <h3 className="font-black text-neutral-900 text-sm mb-0.5">Holiday Packages</h3>
              <p className="text-xs text-neutral-400">All-inclusive curated travel packages</p>
            </div>
          </Link>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          TOP OFFERS — Fetched from backend API
      ════════════════════════════════════════════════════════ */}
      <OffersSection />

      {/* ════════════════════════════════════════════════════════
          RECENTLY VIEWED — personalized, only for returning users
      ════════════════════════════════════════════════════════ */}
      <RecentlyViewed />

      {/* ════════════════════════════════════════════════════════
          POPULAR DESTINATIONS
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        <div className="flex items-end justify-between mb-5">
          <div>
            <h2
              className="text-xl font-black text-neutral-900 font-heading"
            >
              Popular Destinations
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Handpicked by our travel experts
            </p>
          </div>
          <Link
            href="/hotels"
            className="text-xs font-bold hover:underline"
            style={{ color: 'var(--primary)' }}
          >
            View all →
          </Link>
        </div>

        {/* Dynamic destination counts from backend API */}
        <DestinationsSection />
      </section>

      {/* ════════════════════════════════════════════════════════
          WHY ZYGOTRIP
      ════════════════════════════════════════════════════════ */}
      <section style={{ background: 'var(--bg-dark)' }} className="py-14">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2
              className="text-2xl font-black text-white mb-1 font-heading"
            >
              Why ZygoTrip?
            </h2>
            <p
              className="text-sm"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              India's fastest-growing travel platform
            </p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {WHY.map(item => (
              <div
                key={item.title}
                className="rounded-2xl p-5 border transition-colors"
                style={{
                  background:   'var(--bg-mid)',
                  borderColor:  'rgba(255,255,255,0.08)',
                }}
              >
                <div className="text-3xl mb-3">{item.icon}</div>
                <p
                  className="text-xs font-black uppercase tracking-wider mb-1"
                  style={{ color: 'var(--primary-light)' }}
                >
                  {item.stat}
                </p>
                <h3
                  className="font-black text-white text-sm mb-1.5 font-heading"
                >
                  {item.title}
                </h3>
                <p
                  className="text-xs leading-relaxed"
                  style={{ color: 'rgba(255,255,255,0.4)' }}
                >
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          CTA STRIP
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div
          className="rounded-3xl overflow-hidden px-8 py-12 text-center text-white"
          style={{ background: 'linear-gradient(135deg, #EB2026 0%, #FF6B35 100%)' }}
        >
          <h2
            className="text-2xl sm:text-3xl font-black mb-2 font-heading"
          >
            Ready to explore India? 🗺️
          </h2>
          <p className="text-white/80 mb-7 max-w-lg mx-auto text-sm">
            Find the best deals on hotels, buses and holiday packages across India.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/hotels"
              className="bg-white/80 font-black px-8 py-3 rounded-xl text-sm hover:bg-red-50 transition-colors shadow-lg"
              style={{ color: 'var(--primary)' }}
            >
              🏨 Browse Hotels
            </Link>
            <Link
              href="/buses"
              className="bg-white/20 border-2 border-white/40 text-white font-black px-8 py-3 rounded-xl text-sm hover:bg-white/30 transition-colors"
            >
              🚌 Bus Tickets
            </Link>
            <Link
              href="/packages"
              className="bg-white/20 border-2 border-white/40 text-white font-black px-8 py-3 rounded-xl text-sm hover:bg-white/30 transition-colors"
            >
              🌴 Packages
            </Link>
          </div>
        </div>
      </section>

    </div>
  );
}
