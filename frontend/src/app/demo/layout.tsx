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
  const howToSchema = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: 'Как бесплатно проверить договор с помощью ИИ',
    description: 'Регистрация, загрузка договора и проверка отчета Contract AI.',
    totalTime: 'PT10M',
    step: [
      { '@type': 'HowToStep', position: 1, name: 'Зарегистрируйтесь', text: 'Укажите рабочий email и создайте персональный аккаунт.' },
      { '@type': 'HowToStep', position: 2, name: 'Загрузите договор', text: 'Загрузите PDF, DOCX или XML, который вы вправе передать на обработку.' },
      { '@type': 'HowToStep', position: 3, name: 'Проверьте отчет', text: 'Сопоставьте найденные риски и рекомендации с позицией ответственного юриста.' },
    ],
  }

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }} />
      {children}
    </>
  )
}
