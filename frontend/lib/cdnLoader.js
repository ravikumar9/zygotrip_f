/**
 * CDN Image Loader for Next.js
 *
 * Activated when NEXT_PUBLIC_CDN_URL is set in the environment.
 * Transforms Next.js <Image> src URLs to CDN-hosted URLs so images
 * are served from CloudFront / Cloudflare edge nodes instead of the
 * Next.js image optimization server.
 *
 * How it works:
 *   1. Next.js calls this loader for every <Image> component
 *   2. Loader constructs the CDN URL: {CDN_URL}/media/{path}?w={width}&q={quality}
 *   3. CloudFront caches the response at the edge (TTL from Cache-Control)
 *   4. S3 / Django media serves as the CDN origin
 *
 * Setup (production):
 *   NEXT_PUBLIC_CDN_URL=https://cdn.zygotrip.com
 *   NEXT_PUBLIC_S3_BUCKET=zygotrip-media   (optional, for S3 direct)
 *
 * CDN Cache-Control recommendation (CloudFront behavior):
 *   - Images:  Cache-Control: public, max-age=31536000, immutable
 *   - Media:   Cache-Control: public, max-age=86400, s-maxage=2592000
 *
 * @see https://nextjs.org/docs/app/api-reference/components/image#loader
 */

const CDN_URL = process.env.NEXT_PUBLIC_CDN_URL || '';

/**
 * @param {{ src: string, width: number, quality?: number }} params
 * @returns {string} Full CDN URL for the image
 */
export default function cdnLoader({ src, width, quality = 75 }) {
  // If src is already an absolute URL (external), return as-is
  if (src.startsWith('http://') || src.startsWith('https://')) {
    // For external URLs, append width hint as a query param
    // CloudFront Lambda@Edge can use this to serve pre-resized variants
    const url = new URL(src);
    url.searchParams.set('w', String(width));
    url.searchParams.set('q', String(quality));
    return url.toString();
  }

  // Internal media path (e.g. /media/properties/photo.jpg)
  // → https://cdn.zygotrip.com/media/properties/photo.jpg?w=800&q=75
  const cleanSrc = src.startsWith('/') ? src : `/${src}`;
  const params = new URLSearchParams({
    w: String(width),
    q: String(quality),
  });

  return `${CDN_URL}${cleanSrc}?${params.toString()}`;
}
