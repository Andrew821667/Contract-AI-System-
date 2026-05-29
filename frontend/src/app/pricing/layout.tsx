import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Тарифы',
  description: 'Тарифы Contract AI System, бесплатный лимит и варианты перехода к пилоту или рабочему контуру.',
  alternates: { canonical: '/pricing' },
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
