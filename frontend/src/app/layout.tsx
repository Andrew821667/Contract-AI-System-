import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const inter = Inter({
  subsets: ['latin', 'cyrillic'],
  display: 'swap',
  preload: false,
})

const siteUrl = new URL(process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru')

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: {
    default: 'Contract AI — договорная система AI Verdict',
    template: '%s | Contract AI',
  },
  description: 'Анализ, проверка, подготовка и согласование договоров с ИИ в системе AI Verdict.',
  applicationName: 'Contract AI by AI Verdict',
  authors: [{ name: 'AI Verdict', url: 'https://ai-verdict.ru' }],
  creator: 'AI Verdict',
  publisher: 'AI Verdict',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    url: '/',
    siteName: 'Contract AI by AI Verdict',
    title: 'Contract AI — договорная система AI Verdict',
    description: 'Анализ, проверка, подготовка и согласование договоров с ИИ.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System — анализ договоров с ИИ' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Contract AI — договорная система AI Verdict',
    description: 'Анализ, проверка, подготовка и согласование договоров с ИИ.',
    images: ['/twitter-image'],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('theme') || 'light';
                  var dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                  if (dark) document.documentElement.classList.add('dark');
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className={inter.className}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
