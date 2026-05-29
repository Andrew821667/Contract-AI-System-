'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import api, {
  ContractListItem,
  Counterparty,
  RelationTypeOption,
} from '@/services/api'
import AppLayout from '@/components/AppLayout'
import CounterpartyAutocomplete from '@/components/CounterpartyAutocomplete'
import { useAuthGuard } from '@/hooks/useAuthGuard'

type ViewMode = 'list' | 'by_counterparty' | 'by_parent'

const TYPE_LABELS: Record<string, string> = {
  all: 'Все типы',
  supply: 'Договор поставки',
  service: 'Договор услуг',
  lease: 'Договор аренды',
  purchase: 'Договор купли-продажи',
  employment: 'Трудовой договор',
  unknown: 'Не определён',
}

const STATUS_LABELS: Record<string, string> = {
  all: 'Все статусы',
  completed: 'Завершён',
  analyzing: 'Анализируется',
  error: 'Ошибка',
  pending: 'Ожидание',
  uploaded: 'Загружен',
  parsing: 'Парсится',
}

const DOC_TYPE_LABELS: Record<string, string> = {
  all: 'Все документы',
  contract: 'Основные договоры',
  derivative: 'Производные документы',
  disagreement: 'Разногласия',
  tracked_changes: 'С правками',
}

