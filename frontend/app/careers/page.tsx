import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Careers at ZygoTrip | Join Our Team',
  description:
    'Build the future of Indian travel with ZygoTrip. Explore open roles in engineering, product, design, operations, and more.',
};

const OPENINGS = [
  { role: 'Senior Backend Engineer (Django/Python)',  team: 'Engineering',  location: 'Bengaluru / Remote' },
  { role: 'Frontend Engineer (Next.js / TypeScript)',  team: 'Engineering',  location: 'Bengaluru / Remote' },
  { role: 'DevOps / SRE Engineer',                    team: 'Engineering',  location: 'Bengaluru' },
  { role: 'Product Manager – Hotels & Search',         team: 'Product',      location: 'Bengaluru' },
  { role: 'UX/UI Designer',                            team: 'Design',       location: 'Bengaluru / Remote' },
  { role: 'Hotel Partnerships Manager',                team: 'Partnerships', location: 'Mumbai / Delhi / Bengaluru' },
  { role: 'Customer Support Specialist',               team: 'Operations',   location: 'Bengaluru' },
  { role: 'Data Analyst – Revenue & Pricing',          team: 'Analytics',    location: 'Bengaluru' },
];

const PERKS = [
  { icon: '🏠', label: 'Remote-Friendly',    desc: 'Engineering and design roles can be fully remote.' },
  { icon: '✈️', label: 'Travel Allowance',   desc: '₹50,000 annual travel credit on ZygoTrip.' },
  { icon: '📚', label: 'Learning Budget',    desc: '₹30,000/year for courses, books, and conferences.' },
  { icon: '🏥', label: 'Health Insurance',   desc: 'Comprehensive health cover for you and your family.' },
  { icon: '🎯', label: 'ESOPs',              desc: 'Employee stock options from Day 1.' },
  { icon: '🍕', label: 'Free Meals',         desc: 'Catered lunch & dinner at Bengaluru HQ.' },
];

export default function CareersPage() {
  return (
    <main className="min-h-screen page-listing-bg">
      {/* Hero */}
      <section className="text-white py-20 px-4 text-center" style={{ background: 'linear-gradient(135deg,#1d4ed8 0%,#2563eb 55%,#f97316 100%)' }}>
        <h1 className="text-4xl md:text-5xl font-black font-heading mb-4">
          Build the Future of Travel
        </h1>
        <p className="text-white/85 text-lg max-w-xl mx-auto">
          Join a passionate team on a mission to make travel effortless for every Indian.
          We&apos;re a fast-moving startup with massive ambitions.
        </p>
      </section>

      {/* Perks */}
      <section className="bg-page py-14 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-neutral-900 font-heading text-center mb-10">Why ZygoTrip?</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
            {PERKS.map((p) => (
              <div key={p.label} className="bg-white/80 rounded-2xl border border-neutral-100 p-5 shadow-sm">
                <span className="text-2xl">{p.icon}</span>
                <h3 className="font-bold text-neutral-900 mt-2 mb-1 text-sm">{p.label}</h3>
                <p className="text-xs text-neutral-500">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Open Roles */}
      <section className="max-w-4xl mx-auto px-4 py-14">
        <h2 className="text-2xl font-bold text-neutral-900 font-heading mb-8 text-center">Open Positions</h2>
        <div className="space-y-3">
          {OPENINGS.map((job) => (
            <div
              key={job.role}
              className="flex flex-col sm:flex-row sm:items-center justify-between bg-white/80 border border-neutral-200 rounded-2xl px-5 py-4 hover:shadow-md hover:border-primary-300 transition-all"
            >
              <div>
                <p className="font-semibold text-neutral-900 text-sm">{job.role}</p>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {job.team} · {job.location}
                </p>
              </div>
              <a
                href={`mailto:careers@zygotrip.com?subject=Application: ${encodeURIComponent(job.role)}`}
                className="mt-3 sm:mt-0 inline-block bg-primary-50 text-primary-700 font-semibold text-sm px-4 py-2 rounded-xl hover:bg-primary-100 transition-colors"
              >
                Apply →
              </a>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm text-neutral-500 text-center">
          Don&apos;t see your role? Send a general application to{' '}
          <a href="mailto:careers@zygotrip.com" className="text-primary-600 underline">
            careers@zygotrip.com
          </a>
        </p>
      </section>

      {/* CTA */}
      <section className="bg-gradient-to-r from-primary-600 to-accent-500 text-white py-14 px-4 text-center">
        <h2 className="text-2xl font-bold mb-3">Ready to join us?</h2>
        <p className="text-white/80 text-sm mb-6">Send your CV to careers@zygotrip.com and let&apos;s talk.</p>
        <Link
          href="mailto:careers@zygotrip.com"
          className="bg-white/80 text-primary-700 font-semibold px-8 py-3 rounded-xl hover:bg-page transition-colors text-sm"
        >
          Get in Touch
        </Link>
      </section>
    </main>
  );
}
