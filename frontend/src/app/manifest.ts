import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Contract AI by AI Verdict',
    short_name: 'Contract AI',
    description: 'Анализ и проверка юридических договоров с ИИ',
    start_url: '/',
    display: 'standalone',
    background_color: '#08111f',
    theme_color: '#0a1423',
    lang: 'ru',
    icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' }],
  }
}
