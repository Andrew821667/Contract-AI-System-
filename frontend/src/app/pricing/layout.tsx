import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Тарифы',
  description: 'Тарифы Contract AI System, бесплатный лимит и варианты перехода к пилоту или рабочему контуру.',
  alternates: { canonical: '/pricing' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/pricing',
    title: 'Тарифы | Contract AI System',
    description: 'Бесплатный лимит и тарифы для юриста, команды и компании.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Тарифы Contract AI System' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Тарифы | Contract AI System',
    description: 'Бесплатный лимит и тарифы для юриста, команды и компании.',
    images: ['/twitter-image'],
  },
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
