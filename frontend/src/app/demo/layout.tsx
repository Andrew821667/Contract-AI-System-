import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Персональный демо-доступ',
  description: 'Запросите персональный ограниченный доступ к Contract AI для проверки собственной договорной задачи.',
  alternates: { canonical: '/demo' },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/demo',
    title: 'Персональный демо-доступ | Contract AI System',
    description: 'Опишите договорную задачу и получите персональную ссылку на ограниченное демо Contract AI.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Персональный демо-доступ | Contract AI System',
    description: 'Демо Contract AI по заявке для проверки собственного сценария.',
    images: ['/twitter-image'],
  },
}

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  const howToSchema = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: 'Как получить демо-доступ к анализу договоров с ИИ',
    description: 'Заявка, персональная ссылка и проверка отчета Contract AI.',
    totalTime: 'PT10M',
    step: [
      { '@type': 'HowToStep', position: 1, name: 'Опишите задачу', text: 'Оставьте контакт и кратко опишите договорный процесс.' },
      { '@type': 'HowToStep', position: 2, name: 'Получите приглашение', text: 'После проверки задачи мы направим персональную ограниченную ссылку.' },
      { '@type': 'HowToStep', position: 3, name: 'Проверьте отчет', text: 'Загрузите свой документ и оцените найденные риски и рекомендации.' },
    ],
  }

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }} />
      {children}
    </>
  )
}
