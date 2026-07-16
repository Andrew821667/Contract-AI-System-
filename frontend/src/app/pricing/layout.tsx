import type { Metadata } from 'next'
import { pricingFaq } from '@/content/contractSeo'

export const metadata: Metadata = {
  title: 'Тарифы на анализ и проверку договоров с ИИ',
  description: 'Цены Contract AI: персональное демо по заявке, тарифы для юристов и команд, пакеты документов и Enterprise on-premise.',
  alternates: { canonical: '/pricing' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/pricing',
    title: 'Тарифы и форматы запуска | Contract AI System',
    description: 'Бесплатный режим, пакеты, пилот для команды и Enterprise-контур.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Тарифы Contract AI System' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Тарифы и форматы запуска | Contract AI System',
    description: 'Бесплатный режим, пакеты, пилот для команды и Enterprise-контур.',
    images: ['/twitter-image'],
  },
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  const productSchema = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Contract AI by AI Verdict',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    url: 'https://contract.ai-verdict.ru/pricing',
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'RUB',
      lowPrice: '0',
      highPrice: '14990',
      offerCount: '5',
    },
  }
  const faqSchema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: pricingFaq.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  }

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify([productSchema, faqSchema]) }} />
      {children}
    </>
  )
}
