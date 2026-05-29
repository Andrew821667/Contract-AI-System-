import type { MetadataRoute } from 'next'

const siteUrl = (process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru').replace(/\/$/, '')

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/api/',
          '/auth/',
          '/login',
          '/register',
          '/dashboard/',
          '/contracts/',
          '/clauses/',
          '/conditions/',
          '/ai/',
          '/negotiations/',
          '/workflow/',
          '/admin/',
          '/organization/',
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
    host: siteUrl,
  }
}
