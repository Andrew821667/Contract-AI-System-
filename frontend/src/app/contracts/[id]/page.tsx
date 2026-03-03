'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import api from '@/services/api'

interface Risk {
  risk_type: string
  severity: string
  probability: string
  title: string
  description: string
  consequences: string
}

interface Recommendation {
  priority: string
  category: string
  title: string
  description: string
  reasoning: string
  expected_benefit: string
}

export default function ContractDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const contractId = params.id as string

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['contract', contractId],
    queryFn: () => api.getContract(contractId),
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(contractId),
    onSuccess: () => {
      toast.success('Анализ запущен. Обновите страницу через некоторое время.')
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Ошибка запуска анализа')
    },
  })

  const handleExport = async (format: string) => {
    try {
      const blob = await api.exportContract(contractId, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `contract_${contractId}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success(`Экспорт в ${format.toUpperCase()} выполнен`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка экспорта')
    }
  }

  const contract = data?.contract
  const analysis = data?.analysis

  const getSeverityBadge = (severity: string) => {
    const map: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info'; label: string }> = {
      low: { variant: 'success', label: 'Низкий' },
      medium: { variant: 'warning', label: 'Средний' },
      high: { variant: 'danger', label: 'Высокий' },
      critical: { variant: 'danger', label: 'Критический' },
    }
    return map[severity] || { variant: 'info' as const, label: severity }
  }

  const getPriorityLabel = (priority: string) => {
    const map: Record<string, string> = {
      high: 'Высокий',
      medium: 'Средний',
      low: 'Низкий',
    }
    return map[priority] || priority
  }

  const typeLabels: Record<string, string> = {
    supply: 'Договор поставки',
    service: 'Договор услуг',
    lease: 'Договор аренды',
    purchase: 'Договор купли-продажи',
    employment: 'Трудовой договор',
    unknown: 'Не определён',
  }

  const statusLabels: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info' | 'default'; text: string }> = {
    completed: { variant: 'success', text: 'Анализ завершён' },
    analyzing: { variant: 'info', text: 'Анализируется...' },
    error: { variant: 'danger', text: 'Ошибка' },
    uploaded: { variant: 'default', text: 'Загружен' },
    pending: { variant: 'warning', text: 'Ожидание' },
    generated: { variant: 'success', text: 'Сгенерирован' },
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-12 w-12 text-primary-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-gray-600 text-lg">Загрузка договора...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <Card className="max-w-md text-center">
          <div className="text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Ошибка</h2>
          <p className="text-gray-600 mb-6">
            {(error as any)?.response?.data?.detail || 'Не удалось загрузить договор'}
          </p>
          <div className="flex justify-center space-x-3">
            <Button variant="outline" onClick={() => router.push('/contracts')}>
              ← К списку
            </Button>
            <Button variant="primary" onClick={() => router.push('/login')}>
              Войти
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  const statusInfo = statusLabels[contract?.status] || statusLabels.pending
  const risks: Risk[] = analysis?.risks || []
  const recommendations: Recommendation[] = analysis?.recommendations || []

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
              <div className="w-10 h-10 bg-gradient-primary rounded-xl shadow-lg flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <span className="text-xl font-bold gradient-text">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/contracts')}>
                ← Договоры
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Contract Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <Card>
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  {contract?.file_name || 'Договор'}
                </h1>
                <div className="flex items-center flex-wrap gap-3">
                  <Badge variant={statusInfo.variant} size="md">
                    {statusInfo.text}
                  </Badge>
                  <span className="text-gray-500">
                    {typeLabels[contract?.contract_type] || contract?.contract_type}
                  </span>
                  {contract?.created_at && (
                    <span className="text-gray-400">
                      {new Date(contract.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                      })}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-3 flex-shrink-0">
                {contract?.status === 'uploaded' && (
                  <Button
                    variant="primary"
                    size="sm"
                    loading={analyzeMutation.isPending}
                    onClick={() => analyzeMutation.mutate()}
                  >
                    🔍 Запустить анализ
                  </Button>
                )}
                {contract?.status === 'completed' && (
                  <Button
                    variant="outline"
                    size="sm"
                    loading={analyzeMutation.isPending}
                    onClick={() => analyzeMutation.mutate()}
                  >
                    🔄 Повторный анализ
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Analyzing Spinner */}
        {contract?.status === 'analyzing' && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-8"
          >
            <Card className="text-center py-12 bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-primary-200">
              <svg className="animate-spin h-12 w-12 text-primary-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Анализ выполняется...</h3>
              <p className="text-gray-600">
                AI анализирует ваш договор. Это может занять 30-60 секунд.
              </p>
              <p className="text-sm text-gray-400 mt-2">
                Обновите страницу, чтобы проверить результат.
              </p>
            </Card>
          </motion.div>
        )}

        {/* Analysis Results */}
        {analysis && contract?.status === 'completed' && (
          <>
            {/* Risks Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="mb-8"
            >
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                Риски ({risks.length})
              </h2>

              {risks.length === 0 ? (
                <Card>
                  <div className="text-center py-8">
                    <div className="text-4xl mb-2">✅</div>
                    <p className="text-gray-600">Критических рисков не обнаружено</p>
                  </div>
                </Card>
              ) : (
                <div className="space-y-4">
                  {risks.map((risk, idx) => {
                    const severity = getSeverityBadge(risk.severity)
                    return (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.1 * idx }}
                      >
                        <Card>
                          <div className="flex items-start justify-between mb-3">
                            <h3 className="text-lg font-semibold text-gray-900 flex-1">
                              {risk.title}
                            </h3>
                            <div className="flex items-center space-x-2 ml-4">
                              <Badge variant={severity.variant} size="sm">
                                {severity.label}
                              </Badge>
                            </div>
                          </div>
                          <p className="text-gray-700 mb-3">{risk.description}</p>
                          {risk.consequences && (
                            <div className="bg-red-50 border border-red-100 rounded-lg p-3">
                              <span className="text-sm font-semibold text-red-700">Последствия: </span>
                              <span className="text-sm text-red-600">{risk.consequences}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                            <span>Тип: {risk.risk_type}</span>
                            <span>Вероятность: {risk.probability}</span>
                          </div>
                        </Card>
                      </motion.div>
                    )
                  })}
                </div>
              )}
            </motion.div>

            {/* Recommendations Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mb-8"
            >
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                Рекомендации ({recommendations.length})
              </h2>

              {recommendations.length === 0 ? (
                <Card>
                  <div className="text-center py-8">
                    <div className="text-4xl mb-2">👍</div>
                    <p className="text-gray-600">Рекомендаций нет — договор в хорошем состоянии</p>
                  </div>
                </Card>
              ) : (
                <div className="space-y-4">
                  {recommendations.map((rec, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 * idx }}
                    >
                      <Card>
                        <div className="flex items-start justify-between mb-2">
                          <h3 className="text-lg font-semibold text-gray-900">
                            {rec.title}
                          </h3>
                          <Badge
                            variant={rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'info'}
                            size="sm"
                          >
                            {getPriorityLabel(rec.priority)}
                          </Badge>
                        </div>
                        <p className="text-gray-700 mb-3">{rec.description}</p>
                        {rec.reasoning && (
                          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-2">
                            <span className="text-sm font-semibold text-blue-700">Обоснование: </span>
                            <span className="text-sm text-blue-600">{rec.reasoning}</span>
                          </div>
                        )}
                        {rec.expected_benefit && (
                          <div className="bg-green-50 border border-green-100 rounded-lg p-3">
                            <span className="text-sm font-semibold text-green-700">Ожидаемый эффект: </span>
                            <span className="text-sm text-green-600">{rec.expected_benefit}</span>
                          </div>
                        )}
                      </Card>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          </>
        )}

        {/* Export Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card>
            <h2 className="text-xl font-bold text-gray-900 mb-4">Экспорт</h2>
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" size="sm" onClick={() => handleExport('docx')}>
                📄 DOCX
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleExport('pdf')}>
                📑 PDF
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
                📊 JSON
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleExport('txt')}>
                📝 TXT
              </Button>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
