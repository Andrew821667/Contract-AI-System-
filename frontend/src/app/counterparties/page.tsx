'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import api, {
  Counterparty,
  CounterpartyCreate,
  CounterpartyTypeOption,
} from '@/services/api'
import AppLayout from '@/components/AppLayout'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import { useAuthGuard } from '@/hooks/useAuthGuard'

type FormState = CounterpartyCreate

const EMPTY_FORM: FormState = {
  type: 'legal',
  name: '',
  short_name: '',
  inn: '',
  kpp: '',
  ogrn: '',
  legal_address: '',
  contact_person: '',
  contact_email: '',
  contact_phone: '',
  notes: '',
}

export default function CounterpartiesPage() {
  const { isReady } = useAuthGuard()
  const router = useRouter()
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('active')
  const [page, setPage] = useState(1)
  const pageSize = 50

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Counterparty | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)

  const [showLookup, setShowLookup] = useState(false)
  const [lookupInn, setLookupInn] = useState('')

  const { data: types = [] } = useQuery<CounterpartyTypeOption[]>({
    queryKey: ['counterpartyTypes'],
    queryFn: () => api.getCounterpartyTypes(),
    staleTime: 5 * 60_000,
  })

  const { data, isLoading, isError } = useQuery({
    queryKey: ['counterparties', page, pageSize, search, filterType, filterStatus],
    queryFn: () =>
      api.listCounterparties({
        page,
        page_size: pageSize,
        search: search || undefined,
        type: filterType !== 'all' ? filterType : undefined,
        status: filterStatus !== 'all' ? filterStatus : undefined,
      }),
  })

  const createMutation = useMutation({
    mutationFn: (payload: CounterpartyCreate) => api.createCounterparty(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['counterparties'] })
      resetForm()
      toast.success('Контрагент создан')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка создания'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<FormState> }) =>
      api.updateCounterparty(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['counterparties'] })
      resetForm()
      toast.success('Изменения сохранены')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка обновления'),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.archiveCounterparty(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['counterparties'] })
      toast.success('Контрагент архивирован')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка архивации'),
  })

  const lookupMutation = useMutation({
    mutationFn: (inn: string) => api.lookupCounterparty({ inn, save: true, check_bankruptcy: true }),
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: ['counterparties'] })
      if (resp.saved && resp.counterparty) {
        toast.success(`Создан: ${resp.counterparty.name}`)
        setShowLookup(false)
        setLookupInn('')
        router.push(`/counterparties/${resp.counterparty.id}`)
      } else if (resp.fns_data?.found) {
        toast(`Найдено в ФНС: ${resp.fns_data.name}. Нажмите ещё раз для сохранения.`)
      } else {
        toast.error('Компания не найдена в ЕГРЮЛ')
      }
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка проверки ИНН'),
  })

  function resetForm() {
    setForm(EMPTY_FORM)
    setEditing(null)
    setShowForm(false)
  }

  function startEdit(cp: Counterparty) {
    setEditing(cp)
    setForm({
      type: cp.type,
      name: cp.name,
      short_name: cp.short_name || '',
      inn: cp.inn || '',
      kpp: cp.kpp || '',
      ogrn: cp.ogrn || '',
      legal_address: cp.legal_address || '',
      contact_person: cp.contact_person || '',
      contact_email: cp.contact_email || '',
      contact_phone: cp.contact_phone || '',
      notes: cp.notes || '',
    })
    setShowForm(true)
  }

  function submitForm(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name?.trim()) {
      toast.error('Укажите название контрагента')
      return
    }
    const payload: CounterpartyCreate = {
      ...form,
      short_name: form.short_name || undefined,
      inn: form.inn || undefined,
      kpp: form.kpp || undefined,
      ogrn: form.ogrn || undefined,
      legal_address: form.legal_address || undefined,
      contact_person: form.contact_person || undefined,
      contact_email: form.contact_email || undefined,
      contact_phone: form.contact_phone || undefined,
      notes: form.notes || undefined,
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const counterparties = data?.counterparties ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const typeLabel = (v: string) => types.find(t => t.value === v)?.label || v

  if (!isReady) return null

  return (
    <AppLayout title="Контрагенты">
      <div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-5xl font-bold text-stone-900 mb-2">Контрагенты</h1>
              <p className="text-gray-600">
                <span className="text-3xl font-bold text-primary-600 mr-2">{total}</span>
                всего контрагентов
              </p>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setShowLookup(true)}>
                Найти по ИНН
              </Button>
              <Button variant="primary" onClick={() => { setEditing(null); setForm(EMPTY_FORM); setShowForm(true) }}>
                + Добавить вручную
              </Button>
            </div>
          </div>
        </motion.div>

        <Card className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              placeholder="Поиск по названию / ИНН / ОГРН"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              className="px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
            />
            <select
              value={filterType}
              onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
              className="px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
            >
              <option value="all">Все типы</option>
              {types.map(t => (<option key={t.value} value={t.value}>{t.label}</option>))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => { setFilterStatus(e.target.value); setPage(1) }}
              className="px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
            >
              <option value="active">Активные</option>
              <option value="archived">Архив</option>
              <option value="all">Все</option>
            </select>
          </div>
        </Card>

        {isLoading && (
          <Card className="text-center py-12">Загрузка контрагентов…</Card>
        )}
        {isError && (
          <Card className="text-center py-12">
            <p className="text-red-600">Не удалось загрузить список.</p>
            <Button variant="outline" onClick={() => window.location.reload()} className="mt-4">
              Попробовать снова
            </Button>
          </Card>
        )}

        {!isLoading && !isError && counterparties.length === 0 && (
          <Card className="text-center py-16">
            <div className="text-6xl mb-4">🏢</div>
            <h3 className="text-2xl font-bold mb-2">Контрагенты не найдены</h3>
            <p className="text-gray-600 mb-6">
              Добавьте контрагента вручную или найдите по ИНН через ЕГРЮЛ.
            </p>
            <div className="flex justify-center gap-3">
              <Button variant="outline" onClick={() => setShowLookup(true)}>Найти по ИНН</Button>
              <Button variant="primary" onClick={() => { setEditing(null); setForm(EMPTY_FORM); setShowForm(true) }}>
                + Добавить вручную
              </Button>
            </div>
          </Card>
        )}

        {!isLoading && !isError && counterparties.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {counterparties.map((cp, idx) => (
                <motion.div
                  key={cp.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.04 }}
                >
                  <Card hover>
                    <div onClick={() => router.push(`/counterparties/${cp.id}`)} className="cursor-pointer">
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <h3 className="text-lg font-bold text-gray-900 line-clamp-2">{cp.name}</h3>
                        {cp.status === 'archived' && <Badge variant="default" size="sm">Архив</Badge>}
                      </div>
                      <p className="text-sm text-gray-500 mb-3">{typeLabel(cp.type)}</p>
                      <div className="space-y-1 text-sm text-gray-700">
                        {cp.inn && <div>ИНН: <span className="font-mono">{cp.inn}</span></div>}
                        {cp.kpp && <div>КПП: <span className="font-mono">{cp.kpp}</span></div>}
                        {cp.ogrn && <div>ОГРН: <span className="font-mono">{cp.ogrn}</span></div>}
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-gray-500 mt-4 pt-4 border-t border-gray-100">
                      <button
                        onClick={(e) => { e.stopPropagation(); startEdit(cp) }}
                        className="text-primary-600 font-semibold hover:text-primary-700"
                      >
                        Редактировать
                      </button>
                      {cp.status !== 'archived' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (confirm('Архивировать контрагента?')) archiveMutation.mutate(cp.id)
                          }}
                          className="text-gray-500 hover:text-gray-700"
                        >
                          В архив
                        </button>
                      )}
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex justify-center items-center space-x-4 mt-8">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>← Назад</Button>
                <span className="text-gray-600">Страница {page} из {totalPages}</span>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Далее →</Button>
              </div>
            )}
          </>
        )}

        {/* Lookup by INN modal */}
        <AnimatePresence>
          {showLookup && (
            <motion.div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => !lookupMutation.isPending && setShowLookup(false)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
                className="bg-white rounded-2xl p-6 w-full max-w-md"
                onClick={(e) => e.stopPropagation()}
              >
                <h2 className="text-2xl font-bold mb-4">Поиск по ИНН</h2>
                <p className="text-sm text-gray-600 mb-4">Запросим данные из ЕГРЮЛ и Федресурса. Найденная компания будет сохранена в вашей базе.</p>
                <input
                  type="text"
                  placeholder="ИНН (10 или 12 цифр)"
                  value={lookupInn}
                  onChange={(e) => setLookupInn(e.target.value.replace(/\D/g, '').slice(0, 12))}
                  className="w-full px-4 py-3 mb-4 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none font-mono"
                />
                <div className="flex justify-end gap-3">
                  <Button variant="outline" onClick={() => setShowLookup(false)} disabled={lookupMutation.isPending}>Отмена</Button>
                  <Button
                    variant="primary"
                    disabled={lookupInn.length < 10 || lookupMutation.isPending}
                    onClick={() => lookupMutation.mutate(lookupInn)}
                  >
                    {lookupMutation.isPending ? 'Проверяем…' : 'Проверить и сохранить'}
                  </Button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Create / edit modal */}
        <AnimatePresence>
          {showForm && (
            <motion.div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => !createMutation.isPending && !updateMutation.isPending && resetForm()}
            >
              <motion.form
                initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
                onSubmit={submitForm}
                onClick={(e) => e.stopPropagation()}
                className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
              >
                <h2 className="text-2xl font-bold mb-4">
                  {editing ? 'Редактирование контрагента' : 'Новый контрагент'}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Тип</label>
                    <select
                      value={form.type}
                      onChange={(e) => setForm({ ...form, type: e.target.value as any })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                    >
                      {types.map(t => (<option key={t.value} value={t.value}>{t.label}</option>))}
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Полное наименование <span className="text-red-500">*</span></label>
                    <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Краткое наименование</label>
                    <input value={form.short_name || ''} onChange={(e) => setForm({ ...form, short_name: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">ИНН</label>
                    <input value={form.inn || ''} onChange={(e) => setForm({ ...form, inn: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none font-mono" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">КПП</label>
                    <input value={form.kpp || ''} onChange={(e) => setForm({ ...form, kpp: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none font-mono" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">ОГРН</label>
                    <input value={form.ogrn || ''} onChange={(e) => setForm({ ...form, ogrn: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none font-mono" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Юридический адрес</label>
                    <textarea value={form.legal_address || ''} onChange={(e) => setForm({ ...form, legal_address: e.target.value })}
                      rows={2} className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Контактное лицо</label>
                    <input value={form.contact_person || ''} onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Телефон</label>
                    <input value={form.contact_phone || ''} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">E-mail</label>
                    <input type="email" value={form.contact_email || ''} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Заметки</label>
                    <textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                      rows={3} className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <Button type="button" variant="outline" onClick={resetForm}
                    disabled={createMutation.isPending || updateMutation.isPending}>
                    Отмена
                  </Button>
                  <Button type="submit" variant="primary"
                    disabled={createMutation.isPending || updateMutation.isPending}>
                    {createMutation.isPending || updateMutation.isPending
                      ? 'Сохраняем…'
                      : editing ? 'Сохранить' : 'Создать'}
                  </Button>
                </div>
              </motion.form>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}
