import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Contract AI System',
    short_name: 'Contract AI',
    description: 'Анализ и проверка юридических договоров с ИИ',
    start_url: '/',
    display: 'standalone',
    background_color: '#1e293b',
    theme_color: '#7d6744',
    lang: 'ru',
    icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' }],
  }
}
