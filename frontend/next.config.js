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
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        // S7: Proxy Django media files through Next.js to avoid CORS / absolute URL issues
        source: '/media/:path*',
        destination: `${backendUrl}/media/:path*`,
      },
    ];
  },

  images: {
    domains: [
      'localhost',
      '127.0.0.1',
      'res.cloudinary.com',
      'images.unsplash.com',
      'lh3.googleusercontent.com',
      'maps.googleapis.com',
      'picsum.photos',
      'fastly.picsum.photos',
      'tile.openstreetmap.org',
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // Strict mode for development
  reactStrictMode: true,

  // Prevent Next.js from 308-redirecting /api/*/ URLs to /api/* (stripping trailing slash).
  // Django requires trailing slashes on all API endpoints (APPEND_SLASH=True).
  skipTrailingSlashRedirect: true,

  // Required for Docker standalone output (Dockerfile.frontend Stage 3)
  output: 'standalone',
};

module.exports = nextConfig;
