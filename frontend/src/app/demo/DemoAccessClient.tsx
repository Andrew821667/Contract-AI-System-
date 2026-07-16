'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRightIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import BrandLockup from '@/components/BrandLockup'
import api from '@/services/api'

type RequestForm = {
  name: string
  email: string
  contact: string
  company: string
  task: string
  consent: boolean
  website: string
}

const initialForm: RequestForm = {
  name: '', email: '', contact: '', company: '', task: '', consent: false, website: '',
}

export default function DemoAccessClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token')?.trim() || ''
  const [form, setForm] = useState(initialForm)
  const [activation, setActivation] = useState({ name: '', email: '' })
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const submitRequest = async (event: FormEvent) => {
    event.preventDefault()
    if (!form.consent) return
    setLoading(true)
    setError('')
    try {
      await api.requestDemo({
        name: form.name,
        email: form.email,
        contact: form.contact,
        company: form.company || undefined,
        task: form.task,
        consent: true,
        website: form.website,
      })
      setSubmitted(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Не удалось отправить заявку. Попробуйте ещё раз.')
    } finally {
      setLoading(false)
    }
  }

  const activate = async (event: FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await api.activateDemo({ token, name: activation.name, email: activation.email })
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Ссылка недействительна или срок её действия истёк.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="brand-surface brand-photo brand-auth min-h-screen px-4 py-8 text-slate-900 md:py-12">
      <div className="brand-grid fixed inset-0 pointer-events-none" aria-hidden="true" />
      <div className="relative mx-auto max-w-6xl">
        <header className="mb-8 flex items-center justify-between gap-4">
          <BrandLockup />
          <Link className="text-sm font-semibold text-primary-700 hover:text-primary-800" href="/#login">Войти</Link>
        </header>

        <div className="grid items-start gap-10 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="pt-2 lg:pt-8">
            <p className="mb-3 text-sm font-semibold uppercase text-primary-700">Персональное демо Contract AI</p>
            <h1 className="max-w-xl text-4xl font-bold leading-tight text-slate-900 md:text-5xl">
              Проверьте систему на своей договорной задаче
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-700">
              Коротко опишите задачу и оставьте удобный контакт. Мы проверим, подходит ли сценарий,
              и выдадим персональную ссылку с ограниченным сроком и объёмом использования.
            </p>
            <ol className="mt-8 space-y-4 text-slate-700">
              {[
                'Вы описываете процесс или тип договоров.',
                'Мы уточняем детали и подтверждаем демо-доступ.',
                'Вы тестируете анализ на собственном документе.',
              ].map((item, index) => (
                <li className="flex gap-3" key={item}>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-800">{index + 1}</span>
                  <span className="pt-0.5">{item}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="brand-panel rounded-lg border border-slate-300 bg-white/95 p-6 shadow-xl md:p-8">
            {token ? (
              <form className="space-y-5" onSubmit={activate}>
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">Активировать демо-доступ</h2>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">Укажите тот же email, на который была оформлена персональная ссылка.</p>
                </div>
                <Field label="Имя" required>
                  <input autoComplete="name" className="field-input" maxLength={255} minLength={2} onChange={(e) => setActivation({ ...activation, name: e.target.value })} required value={activation.name} />
                </Field>
                <Field label="Рабочий email" required>
                  <input autoComplete="email" className="field-input" onChange={(e) => setActivation({ ...activation, email: e.target.value })} required type="email" value={activation.email} />
                </Field>
                {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
                <SubmitButton loading={loading} label="Активировать и войти" />
              </form>
            ) : submitted ? (
              <div className="py-8 text-center">
                <CheckCircleIcon className="mx-auto h-14 w-14 text-emerald-600" aria-hidden="true" />
                <h2 className="mt-5 text-2xl font-bold text-slate-900">Заявка принята</h2>
                <p className="mx-auto mt-3 max-w-md leading-relaxed text-slate-600">
                  Мы посмотрим задачу и свяжемся с вами по указанному контакту. Аккаунт автоматически не создаётся.
                </p>
                <Link className="mt-6 inline-block font-semibold text-primary-700 hover:text-primary-800" href="/">Вернуться на главную</Link>
              </div>
            ) : (
              <form className="space-y-5" onSubmit={submitRequest}>
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">Запросить демо-доступ</h2>
                  <p className="mt-2 text-sm text-slate-600">Ответим лично и без автоматической регистрации.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Имя" required>
                    <input className="field-input" maxLength={255} minLength={2} onChange={(e) => setForm({ ...form, name: e.target.value })} required value={form.name} />
                  </Field>
                  <Field label="Рабочий email" required>
                    <input className="field-input" onChange={(e) => setForm({ ...form, email: e.target.value })} required type="email" value={form.email} />
                  </Field>
                  <Field label="Телефон или Telegram" required>
                    <input className="field-input" maxLength={255} onChange={(e) => setForm({ ...form, contact: e.target.value })} required value={form.contact} />
                  </Field>
                  <Field label="Компания и роль">
                    <input className="field-input" maxLength={255} onChange={(e) => setForm({ ...form, company: e.target.value })} value={form.company} />
                  </Field>
                </div>
                <Field label="Какую задачу хотите проверить" required>
                  <textarea
                    className="field-input min-h-32 resize-y"
                    maxLength={4000}
                    minLength={20}
                    onChange={(e) => setForm({ ...form, task: e.target.value })}
                    placeholder="Например: проверяем договоры поставки со стороны покупателя и хотим быстрее находить отклонения от нашей позиции."
                    required
                    value={form.task}
                  />
                </Field>
                <div className="hidden" aria-hidden="true">
                  <label htmlFor="website">Сайт</label>
                  <input id="website" onChange={(e) => setForm({ ...form, website: e.target.value })} tabIndex={-1} value={form.website} />
                </div>
                <label className="flex items-start gap-3 text-sm leading-relaxed text-slate-600">
                  <input checked={form.consent} className="mt-1 h-4 w-4 rounded border-slate-400 text-primary-600 focus:ring-primary-500" onChange={(e) => setForm({ ...form, consent: e.target.checked })} required type="checkbox" />
                  <span>
                    Согласен на обработку данных для ответа на заявку согласно{' '}
                    <Link className="font-semibold text-primary-700 hover:underline" href="/privacy">политике конфиденциальности</Link>.
                  </span>
                </label>
                {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
                <SubmitButton loading={loading} label="Отправить заявку" />
              </form>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block text-sm font-semibold text-slate-700">
      <span className="mb-1.5 block">{label}{required ? ' *' : ''}</span>
      {children}
    </label>
  )
}

function SubmitButton({ loading, label }: { loading: boolean; label: string }) {
  return (
    <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary-700 px-5 py-3 font-semibold text-white transition hover:bg-primary-800 disabled:cursor-wait disabled:opacity-60" disabled={loading} type="submit">
      <span>{loading ? 'Отправляем...' : label}</span>
      {!loading && <ArrowRightIcon className="h-5 w-5" aria-hidden="true" />}
    </button>
  )
}
