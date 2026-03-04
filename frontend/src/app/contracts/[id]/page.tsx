'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import api, { DigitalContract, VerificationResult, RiskPredictionResponse } from '@/services/api'

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
      <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20 flex items-center justify-center">
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
      <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20 flex items-center justify-center">
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
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
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
              <span className="text-xl font-bold text-stone-800">Contract AI</span>
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
            <Card className="text-center py-12 bg-amber-50 border-2 border-primary-200">
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
                          <div className="bg-amber-50 border border-blue-100 rounded-lg p-3 mb-2">
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

        {/* ML Quick Risk Assessment */}
        <MLRiskSection contractId={contractId} contract={contract} onAnalyze={() => analyzeMutation.mutate()} />

        {/* Digital Verification Section */}
        <DigitalVerificationSection contractId={contractId} />

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


// ==================== ML Quick Risk Assessment Section ====================

function MLRiskSection({ contractId, contract, onAnalyze }: { contractId: string; contract: any; onAnalyze: () => void }) {
  const [prediction, setPrediction] = useState<RiskPredictionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [selectedActual, setSelectedActual] = useState('')
  const [feedbackReason, setFeedbackReason] = useState('')
  const [submittingFeedback, setSubmittingFeedback] = useState(false)

  const riskLevelLabels: Record<string, { label: string; color: string; bg: string }> = {
    critical: { label: 'Критический', color: 'text-red-700', bg: 'bg-red-100' },
    high: { label: 'Высокий', color: 'text-orange-700', bg: 'bg-orange-100' },
    medium: { label: 'Средний', color: 'text-yellow-700', bg: 'bg-yellow-100' },
    low: { label: 'Низкий', color: 'text-green-700', bg: 'bg-green-100' },
    minimal: { label: 'Минимальный', color: 'text-emerald-700', bg: 'bg-emerald-100' },
  }

  const handlePredict = async () => {
    setLoading(true)
    setPrediction(null)
    setFeedbackSent(false)
    try {
      const result = await api.predictRisk({
        contract_type: contract?.contract_type || 'unknown',
        amount: contract?.amount || 100000,
        duration_days: contract?.duration_days || 365,
        clause_count: contract?.clause_count || 0,
        doc_length: contract?.doc_length || 0,
      })
      setPrediction(result)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка ML-предсказания')
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async () => {
    if (!prediction || !selectedActual) return
    setSubmittingFeedback(true)
    try {
      await api.submitRiskFeedback({
        contract_id: parseInt(contractId) || undefined,
        contract_features: prediction.features_used,
        predicted_risk_level: prediction.risk_level,
        predicted_confidence: prediction.confidence,
        actual_risk_level: selectedActual,
        feedback_reason: feedbackReason || undefined,
        model_version: prediction.model_version,
      })
      toast.success('Спасибо за обратную связь!')
      setFeedbackSent(true)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка отправки')
    } finally {
      setSubmittingFeedback(false)
    }
  }

  const riskInfo = prediction ? riskLevelLabels[prediction.risk_level] || riskLevelLabels.medium : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25 }}
      className="mb-8"
    >
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">ML Быстрая оценка</h2>
          <Button
            variant="primary"
            size="sm"
            loading={loading}
            onClick={handlePredict}
          >
            Быстрая оценка (ML)
          </Button>
        </div>

        {!prediction && !loading && (
          <p className="text-gray-500 text-sm">
            Мгновенная оценка рисков на основе машинного обучения. Работает в 100 раз быстрее и в 60 раз дешевле полного LLM-анализа.
          </p>
        )}

        {prediction && riskInfo && (
          <div className="space-y-4">
            {/* Risk Result Card */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Risk Level */}
              <div className={`rounded-xl p-4 ${riskInfo.bg} text-center`}>
                <p className="text-xs text-gray-500 mb-1">Уровень риска</p>
                <p className={`text-2xl font-bold ${riskInfo.color}`}>{riskInfo.label}</p>
              </div>

              {/* Risk Score */}
              <div className="rounded-xl p-4 bg-gray-50 text-center">
                <p className="text-xs text-gray-500 mb-1">Оценка риска</p>
                <p className="text-2xl font-bold text-gray-900">{prediction.risk_score.toFixed(0)}<span className="text-sm text-gray-400">/100</span></p>
              </div>

              {/* Confidence */}
              <div className="rounded-xl p-4 bg-blue-50 text-center">
                <p className="text-xs text-gray-500 mb-1">Уверенность</p>
                <p className="text-2xl font-bold text-blue-700">{(prediction.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>

            {/* Confidence Bar */}
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Уверенность модели</span>
                <span>{(prediction.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${prediction.confidence * 100}%` }}
                  transition={{ duration: 0.8 }}
                  className={`h-full rounded-full ${
                    prediction.confidence >= 0.8 ? 'bg-green-500' :
                    prediction.confidence >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                />
              </div>
            </div>

            {/* Recommendation */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-sm text-amber-800">{prediction.recommendation}</p>
            </div>

            {/* Should use LLM suggestion */}
            {prediction.should_use_llm && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center justify-between">
                <p className="text-sm text-blue-800">
                  Рекомендуется запустить полный LLM-анализ для детальных результатов.
                </p>
                <Button variant="primary" size="sm" onClick={onAnalyze}>
                  Запустить LLM
                </Button>
              </div>
            )}

            {/* Prediction time */}
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span>Время: {prediction.prediction_time_ms.toFixed(0)} мс</span>
              <span>Модель: {prediction.model_version}</span>
            </div>

            {/* Feedback section */}
            {!feedbackSent ? (
              <div className="border-t border-gray-200 pt-4 mt-4">
                <p className="text-sm font-semibold text-gray-700 mb-2">Согласны с оценкой?</p>
                <div className="flex flex-wrap gap-2 mb-3">
                  {Object.entries(riskLevelLabels).map(([level, info]) => (
                    <button
                      key={level}
                      onClick={() => setSelectedActual(level)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                        selectedActual === level
                          ? `${info.bg} ${info.color} border-current`
                          : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                      }`}
                    >
                      {info.label}
                    </button>
                  ))}
                </div>
                {selectedActual && selectedActual !== prediction.risk_level && (
                  <input
                    type="text"
                    placeholder="Причина несогласия (опционально)"
                    value={feedbackReason}
                    onChange={(e) => setFeedbackReason(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                )}
                {selectedActual && (
                  <Button
                    variant={selectedActual === prediction.risk_level ? 'outline' : 'primary'}
                    size="sm"
                    loading={submittingFeedback}
                    onClick={handleFeedback}
                  >
                    {selectedActual === prediction.risk_level ? 'Подтвердить оценку' : 'Отправить коррекцию'}
                  </Button>
                )}
              </div>
            ) : (
              <div className="border-t border-gray-200 pt-4 mt-4 text-center text-sm text-green-600 font-medium">
                Спасибо! Ваш отзыв поможет улучшить модель.
              </div>
            )}
          </div>
        )}
      </Card>
    </motion.div>
  )
}


// ==================== Digital Verification Section ====================

function DigitalVerificationSection({ contractId }: { contractId: string }) {
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null)
  const [verifying, setVerifying] = useState(false)

  const { data: digitalData, isLoading: loadingVersions, refetch } = useQuery({
    queryKey: ['digital-versions', contractId],
    queryFn: () => api.getDigitalVersions(contractId),
  })

  const { data: chainData } = useQuery({
    queryKey: ['digital-chain', contractId],
    queryFn: () => api.getHashChain(contractId),
    enabled: (digitalData?.total ?? 0) > 0,
  })

  const digitalizeMutation = useMutation({
    mutationFn: () => api.digitalizeContract(contractId),
    onSuccess: () => {
      toast.success('Цифровая версия создана')
      refetch()
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Ошибка цифровизации')
    },
  })

  const handleVerify = async (digitalId: string) => {
    setVerifying(true)
    setVerifyResult(null)
    try {
      const result = await api.verifyDigital(contractId, digitalId)
      setVerifyResult(result)
      if (result.valid) {
        toast.success('Целостность подтверждена')
      } else {
        toast.error('Целостность нарушена!')
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка верификации')
    } finally {
      setVerifying(false)
    }
  }

  const versions: DigitalContract[] = digitalData?.versions || []
  const activeVersion = versions.find((v) => v.status === 'active')
  const chain = chainData?.chain || []

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35 }}
      className="mb-8"
    >
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Цифровая верификация</h2>
          <div className="flex items-center gap-3">
            {activeVersion ? (
              <Badge variant="success" size="sm">Цифровая версия v{activeVersion.version}</Badge>
            ) : (
              <Badge variant="default" size="sm">Не цифровизирован</Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              loading={digitalizeMutation.isPending}
              onClick={() => digitalizeMutation.mutate()}
            >
              {activeVersion ? 'Новая версия' : 'Цифровизировать'}
            </Button>
          </div>
        </div>

        {/* Verification result */}
        {verifyResult && (
          <div className={`rounded-lg p-4 mb-4 border ${verifyResult.valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{verifyResult.valid ? '\u2705' : '\u274C'}</span>
              <span className={`font-semibold ${verifyResult.valid ? 'text-green-800' : 'text-red-800'}`}>
                {verifyResult.valid ? 'Целостность подтверждена' : 'Целостность нарушена'}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
              <div className="flex items-center gap-1">
                <span>{verifyResult.signature_valid ? '\u2705' : '\u274C'}</span>
                <span className="text-gray-700">HMAC-подпись</span>
              </div>
              <div className="flex items-center gap-1">
                <span>{verifyResult.content_hash_match === null ? '\u2754' : verifyResult.content_hash_match ? '\u2705' : '\u274C'}</span>
                <span className="text-gray-700">Хеш содержимого</span>
              </div>
              <div className="flex items-center gap-1">
                <span>{verifyResult.chain_valid ? '\u2705' : '\u274C'}</span>
                <span className="text-gray-700">Цепочка версий</span>
              </div>
            </div>
          </div>
        )}

        {/* Hash chain timeline */}
        {chain.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
              Цепочка версий ({chain.length})
            </h3>
            <div className="space-y-3">
              {chain.map((item: any, idx: number) => (
                <div key={item.id} className="flex items-start gap-3">
                  {/* Timeline connector */}
                  <div className="flex flex-col items-center">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 ${
                      item.status === 'active'
                        ? 'bg-green-100 border-green-400 text-green-700'
                        : item.status === 'revoked'
                          ? 'bg-red-100 border-red-400 text-red-700'
                          : 'bg-gray-100 border-gray-300 text-gray-500'
                    }`}>
                      {item.version}
                    </div>
                    {idx < chain.length - 1 && (
                      <div className="w-0.5 h-6 bg-gray-300 mt-1" />
                    )}
                  </div>

                  {/* Version info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-900">Версия {item.version}</span>
                      <Badge
                        variant={item.status === 'active' ? 'success' : item.status === 'revoked' ? 'danger' : 'default'}
                        size="sm"
                      >
                        {item.status === 'active' ? 'Активна' : item.status === 'revoked' ? 'Отозвана' : 'Заменена'}
                      </Badge>
                      {item.status === 'active' && (
                        <button
                          onClick={() => handleVerify(item.id)}
                          disabled={verifying}
                          className="text-xs text-primary-600 hover:text-primary-800 font-medium disabled:opacity-50"
                        >
                          {verifying ? 'Проверка...' : 'Верифицировать'}
                        </button>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5 font-mono truncate">
                      SHA-256: {item.content_hash}
                    </div>
                    {item.created_at && (
                      <div className="text-xs text-gray-400 mt-0.5">
                        {new Date(item.created_at).toLocaleString('ru-RU')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loadingVersions && versions.length === 0 && (
          <div className="text-center py-6 text-gray-500">
            <div className="text-3xl mb-2">{'\uD83D\uDD10'}</div>
            <p className="text-sm">Нет цифровых версий. Нажмите «Цифровизировать» для создания.</p>
          </div>
        )}

        {loadingVersions && (
          <div className="text-center py-4 text-gray-400 text-sm">Загрузка...</div>
        )}
      </Card>
    </motion.div>
  )
}
