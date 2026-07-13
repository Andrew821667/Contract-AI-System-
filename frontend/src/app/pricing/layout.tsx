import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Тарифы и форматы запуска',
  description: 'Тарифы Contract AI: бесплатный режим до 3 договоров в месяц, пакеты, пилот для команды и Enterprise-контур.',
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
  return children
}
