import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Условия использования',
  description: 'Условия использования Contract AI System: демо-доступ, ограничения, ответственность и правила работы с договорами.',
  alternates: { canonical: '/terms' },
  openGraph: {
    type: 'article',
    locale: 'ru_RU',
    siteName: 'Contract AI System',
    url: '/terms',
    title: 'Условия использования | Contract AI System',
    description: 'Демо-доступ, ограничения ответственности и правила работы с договорами.',
    images: [{ url: '/opengraph-image', width: 1200, height: 630, alt: 'Contract AI System' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Условия использования | Contract AI System',
    description: 'Демо-доступ, ограничения ответственности и правила работы с договорами.',
    images: ['/twitter-image'],
  },
}

const sections = [
  {
    title: '1. Назначение сервиса',
    paragraphs: [
      'Contract AI System помогает загружать, анализировать и готовить договорные документы с использованием автоматизированных инструментов и AI-моделей.',
      'Результаты анализа носят информационный и вспомогательный характер. Они не заменяют индивидуальную юридическую консультацию по конкретной ситуации.',
    ],
  },
  {
    title: '2. Персональный демо-доступ',
    paragraphs: [
      'Демо-доступ предоставляется по заявке после проверки задачи. Публичная самостоятельная регистрация для демо не предусмотрена.',
      'Срок, количество договоров и AI-запросов указываются в персональном приглашении. После исчерпания лимита дальнейшая работа обсуждается в формате пилота, рабочего контура или отдельного соглашения.',
    ],
  },
  {
    title: '3. Правила загрузки документов',
    paragraphs: [
      'Пользователь отвечает за законность загрузки документов и наличие необходимых прав на их обработку.',
      'Запрещается загружать вредоносные файлы, документы с незаконным содержанием или материалы, обработка которых требует специального режима защиты без отдельного согласования.',
    ],
  },
  {
    title: '4. Ограничение ответственности',
    paragraphs: [
      'Сервис не гарантирует выявление всех юридических, финансовых, налоговых или коммерческих рисков в договоре.',
      'Окончательное решение по подписанию, изменению или отклонению договора принимает пользователь или его уполномоченный специалист.',
    ],
  },
  {
    title: '5. Изменение условий',
    paragraphs: [
      'Условия могут обновляться при развитии продукта, изменении лимитов, появлении новых функций или изменении правовых требований.',
      'Актуальная версия условий публикуется на этой странице и применяется с момента размещения, если не указано иное.',
    ],
  },
]

export default function TermsPage() {
  return (
    <main className="brand-surface brand-photo brand-auth min-h-screen px-4 py-12">
      <div className="brand-grid fixed inset-0 pointer-events-none" aria-hidden="true" />
      <div className="relative max-w-4xl mx-auto">
        <Link href="/" className="inline-flex items-center text-primary-700 hover:text-primary-800 font-semibold mb-8">
          ← На главную Contract AI
        </Link>
        <article className="brand-panel rounded-2xl p-6 md:p-10">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary-300 mb-3">
            Legal
          </p>
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-5">
            Условия использования
          </h1>
          <p className="text-slate-600 text-lg mb-8">
            Настоящие Условия регулируют использование Contract AI System, включая демо-доступ,
            загрузку документов, получение отчетов и переход к пилоту или рабочему контуру.
          </p>
          <div className="space-y-8">
            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-2xl font-bold text-slate-900 mb-3">{section.title}</h2>
                <div className="space-y-3 text-slate-600 leading-relaxed">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
          <div className="mt-10 pt-6 border-t border-slate-700 text-sm text-stone-400">
            Актуальная редакция: 16 июля 2026 года.
          </div>
        </article>
      </div>
    </main>
  )
}
