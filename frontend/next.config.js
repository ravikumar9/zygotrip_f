/** @type {import('next').NextConfig} */
const nextConfig = {
  /**
   * Rewrite /api/* and /media/* → Django backend.
   *
   * IMPORTANT: Hard-code 127.0.0.1 (IPv4 loopback), NOT 'localhost'.
   * On Windows, 'localhost' can resolve to ::1 (IPv6) while Django
   * only binds to 127.0.0.1, causing "ECONNREFUSED" errors.
   *
   * For production deployment override the destination with the
   * BACKEND_URL env variable (server-side only — not NEXT_PUBLIC).
   *
   * S7 — Media reliability:
   *   /media/:path* rewrites to Django MEDIA_ROOT serving.
   *   This ensures uploaded room/property images load via the same-origin
   *   proxy instead of requiring direct Django access.
   */
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    return {
      // beforeFiles rewrites run before filesystem/page routes,
      // guaranteeing /api/* always proxies to Django.
      beforeFiles: [
        {
          // Trailing-slash variant — Django requires trailing slashes (APPEND_SLASH)
          source: '/api/:path*/',
          destination: `${backendUrl}/api/:path*/`,
        },
        {
          // Non-trailing-slash variant — forward and let Django redirect
          source: '/api/:path*',
          destination: `${backendUrl}/api/:path*`,
        },
        {
          // Proxy /search/api/* (track-click, nearby, autocomplete) → Django
          // HotelCard.tsx sendBeacon calls /search/api/track-click/
          source: '/search/api/:path*/',
          destination: `${backendUrl}/search/api/:path*/`,
        },
        {
          source: '/search/api/:path*',
          destination: `${backendUrl}/search/api/:path*`,
        },
        {
          source: '/media/:path*',
          destination: `${backendUrl}/media/:path*`,
        },
      ],
    };
  },

  /**
   * Security headers — production-grade HTTP security.
   * These protect against XSS, clickjacking, MIME sniffing, and info leakage.
   * Includes edge-level caching headers for static assets.
   */
  async headers() {
    return [
      {
        // Apply security headers to all routes
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(self), interest-cohort=()' },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
      {
        // Edge caching for hotel listing pages (stale-while-revalidate)
        source: '/hotels',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, s-maxage=60, stale-while-revalidate=300',
          },
        ],
      },
      {
        // Edge caching for city landing pages
        source: '/hotels/in/:location*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, s-maxage=300, stale-while-revalidate=600',
          },
        ],
      },
      {
        // Long cache for static image assets
        source: '/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        // Cache _next/image optimized images at edge
        source: '/_next/image(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=86400, stale-while-revalidate=86400',
          },
        ],
      },
    ];
  },

  images: {
    // ── CDN loader (production) ──────────────────────────────────────────────
    // Set NEXT_PUBLIC_CDN_URL=https://cdn.zygotrip.com in .env.production to
    // route all <Image> src through CloudFront / Cloudflare edge cache.
    // Leave unset in dev — falls back to built-in Next.js image optimizer.
    ...(process.env.NEXT_PUBLIC_CDN_URL
      ? { loader: 'custom', loaderFile: './lib/cdnLoader.js' }
      : {}
    ),

    // Allowed remote image origins (applies to built-in optimizer)
    remotePatterns: [
      { protocol: 'http',  hostname: 'localhost' },
      { protocol: 'http',  hostname: '127.0.0.1' },
      { protocol: 'http',  hostname: '127.0.0.1', port: '8000' },
      // CDN hostname (CloudFront / Cloudflare)
      ...(process.env.NEXT_PUBLIC_CDN_URL
        ? [{ protocol: 'https', hostname: new URL(process.env.NEXT_PUBLIC_CDN_URL).hostname }]
        : []
      ),
      // S3 bucket direct (staging / backup)
      ...(process.env.NEXT_PUBLIC_S3_BUCKET
        ? [{ protocol: 'https', hostname: `${process.env.NEXT_PUBLIC_S3_BUCKET}.s3.amazonaws.com` }]
        : []
      ),
      // Third-party image origins
      { protocol: 'https', hostname: 'res.cloudinary.com' },
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
      { protocol: 'https', hostname: 'maps.googleapis.com' },
      { protocol: 'https', hostname: 'picsum.photos' },
      { protocol: 'https', hostname: 'fastly.picsum.photos' },
    ],
    formats: ['image/avif', 'image/webp'],
    // Standard breakpoints — mobile / tablet / desktop / retina
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    // Minimize re-optimization on CDN — 1-day minimum TTL
    minimumCacheTTL: 86400,
  },

  // Strict mode for development
  reactStrictMode: true,

  // Prevent Next.js from 308-redirecting /api/*/ URLs to /api/* (stripping trailing slash).
  // Django requires trailing slashes on all API endpoints (APPEND_SLASH=True).
  skipTrailingSlashRedirect: true,

  // Required for Docker standalone output (Dockerfile.frontend Stage 3)
  output: 'standalone',

  // Powered-by header reveals framework — remove for security
  poweredByHeader: false,

  // Compress responses for smaller payloads
  compress: true,
};

module.exports = nextConfig;
