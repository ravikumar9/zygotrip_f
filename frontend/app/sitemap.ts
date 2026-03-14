import type { MetadataRoute } from 'next';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

// Top cities for SEO landing pages — expand as API coverage grows
const TOP_CITIES = [
  'goa', 'jaipur', 'manali', 'mumbai', 'bangalore', 'udaipur',
  'delhi', 'hyderabad', 'chennai', 'kolkata', 'shimla', 'ooty',
  'pondicherry', 'varanasi', 'agra', 'kochi', 'mysore', 'darjeeling',
  'rishikesh', 'amritsar', 'jodhpur', 'mount-abu', 'nainital', 'mussoorie',
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL, lastModified: now, changeFrequency: 'daily', priority: 1.0 },
    { url: `${SITE_URL}/hotels`, lastModified: now, changeFrequency: 'daily', priority: 0.9 },
    { url: `${SITE_URL}/buses`, lastModified: now, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/cabs`, lastModified: now, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/packages`, lastModified: now, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/privacy`, lastModified: now, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/terms`, lastModified: now, changeFrequency: 'yearly', priority: 0.3 },
  ];

  // City landing pages — high SEO value
  const cityPages: MetadataRoute.Sitemap = TOP_CITIES.map((city) => ({
    url: `${SITE_URL}/hotels/${city}`,
    lastModified: now,
    changeFrequency: 'daily' as const,
    priority: 0.85,
  }));

  // Dynamic hotel pages — fetch all property slugs from the API
  let hotelPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API_BASE}/properties/?page_size=500&fields=slug,updated_at`, {
      next: { revalidate: 3600 }, // revalidate hourly
    });
    if (res.ok) {
      const json = await res.json();
      const results = json?.data?.results ?? json?.results ?? [];
      hotelPages = results
        .filter((h: { slug?: string }) => h.slug)
        .map((h: { slug: string; updated_at?: string }) => ({
          url: `${SITE_URL}/hotels/${h.slug}`,
          lastModified: h.updated_at ? new Date(h.updated_at) : now,
          changeFrequency: 'daily' as const,
          priority: 0.75,
        }));
    }
  } catch {
    // Silently fail — sitemap will have static pages only
  }

  return [...staticPages, ...cityPages, ...hotelPages];
}
