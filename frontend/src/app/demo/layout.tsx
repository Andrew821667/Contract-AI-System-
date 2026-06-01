import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Бесплатный режим',
  description: 'Бесплатный режим Contract AI System: 3 договора в месяц для проверки системы.',
  alternates: { canonical: '/demo' },
}

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children
}
