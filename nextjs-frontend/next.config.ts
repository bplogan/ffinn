import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  async redirects() {
    return [
      // The homepage lives at /; keep old /home links and bookmarks working.
      { source: '/home', destination: '/', permanent: true },
      // Canonicalise to bare domain — www → ffinn.ca (permanent 301)
      {
        source: '/:path*',
        has: [{ type: 'host', value: 'www.ffinn.ca' }],
        destination: 'https://ffinn.ca/:path*',
        permanent: true,
      },
    ]
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
      {
        source: '/uploads/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/uploads/:path*`,
      },
    ]
  },
  images: {
    // Restrict the Next image optimizer to known hosts to prevent the /_next/image
    // route from being abused as an open image proxy / SSRF vector / bandwidth sink.
    remotePatterns: [
      { protocol: 'https', hostname: '*.blob.core.windows.net' },
      { protocol: 'https', hostname: '*.azurestaticapps.net' },
      { protocol: 'https', hostname: 'ffinn.ca' },
      { protocol: 'https', hostname: 'www.ffinn.ca' },
      { protocol: 'https', hostname: 'www.gravatar.com' },
      { protocol: 'https', hostname: 'avatars.githubusercontent.com' },
    ],
  },
}

export default nextConfig
