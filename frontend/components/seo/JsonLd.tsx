/**
 * JSON-LD Structured Data components for SEO.
 *
 * Generates schema.org markup for:
 *  - Hotel (lodging business)
 *  - AggregateRating
 *  - BreadcrumbList
 *  - FAQPage
 *  - WebSite (search action)
 *  - Organization
 */

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';

// ── Types ────────────────────────────────────────────────────────

interface HotelSchemaProps {
  name: string;
  description: string;
  slug: string;
  address?: {
    city?: string;
    state?: string;
    country?: string;
    streetAddress?: string;
    postalCode?: string;
  };
  stars?: number;
  rating?: number;
  reviewCount?: number;
  priceRange?: string;
  images?: string[];
  amenities?: string[];
  checkInTime?: string;
  checkOutTime?: string;
  geo?: { lat: number; lng: number };
}

interface BreadcrumbItem {
  name: string;
  url: string;
}

interface FAQItem {
  question: string;
  answer: string;
}

// ── Components ───────────────────────────────────────────────────

export function HotelJsonLd({
  name, description, slug, address, stars, rating,
  reviewCount, priceRange, images, amenities, checkInTime,
  checkOutTime, geo,
}: HotelSchemaProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Hotel',
    name,
    description,
    url: `${SITE_URL}/hotels/${slug}`,
    ...(images?.length && { image: images }),
    ...(stars && { starRating: { '@type': 'Rating', ratingValue: stars } }),
    ...(rating && reviewCount && {
      aggregateRating: {
        '@type': 'AggregateRating',
        ratingValue: rating,
        bestRating: 5,
        worstRating: 1,
        reviewCount,
      },
    }),
    ...(priceRange && { priceRange }),
    ...(address && {
      address: {
        '@type': 'PostalAddress',
        ...(address.streetAddress && { streetAddress: address.streetAddress }),
        ...(address.city && { addressLocality: address.city }),
        ...(address.state && { addressRegion: address.state }),
        ...(address.country && { addressCountry: address.country || 'IN' }),
        ...(address.postalCode && { postalCode: address.postalCode }),
      },
    }),
    ...(geo && {
      geo: {
        '@type': 'GeoCoordinates',
        latitude: geo.lat,
        longitude: geo.lng,
      },
    }),
    ...(amenities?.length && {
      amenityFeature: amenities.map((a) => ({
        '@type': 'LocationFeatureSpecification',
        name: a,
        value: true,
      })),
    }),
    ...(checkInTime && { checkinTime: checkInTime }),
    ...(checkOutTime && { checkoutTime: checkOutTime }),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function BreadcrumbJsonLd({ items }: { items: BreadcrumbItem[] }) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url.startsWith('http') ? item.url : `${SITE_URL}${item.url}`,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function FAQJsonLd({ items }: { items: FAQItem[] }) {
  if (!items.length) return null;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function WebSiteJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'ZygoTrip',
    url: SITE_URL,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${SITE_URL}/hotels?location={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function OrganizationJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'ZygoTrip',
    url: SITE_URL,
    logo: `${SITE_URL}/logo.png`,
    sameAs: [
      'https://twitter.com/zygotrip',
      'https://www.facebook.com/zygotrip',
      'https://www.instagram.com/zygotrip',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'customer support',
      availableLanguage: ['English', 'Hindi'],
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
