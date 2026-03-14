import type { Metadata } from 'next';
import { Suspense } from 'react';
import SegmentLandingClient from './SegmentLandingClient';
import Breadcrumbs from '@/components/seo/Breadcrumbs';
import { FAQJsonLd, BreadcrumbJsonLd } from '@/components/seo/JsonLd';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';

interface Props {
  params: { location: string; segment: string };
}

// ── Segment definitions ──────────────────────────────────────────────────────

interface SegmentConfig {
  slug: string;
  label: string;
  heading: (city: string) => string;
  description: (city: string) => string;
  filter: Record<string, string | number | boolean>;
}

const SEGMENTS: Record<string, SegmentConfig> = {
  budget: {
    slug: 'budget',
    label: 'Budget Hotels',
    heading: (c) => `Budget Hotels in ${c} — Under ₹3,000/night`,
    description: (c) =>
      `Find the best budget hotels in ${c} starting from ₹499/night. ✓ Verified reviews ✓ Free cancellation ✓ Pay at hotel. Book affordable ${c} stays on ZygoTrip.`,
    filter: { max_price: 3000, sort: 'price_asc' },
  },
  luxury: {
    slug: 'luxury',
    label: 'Luxury Hotels',
    heading: (c) => `Luxury 5-Star Hotels in ${c}`,
    description: (c) =>
      `Discover premium luxury hotels in ${c} with world-class amenities, spa, pool & fine dining. Compare 4 & 5-star ${c} hotels on ZygoTrip.`,
    filter: { min_price: 8000, star_rating: 5, sort: 'rating' },
  },
  family: {
    slug: 'family',
    label: 'Family Hotels',
    heading: (c) => `Best Family Hotels in ${c}`,
    description: (c) =>
      `Top family-friendly hotels in ${c} with spacious rooms, kids' amenities & great locations. Compare and book the perfect family stay.`,
    filter: { amenities: 'family', sort: 'popular' },
  },
  couple: {
    slug: 'couple',
    label: "Couple Hotels",
    heading: (c) => `Romantic & Couple-Friendly Hotels in ${c}`,
    description: (c) =>
      `Find couple-friendly hotels in ${c} with great privacy, romantic ambiance & best-in-class facilities. Perfect for honeymoons & anniversaries.`,
    filter: { amenities: 'couple', sort: 'rating' },
  },
  'near-railway-station': {
    slug: 'near-railway-station',
    label: 'Near Railway Station',
    heading: (c) => `Hotels Near ${c} Railway Station`,
    description: (c) =>
      `Book hotels near ${c} railway station. Convenient stays within 2 km of the station with easy check-in, free cancellation & great prices.`,
    filter: { near: 'railway_station', sort: 'distance' },
  },
  'near-airport': {
    slug: 'near-airport',
    label: 'Near Airport',
    heading: (c) => `Hotels Near ${c} Airport`,
    description: (c) =>
      `Find hotels near ${c} airport for convenient transit stays. Early check-in, airport shuttle & 24/7 front desk available.`,
    filter: { near: 'airport', sort: 'distance' },
  },
  'free-cancellation': {
    slug: 'free-cancellation',
    label: 'Free Cancellation',
    heading: (c) => `Hotels with Free Cancellation in ${c}`,
    description: (c) =>
      `Book hotels in ${c} with free cancellation. Change plans without losing money — cancel up to 24 hours before check-in at no cost.`,
    filter: { free_cancellation: true, sort: 'popular' },
  },
};

// Top cities × segments for static generation
const TOP_CITIES = [
  'goa', 'jaipur', 'manali', 'mumbai', 'bangalore', 'udaipur',
  'delhi', 'hyderabad', 'chennai', 'kolkata', 'shimla', 'ooty',
  'pondicherry', 'varanasi', 'agra', 'kochi', 'mysore', 'darjeeling',
  'rishikesh', 'amritsar', 'jodhpur', 'mount-abu', 'nainital', 'mussoorie',
];

const PRIORITY_SEGMENTS = ['budget', 'luxury', 'family', 'couple', 'free-cancellation'];

export async function generateStaticParams() {
  const params: Array<{ location: string; segment: string }> = [];
  for (const city of TOP_CITIES) {
    for (const seg of PRIORITY_SEGMENTS) {
      params.push({ location: city, segment: seg });
    }
  }
  return params;
}

