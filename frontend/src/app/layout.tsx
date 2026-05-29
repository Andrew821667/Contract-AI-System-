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
    default: 'Contract AI System',
    template: '%s | Contract AI System',
  },
  description: 'Интеллектуальная система для автоматизации работы с договорами',
  applicationName: 'Contract AI System',
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
    siteName: 'Contract AI System',
    title: 'Contract AI System',
    description: 'Интеллектуальная система для автоматизации работы с договорами',
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
                  var theme = localStorage.getItem('theme') || 'system';
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
