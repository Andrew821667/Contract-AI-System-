import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Демо',
  description: 'Демо Contract AI System: как сервис помогает анализировать договоры и готовить отчеты по рискам.',
  alternates: { canonical: '/demo' },
}

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children
}
