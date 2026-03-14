import type { Metadata } from 'next';
import { Suspense } from 'react';
import CityLandingClient from './CityLandingClient';
import Breadcrumbs from '@/components/seo/Breadcrumbs';
import { FAQJsonLd, BreadcrumbJsonLd } from '@/components/seo/JsonLd';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';

interface Props {
  params: { location: string };
}

// Top cities for static generation
const TOP_CITIES = [
  'goa', 'jaipur', 'manali', 'mumbai', 'bangalore', 'udaipur',
  'delhi', 'hyderabad', 'chennai', 'kolkata', 'shimla', 'ooty',
  'pondicherry', 'varanasi', 'agra', 'kochi', 'mysore', 'darjeeling',
  'rishikesh', 'amritsar', 'jodhpur', 'mount-abu', 'nainital', 'mussoorie',
];

// Pre-generate static pages for top cities
export async function generateStaticParams() {
  return TOP_CITIES.map((city) => ({ location: city }));
}

function titleCase(s: string): string {
  return s
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// City-specific FAQs for rich snippets
function getCityFAQs(city: string): Array<{ question: string; answer: string }> {
  const name = titleCase(city);
  return [
    {
      question: `What are the best hotels in ${name}?`,
      answer: `ZygoTrip offers a wide selection of hotels in ${name} ranging from budget stays to luxury 5-star properties. Use our filters to find the best hotel for your budget and preferences.`,
    },
    {
      question: `How much does a hotel in ${name} cost per night?`,
      answer: `Hotel prices in ${name} vary from ₹500/night for budget stays to ₹15,000+/night for luxury properties. Prices depend on season, location, and amenities.`,
    },
    {
      question: `Can I get free cancellation on hotels in ${name}?`,
      answer: `Yes! Many hotels in ${name} on ZygoTrip offer free cancellation up to 24 hours before check-in. Use the "Free Cancellation" filter to find eligible properties.`,
    },
    {
      question: `What are the popular areas to stay in ${name}?`,
      answer: `The best areas to stay in ${name} depend on your purpose of visit. Use ZygoTrip's area filters and popular location tags to discover the most booked neighborhoods.`,
    },
  ];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const city = titleCase(params.location);
  const title = `Best Hotels in ${city} — Book from ₹499/night | ZygoTrip`;
  const description = `Find and compare ${city} hotels on ZygoTrip. ✓ Best prices ✓ Free cancellation ✓ Instant booking ✓ Verified reviews. Book your ${city} hotel stay now!`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `${SITE_URL}/hotels/in/${params.location}`,
      type: 'website',
      siteName: 'ZygoTrip',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
    alternates: {
      canonical: `${SITE_URL}/hotels/in/${params.location}`,
    },
  };
}

export default function CityLandingPage({ params }: Props) {
  const city = titleCase(params.location);
  const faqs = getCityFAQs(params.location);

  return (
    <>
      {/* Schema.org structured data */}
      <BreadcrumbJsonLd
        items={[
          { name: 'Home', url: '/' },
          { name: 'Hotels', url: '/hotels' },
          { name: `Hotels in ${city}`, url: `/hotels/in/${params.location}` },
        ]}
      />
      <FAQJsonLd items={faqs} />

      <div className="min-h-screen page-listing-bg">
        {/* Breadcrumbs */}
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pt-4">
          <Breadcrumbs
            items={[
              { label: 'Hotels', href: '/hotels' },
              { label: `Hotels in ${city}`, href: `/hotels/in/${params.location}` },
            ]}
          />
        </div>

        {/* SEO-rich heading section */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-black text-neutral-900 font-heading">
            Best Hotels in <span className="text-primary-600">{city}</span>
          </h1>
          <p className="text-neutral-500 mt-2 max-w-2xl">
            Compare prices and find the best deals on hotels in {city}. Book with free cancellation,
            instant confirmation, and verified guest reviews.
          </p>
        </section>

        {/* Hotel listing (client component with all filters) */}
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
          <CityLandingClient location={params.location} cityName={city} />
        </Suspense>

        {/* SEO-rich FAQ section */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <h2 className="text-xl font-bold text-neutral-900 mb-6">
            Frequently Asked Questions about Hotels in {city}
          </h2>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <details
                key={i}
                className="bg-white rounded-xl border border-neutral-200 overflow-hidden group"
              >
                <summary className="px-5 py-4 text-sm font-semibold text-neutral-800 cursor-pointer hover:bg-neutral-50 transition-colors list-none flex items-center justify-between">
                  {faq.question}
                  <span className="text-neutral-400 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="px-5 pb-4 text-sm text-neutral-600 leading-relaxed">
                  {faq.answer}
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* SEO-rich city description */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pb-8">
          <h2 className="text-lg font-bold text-neutral-900 mb-3">
            About Hotels in {city}
          </h2>
          <div className="text-sm text-neutral-600 leading-relaxed space-y-3">
            <p>
              {city} is one of India&apos;s most popular travel destinations, attracting visitors
              with its unique blend of culture, cuisine, and attractions. Whether you&apos;re
              visiting for business or leisure, ZygoTrip helps you find the perfect hotel stay.
            </p>
            <p>
              From budget-friendly guesthouses to luxury 5-star resorts, {city} offers
              accommodation for every budget. Many properties on ZygoTrip feature free
              cancellation, breakfast included, and pay-at-hotel options for your convenience.
            </p>
            <p>
              Book your {city} hotel on ZygoTrip today and enjoy the best prices with instant
              confirmation and 24/7 customer support.
            </p>
          </div>
        </section>

        {/* Internal linking to segment pages for SEO */}
        <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pb-12">
          <h2 className="text-lg font-bold text-neutral-900 mb-4">
            Popular Hotel Categories in {city}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {[
              { slug: 'budget', label: `Budget Hotels in ${city}` },
              { slug: 'luxury', label: `Luxury Hotels in ${city}` },
              { slug: 'family', label: `Family Hotels in ${city}` },
              { slug: 'couple', label: `Couple Hotels in ${city}` },
              { slug: 'free-cancellation', label: `Free Cancellation Hotels` },
              { slug: 'near-railway-station', label: `Near Railway Station` },
              { slug: 'near-airport', label: `Near Airport` },
            ].map((seg) => (
              <a
                key={seg.slug}
                href={`/hotels/in/${params.location}/${seg.slug}`}
                className="block bg-white border border-neutral-200 rounded-xl px-4 py-3 text-sm font-medium text-neutral-700 hover:shadow-md hover:border-primary-300 transition-all"
              >
                {seg.label}
              </a>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
