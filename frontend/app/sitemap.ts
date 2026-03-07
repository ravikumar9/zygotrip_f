import type { MetadataRoute } from 'next';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL, lastModified: new Date(), changeFrequency: 'daily', priority: 1.0 },
    { url: `${SITE_URL}/hotels`, lastModified: new Date(), changeFrequency: 'daily', priority: 0.9 },
    { url: `${SITE_URL}/buses`, lastModified: new Date(), changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/cabs`, lastModified: new Date(), changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/packages`, lastModified: new Date(), changeFrequency: 'weekly', priority: 0.7 },
    { url: `${SITE_URL}/privacy`, lastModified: new Date(), changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/terms`, lastModified: new Date(), changeFrequency: 'yearly', priority: 0.3 },
  ];

  // Dynamic hotel pages — fetch all property slugs from the API
  let hotelPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API_BASE}/properties/?page_size=500&fields=slug`, {
      next: { revalidate: 86400 }, // revalidate daily
    });
    if (res.ok) {
      const json = await res.json();
      const results = json?.data?.results ?? json?.results ?? [];
      hotelPages = results
        .filter((h: { slug?: string }) => h.slug)
        .map((h: { slug: string }) => ({
          url: `${SITE_URL}/hotels/${h.slug}`,
          lastModified: new Date(),
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        }));
    }
  } catch {
    // Silently fail — sitemap will have static pages only
  }

  return [...staticPages, ...hotelPages];
}
