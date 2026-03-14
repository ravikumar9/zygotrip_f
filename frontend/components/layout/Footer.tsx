'use client';

import Link from 'next/link';

// ── Official ZygoTrip Social Channels ────────────────────────────────────────
const SOCIAL_LINKS = [
  {
    name: 'Instagram',
    href: 'https://www.instagram.com/zygotrip/',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
      </svg>
    ),
    color: 'hover:text-pink-400',
  },
  {
    name: 'Facebook',
    href: 'https://www.facebook.com/profile.php?id=61583679493958',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
      </svg>
    ),
    color: 'hover:text-blue-400',
  },
  {
    name: 'YouTube',
    href: 'https://youtube.com/@zygotrip',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
      </svg>
    ),
    color: 'hover:text-red-400',
  },
  {
    name: 'X (Twitter)',
    href: 'https://x.com/ZygoTrip',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
      </svg>
    ),
    color: 'hover:text-white',
  },
  {
    name: 'LinkedIn',
    href: 'https://www.linkedin.com/in/zygo-trip-1968a63b6/',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
      </svg>
    ),
    color: 'hover:text-blue-300',
  },
];

const TRAVEL_LINKS = ['Hotels', 'Buses', 'Cabs', 'Packages', 'Activities', 'Flights'];
const COMPANY_LINKS = [
  { label: 'About Us', href: '/about' },
  { label: 'Careers', href: '/careers' },
  { label: 'Blog', href: '/blog' },
  { label: 'Press', href: '/press' },
  { label: 'Partner With Us', href: '/partner' },
];
const SUPPORT_LINKS = [
  { label: 'Help Centre', href: '/help' },
  { label: 'Cancellation Policy', href: '/cancellation-policy' },
  { label: 'Privacy Policy', href: '/privacy-policy' },
  { label: 'Terms of Service', href: '/terms' },
  { label: 'Contact Us', href: 'mailto:support@zygotrip.com' },
];

const POPULAR_DESTINATIONS = [
  { city: 'Goa',      slug: 'goa' },
  { city: 'Mumbai',   slug: 'mumbai' },
  { city: 'Delhi',    slug: 'delhi' },
  { city: 'Jaipur',   slug: 'jaipur' },
  { city: 'Manali',   slug: 'manali' },
  { city: 'Kerala',   slug: 'kerala' },
  { city: 'Udaipur',  slug: 'udaipur' },
  { city: 'Shimla',   slug: 'shimla' },
];

