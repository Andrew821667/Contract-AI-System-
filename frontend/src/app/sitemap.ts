import type { MetadataRoute } from 'next'

const siteUrl = (process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru').replace(/\/$/, '')

const publicRoutes = [
  { route: '/', updatedAt: '2026-07-13', changeFrequency: 'weekly', priority: 1 },
  { route: '/pricing', updatedAt: '2026-07-13', changeFrequency: 'monthly', priority: 0.9 },
  { route: '/demo', updatedAt: '2026-07-13', changeFrequency: 'monthly', priority: 0.75 },
  { route: '/privacy', updatedAt: '2026-07-13', changeFrequency: 'yearly', priority: 0.3 },
  { route: '/terms', updatedAt: '2026-07-13', changeFrequency: 'yearly', priority: 0.3 },
] as const

export default function sitemap(): MetadataRoute.Sitemap {
  return publicRoutes.map(({ route, updatedAt, changeFrequency, priority }) => ({
    url: `${siteUrl}${route === '/' ? '' : route}`,
    lastModified: new Date(`${updatedAt}T00:00:00.000Z`),
    changeFrequency,
    priority,
  }))
}
