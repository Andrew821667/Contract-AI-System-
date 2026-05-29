import type { MetadataRoute } from 'next'

const siteUrl = (process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru').replace(/\/$/, '')

const publicRoutes = ['/', '/pricing', '/demo', '/privacy', '/terms'] as const

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date('2026-05-28T00:00:00.000Z')

  return publicRoutes.map((route) => ({
    url: `${siteUrl}${route === '/' ? '' : route}`,
    lastModified,
    changeFrequency: route === '/' || route === '/pricing' ? 'weekly' : 'monthly',
    priority: route === '/' ? 1 : route === '/pricing' ? 0.9 : 0.6,
  }))
}