function titleCase(s: string): string {
  return s.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function getSegmentFAQs(
  city: string,
  segment: SegmentConfig,
): Array<{ question: string; answer: string }> {
  const name = titleCase(city);
  return [
    {
      question: `What are the best ${segment.label.toLowerCase()} in ${name}?`,
      answer: `ZygoTrip lists verified ${segment.label.toLowerCase()} in ${name} with real guest ratings, transparent pricing, and instant booking confirmation.`,
    },
    {
      question: `How do I find ${segment.label.toLowerCase()} in ${name}?`,
      answer: `Use ZygoTrip's smart filters — we automatically show ${segment.label.toLowerCase()} in ${name} sorted by guest ratings and value for money.`,
    },
    {
      question: `Can I get free cancellation on ${segment.label.toLowerCase()} in ${name}?`,
      answer: `Many ${segment.label.toLowerCase()} in ${name} offer free cancellation up to 24 hours before check-in. Look for the "Free Cancellation" badge on listings.`,
    },
  ];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const city = titleCase(params.location);
  const segment = SEGMENTS[params.segment];

  if (!segment) {
    return { title: `Hotels in ${city} | ZygoTrip` };
  }

  const title = `${segment.heading(city)} | ZygoTrip`;
  const description = segment.description(city);

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `${SITE_URL}/hotels/in/${params.location}/${params.segment}`,
      type: 'website',
      siteName: 'ZygoTrip',
    },
    twitter: { card: 'summary_large_image', title, description },
    alternates: {
      canonical: `${SITE_URL}/hotels/in/${params.location}/${params.segment}`,
    },
  };
}

export default function SegmentLandingPage({ params }: Props) {
  const city = titleCase(params.location);
  const segment = SEGMENTS[params.segment];

  if (!segment) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-neutral-500">Segment not found.</p>
      </div>
    );
  }

  const faqs = getSegmentFAQs(params.location, segment);

  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: 'Home', url: '/' },
          { name: 'Hotels', url: '/hotels' },
          { name: `Hotels in ${city}`, url: `/hotels/in/${params.location}` },
          { name: segment.label, url: `/hotels/in/${params.location}/${params.segment}` },
        ]}
      />
      <FAQJsonLd items={faqs} />

      <div className="min-h-screen page-listing-bg">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pt-4">
          <Breadcrumbs
            items={[
              { label: 'Hotels', href: '/hotels' },
              { label: `Hotels in ${city}`, href: `/hotels/in/${params.location}` },
              { label: segment.label, href: `/hotels/in/${params.location}/${params.segment}` },
            ]}
          />
        </div>

        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-black text-neutral-900 font-heading">
            {segment.heading(city)}
          </h1>
          <p className="text-neutral-500 mt-2 max-w-2xl">{segment.description(city)}</p>
        </section>

        {/* Cross-links to other segments */}
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pb-4">
          <div className="flex flex-wrap gap-2">
            {Object.values(SEGMENTS)
              .filter((s) => s.slug !== params.segment)
              .map((s) => (
                <a
                  key={s.slug}
                  href={`/hotels/in/${params.location}/${s.slug}`}
                  className="text-xs px-3 py-1.5 rounded-full border border-neutral-200 bg-white text-neutral-600 hover:border-primary-400 hover:text-primary-700 transition-colors"
                >
                  {s.label}
                </a>
              ))}
          </div>
        </div>

        <Suspense
          fallback={
            <div className="max-w-[1200px] mx-auto px-4 py-8">
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="bg-white rounded-2xl overflow-hidden shadow-sm border">
                    <div className="h-52 bg-neutral-100 animate-pulse" />
                    <div className="p-4 space-y-2">
                      <div className="h-4 bg-neutral-100 rounded animate-pulse w-2/3" />
                      <div className="h-3 bg-neutral-100 rounded animate-pulse w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          }
        >
          <SegmentLandingClient
            location={params.location}
            cityName={city}
            segmentSlug={params.segment}
            segmentLabel={segment.label}
            segmentFilter={segment.filter}
          />
        </Suspense>

        {/* FAQ section */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <h2 className="text-xl font-bold text-neutral-900 mb-6">
            FAQs — {segment.label} in {city}
          </h2>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <details
                key={i}
                className="bg-white rounded-xl border border-neutral-200 overflow-hidden group"
              >
                <summary className="px-5 py-4 text-sm font-semibold text-neutral-800 cursor-pointer hover:bg-neutral-50 transition-colors list-none flex items-center justify-between">
                  {faq.question}
                  <span className="text-neutral-400 group-open:rotate-180 transition-transform">
                    ▼
                  </span>
                </summary>
                <div className="px-5 pb-4 text-sm text-neutral-600 leading-relaxed">
                  {faq.answer}
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* Internal linking block for SEO */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pb-12">
          <h2 className="text-lg font-bold text-neutral-900 mb-3">
            Explore More Hotels in {city}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {Object.values(SEGMENTS).map((s) => (
              <a
                key={s.slug}
                href={`/hotels/in/${params.location}/${s.slug}`}
                className="block bg-white border border-neutral-200 rounded-xl px-4 py-3 text-sm font-medium text-neutral-700 hover:shadow-md hover:border-primary-300 transition-all"
              >
                {s.heading(city).replace(` | ZygoTrip`, '')}
              </a>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
