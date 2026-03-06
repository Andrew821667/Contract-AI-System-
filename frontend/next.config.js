/** @type {import('next').NextConfig} */

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Enable standalone output for Docker
  output: 'standalone',

  // API proxy
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },

  // Optimize images
  images: {
    domains: ['contract-ai.example.com'],
  },
}

module.exports = nextConfig