export default function ContractsListPage() {
  const { isReady } = useAuthGuard()
  const router = useRouter()

  const [view, setView] = useState<ViewMode>('list')
  const [q, setQ] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterDocType, setFilterDocType] = useState<string>('all')
  const [filterRelType, setFilterRelType] = useState<string>('all')
  const [counterparty, setCounterparty] = useState<Counterparty | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [amountFrom, setAmountFrom] = useState('')
  const [amountTo, setAmountTo] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data: relationTypes = [] } = useQuery<RelationTypeOption[]>({
    queryKey: ['relation-types'],
    queryFn: () => api.getRelationTypes(),
    staleTime: 5 * 60_000,
  })

  const groupBy = view === 'by_counterparty' ? 'counterparty' : view === 'by_parent' ? 'parent' : undefined

  const { data, isLoading, isError, error } = useQuery({
    queryKey: [
      'contracts',
      { page, pageSize, q, filterType, filterStatus, filterDocType, filterRelType,
        counterpartyId: counterparty?.id, dateFrom, dateTo, amountFrom, amountTo, groupBy },
    ],
    queryFn: () =>
      api.listContracts({
        page,
        page_size: pageSize,
        q: q || undefined,
        contract_type: filterType !== 'all' ? filterType : undefined,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        document_type: filterDocType !== 'all' ? filterDocType : undefined,
        relation_type: filterRelType !== 'all' ? filterRelType : undefined,
        counterparty_id: counterparty?.id,
        contract_date_from: dateFrom || undefined,
        contract_date_to: dateTo || undefined,
        amount_from: amountFrom ? Number(amountFrom) : undefined,
        amount_to: amountTo ? Number(amountTo) : undefined,
        group_by: groupBy,
      }),
  })

  const contracts: ContractListItem[] = data?.contracts ?? []
  const groups = data?.groups || null
  const total: number = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const activeFilters = useMemo(() => {
    const list: { label: string; clear: () => void }[] = []
    if (q) list.push({ label: `Поиск: "${q}"`, clear: () => setQ('') })
    if (filterType !== 'all') list.push({ label: TYPE_LABELS[filterType] || filterType, clear: () => setFilterType('all') })
    if (filterStatus !== 'all') list.push({ label: STATUS_LABELS[filterStatus] || filterStatus, clear: () => setFilterStatus('all') })
    if (filterDocType !== 'all') list.push({ label: DOC_TYPE_LABELS[filterDocType] || filterDocType, clear: () => setFilterDocType('all') })
    if (filterRelType !== 'all') {
      const rt = relationTypes.find(r => r.value === filterRelType)
      list.push({ label: rt?.label || filterRelType, clear: () => setFilterRelType('all') })
    }
    if (counterparty) list.push({ label: `Контрагент: ${counterparty.name}`, clear: () => setCounterparty(null) })
    if (dateFrom) list.push({ label: `с ${dateFrom}`, clear: () => setDateFrom('') })
    if (dateTo) list.push({ label: `до ${dateTo}`, clear: () => setDateTo('') })
    if (amountFrom) list.push({ label: `сумма от ${amountFrom}`, clear: () => setAmountFrom('') })
    if (amountTo) list.push({ label: `сумма до ${amountTo}`, clear: () => setAmountTo('') })
    return list
  }, [q, filterType, filterStatus, filterDocType, filterRelType, counterparty, dateFrom, dateTo, amountFrom, amountTo, relationTypes])

  function clearAll() {
    setQ(''); setFilterType('all'); setFilterStatus('all')
    setFilterDocType('all'); setFilterRelType('all')
    setCounterparty(null)
    setDateFrom(''); setDateTo(''); setAmountFrom(''); setAmountTo('')
    setPage(1)
  }

  if (!isReady) return null

  return (
    <AppLayout title="Мои договоры">
      <div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <h1 className="text-5xl font-bold text-stone-900 mb-2">Мои договоры</h1>
          <div className="flex items-center space-x-6">
            <div className="flex items-center">
              <span className="text-3xl font-bold text-primary-600 mr-2">{total}</span>
              <span className="text-gray-600">всего</span>
            </div>
          </div>
        </motion.div>

        {/* View toggle */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <ViewBtn active={view === 'list'} onClick={() => setView('list')}>Список</ViewBtn>
          <ViewBtn active={view === 'by_counterparty'} onClick={() => setView('by_counterparty')}>По контрагентам</ViewBtn>
          <ViewBtn active={view === 'by_parent'} onClick={() => setView('by_parent')}>Иерархия</ViewBtn>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
            <div className="md:col-span-5">
              <input
                type="text"
                value={q}
                onChange={(e) => { setQ(e.target.value); setPage(1) }}
                placeholder="Поиск по названию, № договора, содержимому"
                className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none"
              />
            </div>
            <div className="md:col-span-3">
              <select value={filterDocType} onChange={(e) => { setFilterDocType(e.target.value); setPage(1) }}
                className="w-full px-3 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none">
                {Object.entries(DOC_TYPE_LABELS).map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
              </select>
            </div>
            <div className="md:col-span-2">
              <select value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setPage(1) }}
                className="w-full px-3 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none">
                {Object.entries(STATUS_LABELS).map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
              </select>
            </div>
            <div className="md:col-span-2 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAdvanced(s => !s)}
                className="w-full"
              >
                {showAdvanced ? 'Скрыть фильтры' : 'Доп. фильтры'}
              </Button>
            </div>
          </div>

          {showAdvanced && (
            <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Контрагент</label>
                <CounterpartyAutocomplete value={counterparty} onChange={(cp) => { setCounterparty(cp); setPage(1) }} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Тип производного</label>
                <select value={filterRelType} onChange={(e) => { setFilterRelType(e.target.value); setPage(1) }}
                  className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none">
                  <option value="all">Любой</option>
                  {relationTypes.map(rt => (<option key={rt.value} value={rt.value}>{rt.label}</option>))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Тип контракта</label>
                <select value={filterType} onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
                  className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none">
                  {Object.entries(TYPE_LABELS).map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Дата договора с</label>
                <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
                  className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Дата договора по</label>
                <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
                  className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Сумма от</label>
                  <input type="number" value={amountFrom} onChange={(e) => { setAmountFrom(e.target.value); setPage(1) }}
                    className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Сумма до</label>
                  <input type="number" value={amountTo} onChange={(e) => { setAmountTo(e.target.value); setPage(1) }}
                    className="w-full px-3 py-2 bg-white border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none" />
                </div>
              </div>
            </div>
          )}

          {activeFilters.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-500">Активные фильтры:</span>
              {activeFilters.map((f, i) => (
                <button
                  key={i}
                  onClick={f.clear}
                  className="text-xs px-2 py-1 rounded-full bg-primary-50 text-primary-700 hover:bg-primary-100 border border-primary-100"
                >
                  {f.label} ✕
                </button>
              ))}
              <button onClick={clearAll} className="text-xs text-gray-500 hover:text-gray-700 underline">
                Очистить все
              </button>
            </div>
          )}
        </Card>

        {isLoading && (<Card className="text-center py-12">Загрузка договоров…</Card>)}
        {isError && (
          <Card className="text-center py-12">
            <div className="text-6xl mb-4">⚠️</div>
            <p className="text-gray-600 mb-4">{(error as any)?.response?.data?.detail || 'Ошибка загрузки'}</p>
            <Button variant="primary" onClick={() => window.location.reload()}>Попробовать снова</Button>
          </Card>
        )}

        {!isLoading && !isError && !groups && contracts.length === 0 && (
          <Card className="text-center py-12">
            <div className="text-6xl mb-4">📭</div>
            <h3 className="text-2xl font-bold mb-2">Договоры не найдены</h3>
            <p className="text-gray-600 mb-6">
              {activeFilters.length > 0 ? 'Попробуйте изменить фильтры' : 'Загрузите первый договор для анализа'}
            </p>
            <Button variant="primary" onClick={() => router.push('/contracts/upload')}>+ Загрузить договор</Button>
          </Card>
        )}

        {!isLoading && !isError && !groups && contracts.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {contracts.map((c, idx) => (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.04 }}
                >
                  <ContractCard
                    contract={c}
                    onClick={() => router.push(`/contracts/${c.id}`)}
                    relationTypes={relationTypes}
                  />
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

        {!isLoading && !isError && groups && (
          <div className="space-y-6">
            {groups.length === 0 && (
              <Card className="text-center py-12 text-gray-500">Нет данных для группировки</Card>
            )}
            {groups.map((g) => (
              <div key={g.group_id || 'none'}>
                <div className="flex items-baseline gap-3 mb-3">
                  <h2 className="text-xl font-bold text-stone-900">{g.group_label}</h2>
                  <span className="text-sm text-gray-500">· {g.total}</span>
                  {g.group_meta?.inn && (
                    <span className="text-xs font-mono text-gray-500">ИНН {g.group_meta.inn}</span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {g.contracts.map((c) => (
                    <ContractCard
                      key={c.id}
                      contract={c}
                      onClick={() => router.push(`/contracts/${c.id}`)}
                      relationTypes={relationTypes}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}

function ViewBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
        active
          ? 'bg-primary-600 text-white'
          : 'bg-white border-2 border-gray-200 text-gray-700 hover:border-primary-300'
      }`}
    >
      {children}
    </button>
  )
}

function ContractCard({
  contract: c,
  onClick,
  relationTypes,
}: {
  contract: ContractListItem
  onClick: () => void
  relationTypes: RelationTypeOption[]
}) {
  const statusBadge = (() => {
    const map: Record<string, { variant: 'success' | 'info' | 'danger' | 'warning' | 'default'; text: string }> = {
      completed: { variant: 'success', text: 'Завершён' },
      analyzing: { variant: 'info', text: 'Анализ...' },
      error: { variant: 'danger', text: 'Ошибка' },
      pending: { variant: 'warning', text: 'Ожидание' },
      uploaded: { variant: 'default', text: 'Загружен' },
      parsing: { variant: 'info', text: 'Парсинг' },
    }
    return map[c.status] || { variant: 'default' as const, text: c.status }
  })()

  const docTypeLabel = (() => {
    if (c.document_type === 'derivative' && c.primary_relation_type) {
      return relationTypes.find(rt => rt.value === c.primary_relation_type)?.label || 'Производный'
    }
    return DOC_TYPE_LABELS[c.document_type] || c.document_type
  })()

  return (
    <Card hover onClick={onClick}>
      <div className="flex items-start justify-between mb-3 gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-bold text-gray-900 line-clamp-2">{c.file_name}</h3>
          <p className="text-xs text-gray-500 mt-1">
            {docTypeLabel}
            {c.contract_type ? ` · ${TYPE_LABELS[c.contract_type] || c.contract_type}` : ''}
          </p>
        </div>
        <Badge variant={statusBadge.variant} size="sm">{statusBadge.text}</Badge>
      </div>

      <div className="space-y-1 text-sm text-gray-700">
        {c.contract_number && (<div>№ <span className="font-mono">{c.contract_number}</span></div>)}
        {c.contract_date && (
          <div>от {new Date(c.contract_date).toLocaleDateString('ru-RU')}</div>
        )}
        {c.counterparty?.name && (
          <div className="truncate">
            <span className="text-gray-500">с </span>
            {c.counterparty.name}
            {c.counterparty.inn && (<span className="text-gray-400 text-xs"> · ИНН {c.counterparty.inn}</span>)}
          </div>
        )}
        {c.total_amount !== null && c.total_amount !== undefined && (
          <div className="text-gray-700">
            {c.total_amount.toLocaleString('ru-RU')} {c.currency || ''}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 mt-4 pt-3 border-t border-gray-100">
        <span>
          {c.created_at ? new Date(c.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
        </span>
        <div className="flex items-center gap-3">
          <Link
            href={`/revisions/compare?contractId=${c.id}`}
            // The card itself has onClick → /contracts/{id}; stopPropagation so
            // clicking this link doesn't *also* fire the card navigation.
            onClick={(e) => e.stopPropagation()}
            className="text-gray-600 font-medium hover:text-primary-600"
            title="Открыть юридическое сравнение редакций этого договора"
          >
            Сравнить редакции
          </Link>
          <span className="text-primary-600 font-semibold">Открыть →</span>
        </div>
      </div>
    </Card>
  )
}