export default function Footer() {
  return (
    <footer className="bg-neutral-900 text-neutral-300">
      {/* ── Social proof banner ─────────────────────────────── */}
      <div className="bg-gradient-to-r from-accent-600 to-accent-500 text-white py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-sm font-medium">
            🌍 Join 2M+ happy travellers — follow ZygoTrip for exclusive deals!
          </p>
          <div className="flex items-center gap-3">
            {SOCIAL_LINKS.map((s) => (
              <a
                key={s.name}
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Follow ZygoTrip on ${s.name}`}
                className={`text-white/80 ${s.color} transition-colors`}
              >
                {s.icon}
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* ── Main footer ─────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">

          {/* Brand + social */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="inline-block mb-3">
              <span className="text-2xl font-bold text-white">
                Zygo<span className="text-accent-400">Trip</span>
              </span>
            </Link>
            <p className="text-sm text-neutral-400 leading-relaxed mb-6">
              Your trusted travel companion for hotels, buses, cabs, and holiday packages across India.
            </p>

            {/* Social icons */}
            <div className="flex items-center gap-3 flex-wrap">
              {SOCIAL_LINKS.map((s) => (
                <a
                  key={s.name}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`ZygoTrip on ${s.name}`}
                  title={s.name}
                  className={`text-neutral-400 ${s.color} transition-colors p-1.5 rounded-lg hover:bg-neutral-800`}
                >
                  {s.icon}
                </a>
              ))}
            </div>

            {/* App store badges */}
            <div className="mt-5 flex flex-col gap-2">
              <p className="text-xs text-neutral-500 uppercase tracking-wide font-semibold">Download App</p>
              <div className="flex gap-2">
                <a
                  href="#"
                  className="flex items-center gap-1.5 bg-neutral-800 hover:bg-neutral-700 text-white text-xs px-3 py-2 rounded-lg transition-colors border border-neutral-700"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                  </svg>
                  App Store
                </a>
                <a
                  href="#"
                  className="flex items-center gap-1.5 bg-neutral-800 hover:bg-neutral-700 text-white text-xs px-3 py-2 rounded-lg transition-colors border border-neutral-700"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3.18 23.76c.3.17.65.19.97.08L13.86 12 3.18.16C2.83.27 2.5.55 2.5 1.02v21.96c0 .47.33.65.68.78zM14.89 13.03l2.79 2.79-9.59 5.49 6.8-8.28zm3.84-1.03L16.6 10.8l-1.71 1.71 1.71 1.71L18.73 13l.24-.27-.24-.73zm-11.64-8.3l9.59 5.49-2.79 2.79L7.09 3.7z"/>
                  </svg>
                  Google Play
                </a>
              </div>
            </div>
          </div>

          {/* Travel links */}
          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Travel</h4>
            <ul className="space-y-2 text-sm">
              {TRAVEL_LINKS.map((item) => (
                <li key={item}>
                  <Link
                    href={`/${item.toLowerCase()}`}
                    className="hover:text-white transition-colors"
                  >
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company links */}
          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Company</h4>
            <ul className="space-y-2 text-sm">
              {COMPANY_LINKS.map(({ label, href }) => (
                <li key={label}>
                  <Link href={href} className="hover:text-white transition-colors">{label}</Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Support links */}
          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Support</h4>
            <ul className="space-y-2 text-sm">
              {SUPPORT_LINKS.map(({ label, href }) => (
                <li key={label}>
                  <a href={href} className="hover:text-white transition-colors">{label}</a>
                </li>
              ))}
            </ul>
            {/* Trust badges */}
            <div className="mt-5">
              <p className="text-xs text-neutral-500 uppercase tracking-wide font-semibold mb-2">Secured by</p>
              <div className="flex gap-2 items-center text-xs text-neutral-400">
                <span className="bg-neutral-800 px-2 py-1 rounded border border-neutral-700">🔒 SSL</span>
                <span className="bg-neutral-800 px-2 py-1 rounded border border-neutral-700">PCI DSS</span>
              </div>
            </div>
          </div>

          {/* Popular destinations */}
          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Popular</h4>
            <ul className="space-y-2 text-sm">
              {POPULAR_DESTINATIONS.map(({ city, slug }) => (
                <li key={slug}>
                  <Link
                    href={`/hotels/in/${slug}`}
                    className="hover:text-white transition-colors"
                  >
                    Hotels in {city}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── Bottom bar ───────────────────────────────────── */}
        <div className="mt-12 pt-6 border-t border-neutral-800">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-neutral-500">
            <p>© {new Date().getFullYear()} ZygoTrip Technologies Pvt. Ltd. All rights reserved.</p>

            {/* Payment methods */}
            <div className="flex items-center gap-2">
              <span className="text-xs">Pay via:</span>
              {['UPI', 'Visa', 'MC', 'Amex', 'NetBanking'].map((method) => (
                <span key={method} className="bg-neutral-800 text-neutral-400 text-xs px-2 py-0.5 rounded border border-neutral-700">
                  {method}
                </span>
              ))}
            </div>

            <p className="flex items-center gap-1">
              Made with <span className="text-red-400">❤️</span> in India 🇮🇳
            </p>
          </div>

          {/* Social follow prompt */}
          <div className="mt-6 text-center">
            <p className="text-xs text-neutral-600">
              Follow us for travel inspiration, exclusive deals, and destination guides:&nbsp;
              {SOCIAL_LINKS.map((s, i) => (
                <span key={s.name}>
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-neutral-300 transition-colors underline underline-offset-2"
                  >
                    {s.name}
                  </a>
                  {i < SOCIAL_LINKS.length - 1 && ' · '}
                </span>
              ))}
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
