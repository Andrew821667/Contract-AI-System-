import type { Metadata } from 'next'
import Link from 'next/link'
import BrandLockup from '@/components/BrandLockup'

export const metadata: Metadata = {
  title: 'Бесплатная проверка договора с ИИ',
  description: 'Как проверить собственный договор в Contract AI: регистрация, загрузка файла, анализ рисков и бесплатный лимит до 3 договоров в месяц.',
  alternates: { canonical: '/demo' },
}

export default function DemoPage() {
  return (
    <main className="brand-surface min-h-screen px-4 py-12 text-slate-100">
      <div className="brand-grid fixed inset-0 pointer-events-none" aria-hidden="true" />
      <article className="brand-panel relative mx-auto w-full max-w-4xl rounded-3xl p-6 md:p-10">
        <div className="text-center">
          <BrandLockup className="mb-6 justify-center" />
          <h1 className="text-3xl font-bold text-white mb-3">
            Бесплатная проверка договора с ИИ
          </h1>
          <p className="mx-auto mb-6 max-w-2xl text-lg leading-relaxed text-slate-300">
            Создайте собственный аккаунт и используйте до 3 договоров бесплатно каждый месяц.
            Публичных тестовых логинов нет: ваши документы и результаты не смешиваются с чужой демо-сессией.
          </p>
          <div className="grid grid-cols-1 gap-3 text-left mb-6">
            {[
              '3 договора бесплатно в месяц',
              'AI-анализ рисков и экспорт DOCX',
              'Без готовых публичных логинов и демо-ролей',
            ].map((text) => (
              <div key={text} className="flex items-center gap-3 rounded-xl border border-cyan-300/10 bg-slate-950/45 px-4 py-3 text-sm text-slate-200">
                <span className="h-2 w-2 rounded-full bg-primary-600" />
                <span>{text}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-col justify-center gap-3 sm:flex-row">
            <Link className="rounded-xl bg-primary-600 px-6 py-3 font-semibold text-white hover:bg-primary-700" href="/register">
              Начать бесплатно
            </Link>
            <Link className="rounded-xl border border-cyan-300/30 px-6 py-3 font-semibold text-cyan-200 hover:bg-cyan-300/10" href="/#login">
              Уже есть аккаунт
            </Link>
          </div>
        </div>

        <section className="mt-12 border-t border-slate-700 pt-10">
          <h2 className="text-2xl font-bold text-white">Как проверить сервис на своем договоре</h2>
          <ol className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              ['1. Зарегистрируйтесь', 'Укажите рабочий email и создайте персональный аккаунт.'],
              ['2. Загрузите документ', 'Используйте договор, который вы вправе передать на автоматизированную обработку.'],
              ['3. Проверьте отчет', 'Сопоставьте найденные риски и рекомендации с позицией ответственного юриста.'],
            ].map(([title, text]) => (
              <li key={title} className="rounded-xl border border-slate-700 bg-slate-950/45 p-5">
                <h3 className="font-semibold text-white">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">{text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-10 grid gap-6 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold text-white">Что оценивать в результате</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-slate-300">
              <li>понятность выделенных условий и уровня риска;</li>
              <li>применимость рекомендаций к позиции вашей стороны;</li>
              <li>экономию времени на первом проходе по документу;</li>
              <li>удобство экспорта и передачи результата коллеге.</li>
            </ul>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">Важное ограничение</h2>
            <p className="mt-4 leading-relaxed text-slate-300">
              Автоматизированный анализ помогает провести первичный обзор, но не гарантирует выявление всех
              юридических, налоговых или коммерческих рисков. Решение о согласовании и подписании договора
              должен принимать пользователь или уполномоченный специалист с учетом фактов конкретной сделки.
            </p>
          </div>
        </section>

        <nav className="mt-10 flex flex-wrap gap-5 border-t border-slate-700 pt-6 text-sm">
          <Link className="font-semibold text-primary-300 hover:text-primary-200" href="/pricing">Посмотреть тарифы</Link>
          <Link className="font-semibold text-primary-300 hover:text-primary-200" href="/privacy">Политика конфиденциальности</Link>
          <Link className="font-semibold text-primary-300 hover:text-primary-200" href="/terms">Условия использования</Link>
        </nav>
      </article>
    </main>
  )
}
