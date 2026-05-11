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
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
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
