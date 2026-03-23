import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: "About Us — ZygoTrip | India's Trusted Travel Platform",
  description:
    "Learn about ZygoTrip — our mission, story, and the team behind India's fastest-growing travel booking platform for hotels, buses, cabs, and holiday packages.",
};

const STATS = [
  { value: '2M+',     label: 'Happy Travellers' },
  { value: '50,000+', label: 'Hotels Listed' },
  { value: '500+',    label: 'Cities Covered' },
  { value: '4.6★',    label: 'App Rating' },
];

const VALUES = [
  {
    icon: '🔒',
    title: 'Trust & Transparency',
    desc: 'No hidden charges. Every price you see is the price you pay. HMAC-signed transactions and PCI-DSS compliant payment flows protect every rupee.',
  },
  {
    icon: '⚡',
    title: 'Instant Confirmation',
    desc: 'Your booking is confirmed in seconds, not hours. We maintain real-time inventory across all our partner properties so you never face an unpleasant surprise at check-in.',
  },
  {
    icon: '🌏',
    title: 'Built for India',
    desc: 'From UPI and Paytm to EMI on credit cards, we support every payment method Indians love. Our pricing understands GST slabs, regional festivals, and seasonal demand.',
  },
  {
    icon: '🤝',
    title: 'Partner-First',
    desc: 'We treat hotel owners as partners, not just suppliers. Our owner dashboard gives full revenue intelligence, competitor insights, and settlement transparency.',
  },
];

const TEAM = [
  {
    name:     'Ravikumar',
    role:     'Co-Founder',
    initials: 'RK',
    color:    'bg-blue-100 text-blue-700',
  },
  {
    name:     'Bhargavi',
    role:     'Director',
    initials: 'BH',
    color:    'bg-purple-100 text-purple-700',
  },
  {
    name:     'Rajeswari',
    role:     'Director',
    initials: 'RJ',
    color:    'bg-pink-100 text-pink-700',
  },
];

export default function AboutPage() {
  return (
    <main className="min-h-screen page-listing-bg">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        className="text-white py-20 px-4"
        style={{ background: 'linear-gradient(135deg, #1d4ed8 0%, #2563eb 55%, #f97316 100%)' }}
      >
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-white/70 mb-3">
            Our Story
          </p>
          <h1 className="text-4xl md:text-5xl font-black mb-5" style={{ fontFamily: 'inherit' }}>
            About{' '}
            <span className="text-yellow-300">ZygoTrip</span>
          </h1>
          <p className="text-lg md:text-xl max-w-2xl mx-auto leading-relaxed" style={{ color: 'rgba(255,255,255,0.85)' }}>
            We&apos;re on a mission to make travel planning effortless for every Indian traveller —
            from weekend getaways to month-long holidays.
          </p>
        </div>
      </section>

      {/* ── Stats bar ────────────────────────────────────────── */}
      <section className="bg-page py-12 px-4 border-b border-neutral-100">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {STATS.map((s) => (
            <div key={s.label}>
              <p className="text-3xl font-black text-blue-700">{s.value}</p>
              <p className="text-sm text-neutral-500 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Our Story ────────────────────────────────────────── */}
      <section className="max-w-3xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-bold text-neutral-900 mb-6">Our Story</h2>
        <div className="space-y-4 text-neutral-600 leading-relaxed text-[15px]">
          <p>
            ZygoTrip was founded in <strong>February 2026</strong> by a team who believed India
            deserved a travel platform built for Indians — with transparent pricing, instant
            confirmation, and zero hidden charges.
          </p>
          <p>
            Starting with hotels across Goa, Jaipur, and Manali, we grew rapidly by obsessing over
            two things: the best prices and the fastest, most reliable booking experience in India.
            Today, ZygoTrip lists over 50,000 properties across 500+ cities and has served more
            than 2 million happy travellers.
          </p>
          <p>
            We&apos;ve expanded beyond hotels to offer buses, cabs, holiday packages, and
            activities — all under one roof, with a single wallet, and the same commitment to
            transparency that we started with.
          </p>
          <p>
            ZygoTrip is headquartered in India and is on a mission to make quality travel
            accessible to every Indian traveller.
          </p>
        </div>
      </section>

      {/* ── Values ───────────────────────────────────────────── */}
      <section className="bg-page py-16 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-neutral-900 mb-10 text-center">
            What We Stand For
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {VALUES.map((v) => (
              <div
                key={v.title}
                className="bg-white/80 rounded-2xl border border-neutral-100 shadow-sm p-6 hover:shadow-md transition-shadow"
              >
                <span className="text-3xl">{v.icon}</span>
                <h3 className="text-base font-bold text-neutral-900 mt-3 mb-2">{v.title}</h3>
                <p className="text-sm text-neutral-600 leading-relaxed">{v.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Leadership ───────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-bold text-neutral-900 mb-10 text-center">
          Leadership Team
        </h2>
        <div className="flex flex-wrap justify-center gap-10">
          {TEAM.map((m) => (
            <div key={m.name} className="text-center">
              <div
                className={`w-20 h-20 rounded-full font-bold text-xl flex items-center justify-center mx-auto mb-3 ${m.color}`}
              >
                {m.initials}
              </div>
              <p className="font-semibold text-neutral-900 text-sm">{m.name}</p>
              <p className="text-xs text-neutral-500 mt-0.5">{m.role}</p>
            </div>
          ))}
        </div>

        {/* Founded badge */}
        <div className="mt-12 text-center">
          <span className="inline-block bg-blue-50 text-blue-700 text-sm font-semibold px-5 py-2 rounded-full border border-blue-100">
            Founded February 2026 · Bengaluru, India
          </span>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <section
        className="text-white py-14 px-4 text-center"
        style={{ background: 'linear-gradient(90deg, #2563eb 0%, #f97316 100%)' }}
      >
        <h2 className="text-2xl font-bold mb-3">Ready to explore India with ZygoTrip?</h2>
        <p className="mb-7 text-sm" style={{ color: 'rgba(255,255,255,0.80)' }}>
          Millions of travellers trust us every month. Join them today.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/hotels"
            className="bg-white/80 text-blue-700 font-semibold px-7 py-3 rounded-xl hover:bg-page transition-colors text-sm"
          >
            Search Hotels
          </Link>
          <Link
            href="/partner"
            className="font-semibold px-7 py-3 rounded-xl transition-colors text-sm text-white"
            style={{ border: '1px solid rgba(255,255,255,0.5)' }}
          >
            List Your Property
          </Link>
        </div>
      </section>
    </main>
  );
}
