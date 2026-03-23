import type { Metadata } from 'next';
import Link from 'next/link';

const SOCIAL_LINKS = [
  { label: 'Facebook', href: 'https://www.facebook.com/profile.php?id=61583679493958' },
  { label: 'YouTube', href: 'https://youtube.com/@zygotrip' },
  { label: 'LinkedIn', href: 'https://www.linkedin.com/in/zygo-trip-1968a63b6/' },
  { label: 'X', href: 'https://x.com/ZygoTrip' },
  { label: 'Instagram', href: 'https://www.instagram.com/zygotrip/' },
];

export const metadata: Metadata = {
  title: 'Travel Blog | ZygoTrip',
  description:
    'Discover travel guides, destination tips, hotel reviews, and travel inspiration for your next India trip on the ZygoTrip blog.',
};

const POSTS = [
  {
    slug:    'best-hotels-goa-2026',
    title:   'Best Hotels in Goa for 2026: Beach Stays & Budget Picks',
    excerpt: 'From shack-side guesthouses in Arambol to luxury resorts in Candolim — our curated guide to the best Goa stays.',
    tag:     'Destination Guide',
    date:    'March 10, 2026',
    readTime: '5 min read',
  },
  {
    slug:    'manali-travel-tips',
    title:   'Manali in April: What to Expect, Where to Stay',
    excerpt: 'Snow, biker culture, and budget dhabas — everything you need to plan the perfect Manali trip this spring.',
    tag:     'Travel Tips',
    date:    'March 7, 2026',
    readTime: '7 min read',
  },
  {
    slug:    'rajasthan-road-trip',
    title:   'The Ultimate Rajasthan Road Trip Itinerary (7 Days)',
    excerpt: 'Jaipur → Pushkar → Jodhpur → Jaisalmer → Udaipur. Our week-long golden triangle plus route.',
    tag:     'Itinerary',
    date:    'March 3, 2026',
    readTime: '10 min read',
  },
  {
    slug:    'budget-travel-india',
    title:   '10 Ways to Travel India on ₹1,500 a Day',
    excerpt: 'Backpacker secrets, budget hotel hacks, and the best free attractions in Indian cities.',
    tag:     'Budget Travel',
    date:    'February 25, 2026',
    readTime: '6 min read',
  },
  {
    slug:    'kerala-monsoon',
    title:   'Why Kerala in Monsoon is Actually Magical',
    excerpt: 'Forget the crowds — the backwaters, spice gardens, and Ayurveda resorts are best in the rains.',
    tag:     'Destination Guide',
    date:    'February 18, 2026',
    readTime: '5 min read',
  },
  {
    slug:    'hotel-checkin-tips',
    title:   '7 Things to Check at Hotel Check-In (That Most Travellers Ignore)',
    excerpt: 'Minibar charges, WiFi passwords, and room upgrades — what to ask and verify the moment you arrive.',
    tag:     'Travel Hacks',
    date:    'February 12, 2026',
    readTime: '4 min read',
  },
];

const TAG_COLORS: Record<string, string> = {
  'Destination Guide': 'bg-blue-50 text-blue-700',
  'Travel Tips':       'bg-green-50 text-green-700',
  'Itinerary':         'bg-purple-50 text-purple-700',
  'Budget Travel':     'bg-orange-50 text-orange-700',
  'Travel Hacks':      'bg-yellow-50 text-yellow-700',
};

export default function BlogPage() {
  return (
    <main className="min-h-screen page-listing-bg">
      {/* Header */}
      <section className="text-white py-16 px-4 text-center" style={{ background: 'linear-gradient(135deg,#1d4ed8,#f97316)' }}>
        <h1 className="text-4xl font-black font-heading mb-3">ZygoTrip Travel Blog</h1>
        <p className="text-white/80 max-w-lg mx-auto text-sm">
          Destination guides, hotel reviews, travel hacks, and inspiration for your next India adventure.
        </p>
      </section>

      {/* Posts Grid */}
      <section className="max-w-5xl mx-auto px-4 py-14">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {POSTS.map((post) => (
            <article
              key={post.slug}
              className="bg-white/80 border border-neutral-200 rounded-2xl overflow-hidden hover:shadow-md transition-shadow"
            >
              {/* Placeholder image */}
              <div className="h-44 flex items-center justify-center text-4xl" style={{ background: 'linear-gradient(135deg,#dbeafe,#fed7aa)' }}>
                🌄
              </div>
              <div className="p-5">
                <span
                  className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                    TAG_COLORS[post.tag] ?? 'bg-neutral-100 text-neutral-600'
                  }`}
                >
                  {post.tag}
                </span>
                <h2 className="text-sm font-bold text-neutral-900 mt-3 mb-2 leading-snug line-clamp-2">
                  {post.title}
                </h2>
                <p className="text-xs text-neutral-500 line-clamp-2 leading-relaxed mb-3">
                  {post.excerpt}
                </p>
                <div className="flex items-center justify-between text-xs text-neutral-400">
                  <span>{post.date}</span>
                  <span>{post.readTime}</span>
                </div>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-10 text-center">
          <p className="text-sm text-neutral-400 mb-4">
            More articles coming soon. Follow ZygoTrip across our official channels for travel inspiration and destination drops.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
            {SOCIAL_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="rounded-full border border-neutral-200 px-4 py-2 text-neutral-600 hover:border-primary-300 hover:text-primary-700 transition-colors"
                target="_blank"
                rel="noopener noreferrer"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* Explore destinations CTA */}
      <section className="bg-page border-t border-neutral-100 py-12 px-4 text-center">
        <h2 className="text-xl font-bold text-neutral-900 mb-2">Ready to travel?</h2>
        <p className="text-neutral-500 text-sm mb-5">Book hotels across 500+ Indian destinations on ZygoTrip.</p>
        <Link
          href="/hotels"
          className="bg-primary-600 text-white font-semibold px-8 py-3 rounded-xl hover:bg-primary-700 transition-colors text-sm"
        >
          Search Hotels
        </Link>
      </section>
    </main>
  );
}
