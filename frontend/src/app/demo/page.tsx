import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Бесплатная проверка договора с ИИ',
  description: 'Как проверить собственный договор в Contract AI: регистрация, загрузка файла, анализ рисков и бесплатный лимит до 3 договоров в месяц.',
  alternates: { canonical: '/demo' },
}

export default function DemoPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20 px-4 py-12">
      <article className="mx-auto w-full max-w-4xl rounded-3xl border border-stone-200 bg-white p-6 shadow-xl md:p-10">
        <div className="text-center">
          <div className="w-16 h-16 bg-primary-600 rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-5">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-stone-800 mb-3">
            Бесплатный режим Contract AI
          </h1>
          <p className="mx-auto mb-6 max-w-2xl text-lg leading-relaxed text-gray-600">
            Создайте собственный аккаунт и используйте до 3 договоров бесплатно каждый месяц.
            Публичных тестовых логинов нет: ваши документы и результаты не смешиваются с чужой демо-сессией.
          </p>
          <div className="grid grid-cols-1 gap-3 text-left mb-6">
            {[
              '3 договора бесплатно в месяц',
              'AI-анализ рисков и экспорт DOCX',
              'Без готовых публичных логинов и демо-ролей',
            ].map((text) => (
              <div key={text} className="flex items-center gap-3 rounded-xl bg-primary-50 px-4 py-3 text-sm text-primary-900">
                <span className="h-2 w-2 rounded-full bg-primary-600" />
                <span>{text}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-col justify-center gap-3 sm:flex-row">
            <Link className="rounded-xl bg-primary-600 px-6 py-3 font-semibold text-white hover:bg-primary-700" href="/register">
              Начать бесплатно
            </Link>
            <Link className="rounded-xl border border-primary-600 px-6 py-3 font-semibold text-primary-700 hover:bg-primary-50" href="/#login">
              Уже есть аккаунт
            </Link>
          </div>
        </div>

        <section className="mt-12 border-t border-stone-200 pt-10">
          <h2 className="text-2xl font-bold text-stone-800">Как проверить сервис на своем договоре</h2>
          <ol className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              ['1. Зарегистрируйтесь', 'Укажите рабочий email и создайте персональный аккаунт.'],
              ['2. Загрузите документ', 'Используйте договор, который вы вправе передать на автоматизированную обработку.'],
              ['3. Проверьте отчет', 'Сопоставьте найденные риски и рекомендации с позицией ответственного юриста.'],
            ].map(([title, text]) => (
              <li key={title} className="rounded-xl bg-stone-50 p-5">
                <h3 className="font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-600">{text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-10 grid gap-6 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold text-stone-800">Что оценивать в результате</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-stone-600">
              <li>понятность выделенных условий и уровня риска;</li>
              <li>применимость рекомендаций к позиции вашей стороны;</li>
              <li>экономию времени на первом проходе по документу;</li>
              <li>удобство экспорта и передачи результата коллеге.</li>
            </ul>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-stone-800">Важное ограничение</h2>
            <p className="mt-4 leading-relaxed text-stone-600">
              Автоматизированный анализ помогает провести первичный обзор, но не гарантирует выявление всех
              юридических, налоговых или коммерческих рисков. Решение о согласовании и подписании договора
              должен принимать пользователь или уполномоченный специалист с учетом фактов конкретной сделки.
            </p>
          </div>
        </section>

        <nav className="mt-10 flex flex-wrap gap-5 border-t border-stone-200 pt-6 text-sm">
          <Link className="font-semibold text-primary-700 hover:text-primary-900" href="/pricing">Посмотреть тарифы</Link>
          <Link className="font-semibold text-primary-700 hover:text-primary-900" href="/privacy">Политика конфиденциальности</Link>
          <Link className="font-semibold text-primary-700 hover:text-primary-900" href="/terms">Условия использования</Link>
        </nav>
      </article>
    </main>
  )
}
