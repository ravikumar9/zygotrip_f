import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Partner With ZygoTrip | List Your Hotel, Bus or Cab',
  description:
    'Grow your hospitality or transport business with ZygoTrip. List your hotel, bus service, or cab fleet to reach 2M+ travellers across India.',
};

const BENEFITS = [
  {
    icon: '📈',
    title: 'Increase Occupancy',
    desc: 'Reach 2M+ active travellers. Our smart pricing and demand forecasting tools help you maximise RevPAR.',
  },
  {
    icon: '💡',
    title: 'Revenue Intelligence Dashboard',
    desc: 'Get real-time insights on ADR, occupancy rate, competitor pricing, and 30-day demand forecasts.',
  },
  {
    icon: '💰',
    title: 'Transparent Settlements',
    desc: 'Weekly and monthly settlements with full line-item breakdowns. No hidden deductions, ever.',
  },
  {
    icon: '🔗',
    title: 'Channel Manager Integration',
    desc: 'Connect your existing PMS or channel manager (STAAH, SiteMinder, Channex) for seamless inventory sync.',
  },
  {
    icon: '📱',
    title: 'Owner Mobile App',
    desc: 'Manage bookings, update availability, and respond to reviews — all from your smartphone.',
  },
  {
    icon: '🤝',
    title: 'Dedicated Account Manager',
    desc: 'Every ZygoTrip partner gets a dedicated onboarding specialist and ongoing account support.',
  },
];

const STEPS = [
  { step: '01', title: 'Submit Your Application', desc: 'Fill in the form below with your property or fleet details. Our team reviews within 48 hours.' },
  { step: '02', title: 'Onboarding Call',           desc: 'A ZygoTrip representative will walk you through the platform, pricing, and contract.' },
  { step: '03', title: 'Go Live',                   desc: 'Your listing goes live on ZygoTrip and you start receiving bookings within days.' },
];

export default function PartnerPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Hero */}
      <section className="text-white py-20 px-4 text-center" style={{ background: 'linear-gradient(135deg,#171717,#1e3a8a)' }}>
        <h1 className="text-4xl md:text-5xl font-black font-heading mb-4">
          Grow With ZygoTrip
        </h1>
        <p className="text-white/80 text-lg max-w-xl mx-auto mb-8">
          List your hotel, guesthouse, bus, or cab service on ZygoTrip and reach
          millions of travellers across India.
        </p>
        <a
          href="mailto:partners@zygotrip.com"
          className="text-white font-semibold px-8 py-3 rounded-xl transition-colors text-sm" style={{ backgroundColor:'#f97316' }}
        >
          Get Started →
        </a>
      </section>

      {/* Stats */}
      <section className="text-white py-10 px-4" style={{ backgroundColor:'#2563eb' }}>
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { value: '2M+',    label: 'Monthly Travellers' },
            { value: '50,000+', label: 'Partner Properties' },
            { value: '500+',   label: 'Cities' },
            { value: '4.6★',   label: 'App Rating' },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-3xl font-black">{s.value}</p>
              <p className="text-sm text-white/70 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Benefits */}
      <section className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-bold text-neutral-900 font-heading text-center mb-10">
          Why Partner With Us?
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {BENEFITS.map((b) => (
            <div
              key={b.title}
              className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6 hover:shadow-md transition-shadow"
            >
              <span className="text-3xl">{b.icon}</span>
              <h3 className="font-bold text-neutral-900 mt-3 mb-2 text-sm">{b.title}</h3>
              <p className="text-sm text-neutral-600 leading-relaxed">{b.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-neutral-50 py-14 px-4">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-neutral-900 font-heading text-center mb-10">
            How It Works
          </h2>
          <div className="space-y-6">
            {STEPS.map((s) => (
              <div key={s.step} className="flex gap-5 items-start">
                <div className="w-10 h-10 rounded-full text-white font-black text-sm flex items-center justify-center shrink-0" style={{ backgroundColor:'#2563eb' }}>
                  {s.step}
                </div>
                <div>
                  <h3 className="font-bold text-neutral-900 mb-1 text-sm">{s.title}</h3>
                  <p className="text-sm text-neutral-600">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact CTA */}
      <section className="max-w-3xl mx-auto px-4 py-14 text-center">
        <h2 className="text-2xl font-bold text-neutral-900 font-heading mb-3">
          Ready to list your property?
        </h2>
        <p className="text-neutral-500 text-sm mb-6">
          Reach out to our partnerships team and we&apos;ll get you onboarded within 48 hours.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center text-sm">
          <a
            href="mailto:partners@zygotrip.com"
            className="text-white font-semibold px-7 py-3 rounded-xl transition-colors" style={{ backgroundColor:'#2563eb' }}
          >
            Email: partners@zygotrip.com
          </a>
          <Link
            href="/list-property"
            className="border border-neutral-300 text-neutral-700 font-semibold px-7 py-3 rounded-xl hover:bg-neutral-50 transition-colors"
          >
            List Your Property →
          </Link>
        </div>
      </section>
    </main>
  );
}
