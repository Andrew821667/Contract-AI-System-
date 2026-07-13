/** @type {import('next').NextConfig} */

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
const streamlitUrl = process.env.STREAMLIT_URL || 'http://127.0.0.1:8501'

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  skipTrailingSlashRedirect: true,

  // Enable standalone output for Docker
  output: 'standalone',

  // API proxy
  async rewrites() {
    return [
      {
        source: '/streamlit-admin/:path*',
        destination: `${streamlitUrl}/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },

  // Private application routes must stay out of search while remaining crawlable
  // so bots can observe the X-Robots-Tag directive.
  async headers() {
    const privateRoutes = [
      '/auth/:path*',
      '/login',
      '/register',
      '/dashboard/:path*',
      '/contracts/:path*',
      '/clauses/:path*',
      '/conditions/:path*',
      '/ai/:path*',
      '/negotiations/:path*',
      '/workflow/:path*',
      '/admin/:path*',
      '/organization/:path*',
      '/counterparties/:path*',
      '/revisions/:path*',
      '/streamlit-admin/:path*',
    ]

    return privateRoutes.map((source) => ({
      source,
      headers: [
        {
          key: 'X-Robots-Tag',
          value: 'noindex, nofollow, noarchive',
        },
      ],
    }))
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || '',
  },

  // Optimize images
  images: {
    domains: ['contract-ai.example.com'],
  },
}

module.exports = nextConfig
