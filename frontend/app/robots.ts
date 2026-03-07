import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com';

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/api/',
          '/account/',
          '/wallet/',
          '/booking/',
          '/payment/',
          '/confirmation/',
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
