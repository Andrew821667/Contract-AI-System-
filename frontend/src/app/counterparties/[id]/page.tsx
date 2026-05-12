'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import api, { Counterparty, CounterpartyUpdate } from '@/services/api'
import AppLayout from '@/components/AppLayout'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import { useAuthGuard } from '@/hooks/useAuthGuard'

type Tab = 'overview' | 'contracts' | 'fns'

export default function CounterpartyDetailPage() {
  const { isReady } = useAuthGuard()
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<CounterpartyUpdate>({})

  const { data: cp, isLoading, isError } = useQuery<Counterparty>({
    queryKey: ['counterparty', id],
    queryFn: () => api.getCounterparty(id),
    enabled: !!id,
  })

  const { data: contractsData } = useQuery({
    queryKey: ['counterparty-contracts', id],
    queryFn: () => api.listCounterpartyContracts(id),
    enabled: !!id && tab === 'contracts',
  })

  const updateMutation = useMutation({
    mutationFn: (payload: CounterpartyUpdate) => api.updateCounterparty(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['counterparty', id] })
      queryClient.invalidateQueries({ queryKey: ['counterparties'] })
      setEditing(false)
      toast.success('Сохранено')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка сохранения'),
  })

  const archiveMutation = useMutation({
    mutationFn: () => api.archiveCounterparty(id),
    onSuccess: () => {
      toast.success('Архивирован')
      router.push('/counterparties')
    },
  })

  const refreshFnsMutation = useMutation({
    mutationFn: () => api.lookupCounterparty({ inn: cp?.inn || '', save: true, check_bankruptcy: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['counterparty', id] })
      toast.success('Данные обновлены из ФНС')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Не удалось обновить'),
  })

  function startEdit() {
    if (!cp) return
    setForm({
      name: cp.name,
      short_name: cp.short_name || undefined,
      type: cp.type,
      inn: cp.inn || undefined,
      kpp: cp.kpp || undefined,
      ogrn: cp.ogrn || undefined,
      legal_address: cp.legal_address || undefined,
      postal_address: cp.postal_address || undefined,
      contact_person: cp.contact_person || undefined,
      contact_email: cp.contact_email || undefined,
      contact_phone: cp.contact_phone || undefined,
      notes: cp.notes || undefined,
    })
    setEditing(true)
  }

  if (!isReady) return null

  return (
    <AppLayout title={cp?.name || 'Контрагент'}>
      <div>
        <button
          onClick={() => router.push('/counterparties')}
          className="text-primary-600 hover:text-primary-700 mb-4 flex items-center gap-2"
        >
          ← Все контрагенты
        </button>

        {isLoading && <Card className="text-center py-12">Загрузка…</Card>}
        {isError && <Card className="text-center py-12 text-red-600">Не удалось загрузить контрагента.</Card>}

        {cp && (
          <>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h1 className="text-4xl font-bold text-stone-900 mb-2">{cp.name}</h1>
                  <div className="flex flex-wrap gap-2 items-center text-gray-600">
                    <span>{({
                      legal: 'Юридическое лицо',
                      individual: 'Физическое лицо',
                      individual_entrepreneur: 'ИП',
                      foreign: 'Иностранное лицо',
                      other: 'Прочее',
                    } as Record<string, string>)[cp.type] || cp.type}</span>
                    {cp.inn && <span>· ИНН <span className="font-mono">{cp.inn}</span></span>}
                    {cp.status === 'archived' && <Badge variant="default">Архив</Badge>}
                  </div>
                </div>
                <div className="flex gap-3">
                  {!editing && (
                    <Button variant="outline" onClick={startEdit}>Редактировать</Button>
                  )}
                  {cp.inn && (
                    <Button variant="outline" onClick={() => refreshFnsMutation.mutate()}
                      disabled={refreshFnsMutation.isPending}>
                      {refreshFnsMutation.isPending ? 'Обновляем…' : 'Обновить из ФНС'}
                    </Button>
                  )}
                  {cp.status !== 'archived' && (
                    <Button
                      variant="outline"
                      onClick={() => { if (confirm('Архивировать?')) archiveMutation.mutate() }}
                      disabled={archiveMutation.isPending}
                    >
                      В архив
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>

            <div className="border-b border-gray-200 mb-6">
              <nav className="flex gap-6">
                {([
                  ['overview', 'Реквизиты'],
                  ['contracts', `Договоры (${cp.contracts_count ?? 0})`],
                  ['fns', 'Проверка ЕГРЮЛ/Федресурс'],
                ] as [Tab, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setTab(key)}
                    className={`py-3 px-1 -mb-px border-b-2 font-medium transition-colors ${
                      tab === key
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </nav>
            </div>

            {tab === 'overview' && !editing && (
              <Card>
                <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                  <Field label="Полное наименование" value={cp.name} />
                  <Field label="Краткое наименование" value={cp.short_name} />
                  <Field label="ИНН" value={cp.inn} mono />
                  <Field label="КПП" value={cp.kpp} mono />
                  <Field label="ОГРН" value={cp.ogrn} mono />
                  <Field label="Контактное лицо" value={cp.contact_person} />
                  <Field label="E-mail" value={cp.contact_email} />
                  <Field label="Телефон" value={cp.contact_phone} />
                  <Field label="Юридический адрес" value={cp.legal_address} full />
                  <Field label="Почтовый адрес" value={cp.postal_address} full />
                  <Field label="Заметки" value={cp.notes} full multiline />
                  <Field label="Создано" value={cp.created_at ? new Date(cp.created_at).toLocaleString('ru-RU') : null} />
                  <Field label="Обновлено" value={cp.updated_at ? new Date(cp.updated_at).toLocaleString('ru-RU') : null} />
                </dl>
              </Card>
            )}

            {tab === 'overview' && editing && (
              <Card>
                <form
                  onSubmit={(e) => { e.preventDefault(); updateMutation.mutate(form) }}
                  className="grid grid-cols-1 md:grid-cols-2 gap-4"
                >
                  <Input label="Полное наименование *" value={form.name || ''} onChange={(v) => setForm({ ...form, name: v })} required />
                  <Input label="Краткое наименование" value={form.short_name || ''} onChange={(v) => setForm({ ...form, short_name: v })} />
                  <Input label="ИНН" value={form.inn || ''} onChange={(v) => setForm({ ...form, inn: v })} mono />
                  <Input label="КПП" value={form.kpp || ''} onChange={(v) => setForm({ ...form, kpp: v })} mono />
                  <Input label="ОГРН" value={form.ogrn || ''} onChange={(v) => setForm({ ...form, ogrn: v })} mono fullRow />
                  <Input label="Юридический адрес" value={form.legal_address || ''} onChange={(v) => setForm({ ...form, legal_address: v })} fullRow textarea />
                  <Input label="Контактное лицо" value={form.contact_person || ''} onChange={(v) => setForm({ ...form, contact_person: v })} />
                  <Input label="Телефон" value={form.contact_phone || ''} onChange={(v) => setForm({ ...form, contact_phone: v })} />
                  <Input label="E-mail" value={form.contact_email || ''} onChange={(v) => setForm({ ...form, contact_email: v })} fullRow />
                  <Input label="Заметки" value={form.notes || ''} onChange={(v) => setForm({ ...form, notes: v })} fullRow textarea />
                  <div className="md:col-span-2 flex justify-end gap-3 mt-2">
                    <Button type="button" variant="outline" onClick={() => setEditing(false)}>Отмена</Button>
                    <Button type="submit" variant="primary" disabled={updateMutation.isPending}>
                      {updateMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                    </Button>
                  </div>
                </form>
              </Card>
            )}

            {tab === 'contracts' && (
              <Card>
                {!contractsData && <p className="text-center text-gray-500 py-6">Загрузка договоров…</p>}
                {contractsData && contractsData.contracts.length === 0 && (
                  <div className="text-center py-12">
                    <div className="text-5xl mb-3">📄</div>
                    <p className="text-gray-600">У этого контрагента пока нет загруженных договоров.</p>
                    <p className="text-sm text-gray-500 mt-2">
                      Привязка договоров к контрагенту будет включена после миграции 022.
                    </p>
                  </div>
                )}
                {contractsData && contractsData.contracts.length > 0 && (
                  <ul className="divide-y divide-gray-100">
                    {contractsData.contracts.map(c => (
                      <li
                        key={c.id}
                        className="py-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-gray-50 px-2 rounded"
                        onClick={() => router.push(`/contracts/${c.id}`)}
                      >
                        <div>
                          <p className="font-medium text-gray-900">{c.file_name}</p>
                          <p className="text-sm text-gray-500">
                            {c.document_type === 'derivative' ? 'Производный документ' : 'Договор'}
                            {c.contract_type ? ` · ${c.contract_type}` : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge variant={c.status === 'completed' ? 'success' : 'default'} size="sm">{c.status}</Badge>
                          <span className="text-primary-600 text-sm font-semibold">→</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}

            {tab === 'fns' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <h3 className="text-lg font-semibold mb-3">ФНС / ЕГРЮЛ</h3>
                  {cp.fns_checked_at
                    ? <p className="text-sm text-gray-500 mb-3">Проверено: {new Date(cp.fns_checked_at).toLocaleString('ru-RU')}</p>
                    : <p className="text-sm text-gray-500 mb-3">Данные ФНС не запрашивались.</p>
                  }
                  {cp.fns_data && (
                    <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-96">{JSON.stringify(cp.fns_data, null, 2)}</pre>
                  )}
                </Card>
                <Card>
                  <h3 className="text-lg font-semibold mb-3">Федресурс (банкротство)</h3>
                  {cp.bankruptcy_checked_at
                    ? <p className="text-sm text-gray-500 mb-3">Проверено: {new Date(cp.bankruptcy_checked_at).toLocaleString('ru-RU')}</p>
                    : <p className="text-sm text-gray-500 mb-3">Не проверялось.</p>
                  }
                  {cp.bankruptcy_data && (
                    <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-96">{JSON.stringify(cp.bankruptcy_data, null, 2)}</pre>
                  )}
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  )
}

function Field({
  label,
  value,
  mono,
  full,
  multiline,
}: {
  label: string
  value?: string | null
  mono?: boolean
  full?: boolean
  multiline?: boolean
}) {
  return (
    <div className={full ? 'md:col-span-2' : ''}>
      <dt className="text-sm font-medium text-gray-500 mb-1">{label}</dt>
      <dd className={`text-gray-900 ${mono ? 'font-mono' : ''} ${multiline ? 'whitespace-pre-line' : ''}`}>
        {value || <span className="text-gray-400">—</span>}
      </dd>
    </div>
  )
}

function Input({
  label,
  value,
  onChange,
  required,
  mono,
  fullRow,
  textarea,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  required?: boolean
  mono?: boolean
  fullRow?: boolean
  textarea?: boolean
}) {
  const cls = `w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none ${mono ? 'font-mono' : ''}`
  return (
    <div className={fullRow ? 'md:col-span-2' : ''}>
      <label className="block text-sm font-medium mb-1">{label}</label>
      {textarea
        ? <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3} className={cls} />
        : <input value={value} onChange={(e) => onChange(e.target.value)} required={required} className={cls} />
      }
    </div>
  )
}
