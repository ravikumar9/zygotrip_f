const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: '**.unsplash.com' },
      { protocol: 'https', hostname: 'images.pexels.com' },
      { protocol: 'https', hostname: '**.pexels.com' },
      { protocol: 'https', hostname: 'goexplorer-dev.cloud' },
      { protocol: 'http', hostname: '72.61.113.50' },
      { protocol: 'https', hostname: '**.amazonaws.com' },
      { protocol: 'https', hostname: '**.cloudinary.com' },
    ],
    minimumCacheTTL: 86400,
  },
  async rewrites() {
    // Proxy /api/* to Django backend — eliminates CORS issues
    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
