import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Бесплатный режим',
  description: 'Бесплатный режим Contract AI System: 3 договора в месяц для проверки системы.',
  alternates: { canonical: '/demo' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/demo',
    title: 'Бесплатный анализ договоров | Contract AI System',
    description: 'Проверьте до 3 договоров в месяц и оцените формат отчета на собственных документах.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Бесплатный анализ договоров | Contract AI System',
    description: 'До 3 договоров в месяц для проверки системы.',
    images: ['/twitter-image'],
  },
}

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children
}
