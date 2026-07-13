import type { Metadata } from 'next'

import HomeClient from './HomeClient'

const siteUrl = (process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru').replace(/\/$/, '')

export const metadata: Metadata = {
  title: { absolute: 'Анализ и проверка договоров с ИИ | Contract AI' },
  description:
    'Contract AI System анализирует договоры, выделяет юридические риски и помогает готовить правки. Бесплатно — до 3 договоров в месяц.',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/',
    title: 'Анализ договоров с ИИ | Contract AI System',
    description: 'Проверка условий, рисков и спорных формулировок в договорах с бесплатным стартом.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System — анализ договоров с ИИ' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Анализ договоров с ИИ | Contract AI System',
    description: 'Проверка условий, рисков и спорных формулировок в договорах с бесплатным стартом.',
    images: ['/twitter-image'],
  },
}

const softwareSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  '@id': `${siteUrl}/#application`,
  name: 'Contract AI System',
  url: siteUrl,
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  inLanguage: 'ru-RU',
  description:
    'Веб-сервис для анализа, подготовки и управления юридическими договорами с использованием ИИ.',
  featureList: [
    'Анализ условий и юридических рисков',
    'Комментарии и рекомендации по правкам',
    'Сравнение версий договоров',
    'Экспорт результатов анализа',
  ],
  offers: {
    '@type': 'Offer',
    name: 'Бесплатный режим',
    price: '0',
    priceCurrency: 'RUB',
    description: 'До 3 договоров в месяц.',
  },
  provider: {
    '@type': 'Organization',
    name: 'AI Verdict',
    url: 'https://ai-verdict.ru',
  },
}

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareSchema) }}
      />
      <HomeClient />
    </>
  )
}
