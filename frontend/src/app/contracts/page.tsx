'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import api from '@/services/api'

interface Contract {
  id: string
  file_name: string
  status: 'analyzing' | 'completed' | 'error' | 'pending' | 'uploaded'
  contract_type: string
  created_at: string
  updated_at: string
}

export default function ContractsListPage() {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['contracts', page, pageSize],
    queryFn: () => api.listContracts({ page, limit: pageSize }),
  })

  const contracts: Contract[] = data?.contracts ?? []
  const total: number = data?.total ?? 0
  const totalPages = Math.ceil(total / pageSize)

  const contractTypes = ['all', 'supply', 'service', 'lease', 'purchase', 'employment', 'unknown']
  const statuses = ['all', 'completed', 'analyzing', 'error', 'uploaded', 'pending']

  const typeLabels: Record<string, string> = {
    all: 'Все типы',
    supply: 'Договор поставки',
    service: 'Договор услуг',
    lease: 'Договор аренды',
    purchase: 'Договор купли-продажи',
    employment: 'Трудовой договор',
    unknown: 'Не определён',
  }

  const getStatusBadge = (status: string) => {
    const badges = {
      completed: { variant: 'success' as const, text: 'Завершён' },
      analyzing: { variant: 'info' as const, text: 'Анализируется...' },
      error: { variant: 'danger' as const, text: 'Ошибка' },
      pending: { variant: 'warning' as const, text: 'Ожидание' },
      uploaded: { variant: 'default' as const, text: 'Загружен' },
    }
    return badges[status as keyof typeof badges] || badges.pending
  }

  const filteredContracts = contracts.filter(contract => {
    const matchesSearch = contract.file_name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === 'all' || contract.contract_type === filterType
    const matchesStatus = filterStatus === 'all' || contract.status === filterStatus
    return matchesSearch && matchesType && matchesStatus
  })

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3 cursor-pointer"
              onClick={() => router.push('/dashboard')}
            >
              <div className="w-10 h-10 bg-primary-600 rounded-xl shadow-sm flex items-center justify-center">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <span className="text-xl font-bold text-slate-800">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/dashboard')}>
                ← Дашборд
              </Button>
              <Button variant="secondary" size="sm" onClick={() => router.push('/contracts/generate')}>
                ✨ Генератор
              </Button>
              <Button variant="primary" size="sm" onClick={() => router.push('/contracts/upload')}>
                + Загрузить
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title & Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-5xl font-bold text-slate-900 mb-4">
            Мои договоры
          </h1>
          <div className="flex items-center space-x-6">
            <div className="flex items-center">
              <span className="text-3xl font-bold text-primary-600 mr-2">{total}</span>
              <span className="text-gray-600">всего договоров</span>
            </div>
            <div className="flex items-center">
              <span className="text-3xl font-bold text-success-600 mr-2">
                {contracts.filter(c => c.status === 'completed').length}
              </span>
              <span className="text-gray-600">проанализировано</span>
            </div>
          </div>
        </motion.div>

        {/* Filters & Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <Card>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Search */}
              <div className="md:col-span-1">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Поиск по названию..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                  />
                  <svg className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>

              {/* Type Filter */}
              <div>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                >
                  {contractTypes.map(type => (
                    <option key={type} value={type}>
                      {typeLabels[type] || type}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                >
                  {statuses.map(status => (
                    <option key={status} value={status}>
                      {status === 'all' ? 'Все статусы' : getStatusBadge(status).text}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Loading State */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Card className="text-center py-12">
              <div className="flex flex-col items-center">
                <svg className="animate-spin h-10 w-10 text-primary-500 mb-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p className="text-gray-600">Загрузка договоров...</p>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Error State */}
        {isError && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Card className="text-center py-12">
              <div className="text-6xl mb-4">⚠️</div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">
                Ошибка загрузки
              </h3>
              <p className="text-gray-600 mb-6">
                {(error as any)?.response?.data?.detail || 'Не удалось загрузить список договоров. Проверьте авторизацию.'}
              </p>
              <div className="flex justify-center space-x-3">
                <Button variant="primary" onClick={() => window.location.reload()}>
                  Попробовать снова
                </Button>
                <Button variant="outline" onClick={() => router.push('/login')}>
                  Войти
                </Button>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Contracts Grid */}
        {!isLoading && !isError && filteredContracts.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="text-center py-12">
              <div className="text-6xl mb-4">📭</div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">
                Договоры не найдены
              </h3>
              <p className="text-gray-600 mb-6">
                {searchQuery || filterType !== 'all' || filterStatus !== 'all'
                  ? 'Попробуйте изменить фильтры поиска'
                  : 'Загрузите первый договор для анализа'}
              </p>
              <Button variant="primary" onClick={() => router.push('/contracts/upload')}>
                + Загрузить договор
              </Button>
            </Card>
          </motion.div>
        )}

        {!isLoading && !isError && filteredContracts.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredContracts.map((contract, idx) => (
                <motion.div
                  key={contract.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <Card
                    hover
                    onClick={() => router.push(`/contracts/${contract.id}`)}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h3 className="text-lg font-bold text-gray-900 mb-1 line-clamp-1">
                          {contract.file_name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {typeLabels[contract.contract_type] || contract.contract_type}
                        </p>
                      </div>
                      <Badge {...getStatusBadge(contract.status)} size="sm">
                        {getStatusBadge(contract.status).text}
                      </Badge>
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between text-xs text-gray-500 mt-4 pt-4 border-t border-gray-100">
                      <div className="flex items-center">
                        <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        {contract.created_at
                          ? new Date(contract.created_at).toLocaleDateString('ru-RU', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric'
                            })
                          : '—'
                        }
                      </div>
                      <span className="text-primary-600 font-semibold hover:text-primary-700">
                        Открыть →
                      </span>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center items-center space-x-4 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                >
                  ← Назад
                </Button>
                <span className="text-gray-600">
                  Страница {page} из {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(p => p + 1)}
                >
                  Далее →
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
