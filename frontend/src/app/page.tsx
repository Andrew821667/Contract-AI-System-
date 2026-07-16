import type { Metadata } from 'next'

import HomeClient from './HomeClient'
import { contractFaq } from '@/content/contractSeo'

const siteUrl = (process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru').replace(/\/$/, '')

export const metadata: Metadata = {
  title: { absolute: 'Анализ и проверка договоров с ИИ | Contract AI' },
  description:
    'Нейросеть Contract AI анализирует и проверяет договоры, выделяет юридические риски и предлагает правки. Персональное демо доступно по заявке.',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/',
    title: 'Анализ договоров с ИИ | Contract AI System',
    description: 'Проверка условий, рисков и спорных формулировок в договорах. Персональное демо по заявке.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System — анализ договоров с ИИ' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Анализ договоров с ИИ | Contract AI System',
    description: 'Проверка условий, рисков и спорных формулировок в договорах. Персональное демо по заявке.',
    images: ['/twitter-image'],
  },
}

const softwareSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  '@id': `${siteUrl}/#application`,
  name: 'Contract AI by AI Verdict',
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
  provider: {
    '@type': 'Organization',
    name: 'AI Verdict',
    url: 'https://ai-verdict.ru',
  },
}

const websiteSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  '@id': `${siteUrl}/#website`,
  name: 'Contract AI by AI Verdict',
  alternateName: 'Contract AI System',
  url: siteUrl,
  inLanguage: 'ru-RU',
  publisher: {
    '@type': 'Organization',
    '@id': 'https://ai-verdict.ru/#organization',
    name: 'AI Verdict',
    url: 'https://ai-verdict.ru',
  },
}

const faqSchema = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: contractFaq.map((item) => ({
    '@type': 'Question',
    name: item.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: item.answer,
    },
  })),
}

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify([softwareSchema, websiteSchema, faqSchema]) }}
      />
      <HomeClient />
    </>
  )
}
