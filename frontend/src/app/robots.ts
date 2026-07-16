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
          '/admin',
          '/ai',
          '/clauses',
          '/conditions',
          '/contracts',
          '/counterparties',
          '/dashboard',
          '/negotiations',
          '/organization',
          '/revisions',
          '/workflow',
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
    host: siteUrl,
  }
}
