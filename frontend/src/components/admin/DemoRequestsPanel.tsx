'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  ArrowPathIcon,
  CheckIcon,
  ClipboardDocumentIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api, { DemoAccessRequest, DemoLinkResponse } from '@/services/api'

type Status = 'pending' | 'approved' | 'rejected' | 'all'

export default function DemoRequestsPanel() {
  const [status, setStatus] = useState<Status>('pending')
  const [items, setItems] = useState<DemoAccessRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [link, setLink] = useState<DemoLinkResponse | null>(null)
  const [limits, setLimits] = useState({ contracts: 3, llm: 10, hours: 72 })

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listDemoRequests(status)
      setItems(data.items)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Не удалось загрузить заявки')
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => { void load() }, [load])

  const approve = async (item: DemoAccessRequest) => {
    setBusyId(item.id)
    setError('')
    try {
      const result = await api.approveDemoRequest(item.id, {
        max_contracts: limits.contracts,
        max_llm_requests: limits.llm,
        expires_in_hours: limits.hours,
      })
      setLink(result.demo_link)
      await load()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Не удалось одобрить заявку')
    } finally {
      setBusyId(null)
    }
  }

  const reject = async (item: DemoAccessRequest) => {
    if (!window.confirm(`Отклонить заявку ${item.name}?`)) return
    setBusyId(item.id)
    setError('')
    try {
      await api.rejectDemoRequest(item.id)
      await load()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Не удалось отклонить заявку')
    } finally {
      setBusyId(null)
    }
  }

  const copyLink = async () => {
    if (!link) return
    await navigator.clipboard.writeText(link.url)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Заявки на демо</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Одобрение создаёт одноразовую ссылку для указанного email.</p>
        </div>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-dark-600 dark:bg-dark-800 dark:text-gray-300" onClick={() => void load()} title="Обновить заявки" type="button">
          <ArrowPathIcon className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
        </button>
      </div>

      <div className="flex flex-wrap gap-3 border-y border-gray-200 py-4 dark:border-dark-700">
        <LimitInput label="Договоров" max={10} min={1} onChange={(value) => setLimits({ ...limits, contracts: value })} value={limits.contracts} />
        <LimitInput label="AI-запросов" max={100} min={1} onChange={(value) => setLimits({ ...limits, llm: value })} value={limits.llm} />
        <LimitInput label="Часов" max={168} min={1} onChange={(value) => setLimits({ ...limits, hours: value })} value={limits.hours} />
      </div>

      <div className="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-dark-800" aria-label="Статус заявок">
        {([
          ['pending', 'Новые'], ['approved', 'Одобрены'], ['rejected', 'Отклонены'], ['all', 'Все'],
        ] as [Status, string][]).map(([value, label]) => (
          <button
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${status === value ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-700 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}
            key={value}
            onClick={() => setStatus(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {link && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/30">
          <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-200">Персональная ссылка создана</p>
          <div className="mt-2 flex gap-2">
            <input className="min-w-0 flex-1 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-sm text-gray-700" readOnly value={link.url} />
            <button className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-700 text-white hover:bg-emerald-800" onClick={() => void copyLink()} title="Копировать ссылку" type="button">
              <ClipboardDocumentIcon className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</p>}

      {loading ? (
        <p className="py-10 text-center text-sm text-gray-500">Загрузка...</p>
      ) : items.length === 0 ? (
        <p className="border-y border-gray-200 py-10 text-center text-sm text-gray-500 dark:border-dark-700">Заявок с таким статусом нет</p>
      ) : (
        <div className="divide-y divide-gray-200 border-y border-gray-200 dark:divide-dark-700 dark:border-dark-700">
          {items.map((item) => (
            <article className="py-5" key={item.id}>
              <div className="flex flex-col justify-between gap-4 md:flex-row">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h3 className="font-bold text-gray-900 dark:text-gray-100">{item.name}</h3>
                    <span className="text-xs text-gray-400">{new Date(item.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{item.company || 'Компания не указана'}</p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                    <a className="font-medium text-primary-700 hover:underline dark:text-primary-400" href={`mailto:${item.email}`}>{item.email}</a>
                    <span className="text-gray-600 dark:text-gray-300">{item.contact}</span>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-700 dark:text-gray-300">{item.task}</p>
                  {item.demo_link && !item.demo_link.used && (
                    <button className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-primary-700 hover:underline dark:text-primary-400" onClick={() => void navigator.clipboard.writeText(item.demo_link!.url)} type="button">
                      <ClipboardDocumentIcon className="h-4 w-4" aria-hidden="true" /> Копировать активную демо-ссылку
                    </button>
                  )}
                </div>
                {item.status === 'pending' && (
                  <div className="flex shrink-0 gap-2 md:flex-col">
                    <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50" disabled={busyId === item.id} onClick={() => void approve(item)} type="button">
                      <CheckIcon className="h-4 w-4" aria-hidden="true" /> Одобрить
                    </button>
                    <button className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-dark-600 dark:text-gray-300 dark:hover:bg-dark-800" disabled={busyId === item.id} onClick={() => void reject(item)} type="button">
                      <XMarkIcon className="h-4 w-4" aria-hidden="true" /> Отклонить
                    </button>
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

function LimitInput({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
      <span className="mb-1 block">{label}</span>
      <input className="w-28 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-dark-600 dark:bg-dark-800 dark:text-gray-100" max={max} min={min} onChange={(event) => onChange(Number(event.target.value))} type="number" value={value} />
    </label>
  )
}
