'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import FileUpload from '@/components/forms/FileUpload'
import CounterpartyAutocomplete from '@/components/CounterpartyAutocomplete'
import ContractAutocomplete from '@/components/ContractAutocomplete'
import api, {
  Counterparty,
  ContractRelationType,
  ContractUploadOptions,
  ParentCandidate,
  RelationTypeOption,
} from '@/services/api'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import { useAuthStore } from '@/stores/authStore'
import AppLayout from '@/components/AppLayout'

type DocKind = 'contract' | 'derivative'

interface ParentCandidate__ extends ParentCandidate {} // alias to keep types tidy

export default function ContractUploadPage() {
  const { isReady } = useAuthGuard()
  const user = useAuthStore((s) => s.user)
  const router = useRouter()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  // Тип и связь
  const [docKind, setDocKind] = useState<DocKind>('contract')
  const [relationType, setRelationType] = useState<ContractRelationType>('supplementary_agreement')
  const [parentContract, setParentContract] = useState<{ id: string; file_name: string } | null>(null)
  const [autoFindParent, setAutoFindParent] = useState(true)
  const [customLabel, setCustomLabel] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')

  // Контрагент
  const [counterparty, setCounterparty] = useState<Counterparty | null>(null)

  // Пост-загрузочный модал кандидатов
  const [candidatesModal, setCandidatesModal] = useState<{
    contractId: string
    candidates: ParentCandidate[]
  } | null>(null)
  const [linking, setLinking] = useState(false)
  const [postLinkRelationType, setPostLinkRelationType] = useState<ContractRelationType>(
    'supplementary_agreement',
  )

  const { data: relationTypes = [] } = useQuery<RelationTypeOption[]>({
    queryKey: ['relation-types'],
    queryFn: () => api.getRelationTypes(),
    staleTime: 5 * 60_000,
  })

  const isCustom = relationType === 'custom'
  const customRequiresFill =
    docKind === 'derivative' && isCustom && !customLabel.trim() && !customPrompt.trim()

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error('Пожалуйста, загрузите файл')
      return
    }
    if (customRequiresFill) {
      toast.error('Для custom-связи укажите название или промпт')
      return
    }
    if (docKind === 'derivative' && parentContract && !relationType) {
      toast.error('Укажите тип связи')
      return
    }

    setUploading(true)
    setUploadProgress(20)

    try {
      const opts: ContractUploadOptions = {
        document_type: docKind === 'derivative' ? 'derivative' : 'contract',
        counterparty_id: counterparty?.id || undefined,
      }
      if (docKind === 'derivative') {
        opts.relation_type = relationType
        opts.auto_find_parent = !parentContract && autoFindParent
        if (parentContract) opts.parent_contract_id = parentContract.id
        if (isCustom) {
          opts.custom_label = customLabel || undefined
          opts.custom_prompt = customPrompt || undefined
        }
      }

      const result = await api.uploadContract(selectedFile, opts)
      setUploadProgress(100)
      toast.success('Документ загружен')

      // Если автопоиск нашёл кандидатов и parent явно не задавали — показать модал
      const candidates = result.parent_candidates || []
      if (
        docKind === 'derivative' &&
        !parentContract &&
        candidates.length > 0
      ) {
        setPostLinkRelationType(relationType)
        setCandidatesModal({ contractId: result.contract_id, candidates })
        setUploading(false)
        return
      }

      router.push(`/contracts/${result.contract_id}`)
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Ошибка загрузки файла.'
      toast.error(message)
      setUploading(false)
      setUploadProgress(0)
    }
  }

  async function attachParent(parentContractId: string) {
    if (!candidatesModal) return
    setLinking(true)
    try {
      await api.linkContractParent(candidatesModal.contractId, {
        parent_contract_id: parentContractId,
        relation_type: postLinkRelationType,
      })
      toast.success('Основной договор привязан')
      router.push(`/contracts/${candidatesModal.contractId}`)
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Ошибка привязки')
    } finally {
      setLinking(false)
    }
  }

  if (!isReady) return null

  const usesExtendedContractQuota = user?.contract_quota_period === 'month' || user?.contract_quota_period === 'demo'
  const contractQuotaUsed = usesExtendedContractQuota ? (user?.contracts_month ?? 0) : (user?.contracts_today ?? 0)
  const contractQuotaLimit = usesExtendedContractQuota ? (user?.max_contracts_per_month ?? 3) : (user?.max_contracts_per_day ?? 3)
  const contractQuotaRatio = contractQuotaLimit ? contractQuotaUsed / contractQuotaLimit : 0

  return (
    <AppLayout title="Загрузка договора">
      <div className="max-w-5xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <h1 className="text-5xl font-bold gradient-text mb-4">Загрузка договора</h1>
          <p className="text-xl text-gray-600">Загрузите договор для автоматического анализа и обработки</p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
              <Card>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Тип документа</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setDocKind('contract')}
                    className={`text-left p-4 rounded-xl border-2 transition-all ${
                      docKind === 'contract'
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <p className="font-bold text-lg">Основной договор</p>
                    <p className="text-sm text-gray-600 mt-1">
                      Самостоятельный договор. Для него можно создавать производные документы.
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDocKind('derivative')}
                    className={`text-left p-4 rounded-xl border-2 transition-all ${
                      docKind === 'derivative'
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <p className="font-bold text-lg">Производный документ</p>
                    <p className="text-sm text-gray-600 mt-1">
                      Доп.соглашение, спецификация, акт, приложение и т. п. — будет привязан к основному договору.
                    </p>
                  </button>
                </div>

                {docKind === 'derivative' && (
                  <div className="mt-6 space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Тип связи</label>
                      <select
                        value={relationType}
                        onChange={(e) => setRelationType(e.target.value as ContractRelationType)}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                      >
                        {relationTypes.map((rt) => (
                          <option key={rt.value} value={rt.value}>
                            {rt.label}
                          </option>
                        ))}
                      </select>
                      {relationType && (
                        <p className="text-xs text-gray-500 mt-1">
                          {relationTypes.find((r) => r.value === relationType)?.description}
                        </p>
                      )}
                    </div>

                    {isCustom && (
                      <>
                        <div>
                          <label className="block text-sm font-medium mb-2">Название кастомного типа</label>
                          <input
                            type="text"
                            value={customLabel}
                            onChange={(e) => setCustomLabel(e.target.value)}
                            placeholder="Напр. «Протокол согласования»"
                            className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">Промпт для генерации/анализа (опционально)</label>
                          <textarea
                            value={customPrompt}
                            onChange={(e) => setCustomPrompt(e.target.value)}
                            rows={3}
                            placeholder="Опишите, как этот документ соотносится с основным…"
                            className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                          />
                        </div>
                      </>
                    )}

                    <div>
                      <label className="block text-sm font-medium mb-2">Основной договор</label>
                      <ContractAutocomplete
                        value={parentContract}
                        onChange={setParentContract}
                        placeholder="Найти основной договор по названию или оставить пустым для автопоиска"
                      />
                      {!parentContract && (
                        <label className="flex items-center gap-2 mt-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={autoFindParent}
                            onChange={(e) => setAutoFindParent(e.target.checked)}
                            className="rounded"
                          />
                          Найти основной автоматически по реквизитам после загрузки
                        </label>
                      )}
                    </div>
                  </div>
                )}
              </Card>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <Card>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Контрагент (опционально)</h2>
                <CounterpartyAutocomplete
                  value={counterparty}
                  onChange={setCounterparty}
                  placeholder="Поиск по названию или ИНН (можно ввести ИНН и создать сразу)"
                />
                <p className="text-xs text-gray-500 mt-2">
                  Если выбрать контрагента — он будет привязан к этому договору. Все договоры можно
                  потом группировать по контрагенту.
                </p>
              </Card>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
              <Card>
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Файл</h2>

                <FileUpload onFileSelect={setSelectedFile} disabled={uploading} />

                {selectedFile && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 p-4 bg-success-50 border border-success-200 rounded-xl flex items-center justify-between"
                  >
                    <div className="flex items-center min-w-0">
                      <svg className="h-8 w-8 text-success-500 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <div className="min-w-0">
                        <p className="font-semibold text-success-900 truncate">{selectedFile.name}</p>
                        <p className="text-sm text-success-700">{(selectedFile.size / 1024 / 1024).toFixed(2)} МБ</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedFile(null)}
                      disabled={uploading}
                      className="p-2 hover:bg-success-100 rounded-lg transition-colors flex-shrink-0"
                    >
                      <svg className="h-5 w-5 text-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </motion.div>
                )}

                {uploading && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-gray-700">Загрузка файла...</span>
                      <span className="text-sm font-bold text-primary-600">{uploadProgress}%</span>
                    </div>
                    <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${uploadProgress}%` }}
                        className="h-full bg-primary-600"
                        transition={{ duration: 0.3 }}
                      />
                    </div>
                  </motion.div>
                )}

                <div className="mt-6">
                  <Button
                    variant="primary"
                    className="w-full"
                    onClick={handleUpload}
                    loading={uploading}
                    disabled={!selectedFile || customRequiresFill}
                  >
                    {uploading ? 'Загрузка...' : 'Загрузить и проанализировать'}
                  </Button>
                </div>
              </Card>
            </motion.div>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <Card className="sticky top-8">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Что произойдёт после загрузки?</h3>
                <Step n={1} title="Парсинг документа" subtitle="Извлечение текста и структуры" />
                <Step n={2} title="AI-анализ" subtitle="Выявление рисков и недочётов" />
                <Step n={3} title="Рекомендации" subtitle="Предложения по улучшению" />
                <Step n={4} title="Отчёт" subtitle="Детальный отчёт с выводами" />

                {docKind === 'derivative' && !parentContract && autoFindParent && (
                  <div className="mt-6 p-3 rounded-xl bg-primary-50 border border-primary-100">
                    <p className="text-sm font-semibold text-primary-700 mb-1">Автопоиск основного договора</p>
                    <p className="text-xs text-primary-700/80">
                      После загрузки система попробует найти основной договор по номеру / дате / ИНН сторон
                      и предложит привязать его одним кликом.
                    </p>
                  </div>
                )}

                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h4 className="text-sm font-bold text-gray-900 mb-3">Поддерживаемые форматы:</h4>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="info" size="sm">PDF</Badge>
                    <Badge variant="info" size="sm">DOCX</Badge>
                    <Badge variant="info" size="sm">XML</Badge>
                  </div>
                </div>

                <div className="mt-4">
                  <h4 className="text-sm font-bold text-gray-900 mb-3">Макс. размер файла:</h4>
                  <Badge variant="default" size="sm">50 МБ</Badge>
                </div>

                {user && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <h4 className="text-sm font-bold text-gray-900 mb-3">
                      Лимит {user.contract_quota_period === 'demo' ? 'на демо' : user.contract_quota_period === 'month' ? 'на месяц' : 'на сегодня'}:
                    </h4>
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between text-xs text-gray-600 mb-1">
                          <span>Загрузок</span>
                          <span className={contractQuotaUsed >= contractQuotaLimit ? 'text-red-600 font-bold' : 'font-semibold'}>
                            {contractQuotaUsed} / {contractQuotaLimit}
                          </span>
                        </div>
                        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              contractQuotaRatio >= 1
                                ? 'bg-red-500'
                                : contractQuotaRatio >= 0.8
                                ? 'bg-amber-500'
                                : 'bg-primary-500'
                            }`}
                            style={{ width: `${Math.min(100, contractQuotaRatio * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            </motion.div>
          </div>
        </div>

        <AnimatePresence>
          {candidatesModal && (
            <motion.div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
              >
                <h2 className="text-2xl font-bold mb-2">Возможные основные договоры</h2>
                <p className="text-sm text-gray-600 mb-4">
                  Мы нашли {candidatesModal.candidates.length} кандидата(ов) по реквизитам из загруженного
                  документа. Выберите подходящий или пропустите — привяжете позже.
                </p>

                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1">Тип связи</label>
                  <select
                    value={postLinkRelationType}
                    onChange={(e) => setPostLinkRelationType(e.target.value as ContractRelationType)}
                    className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                  >
                    {relationTypes.map((rt) => (
                      <option key={rt.value} value={rt.value}>
                        {rt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  {candidatesModal.candidates.map((c) => (
                    <div
                      key={c.contract_id}
                      className="border border-gray-200 rounded-xl p-3 flex items-start justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="font-medium truncate">{c.file_name}</p>
                        <p className="text-xs text-gray-500">
                          {c.contract_number ? `№ ${c.contract_number}` : '—'}
                          {c.contract_date ? ` · от ${new Date(c.contract_date).toLocaleDateString('ru-RU')}` : ''}
                        </p>
                        {c.counterparties.length > 0 && (
                          <p className="text-xs text-gray-500 mt-1">
                            {c.counterparties.map((cp) => cp.name).join(', ')}
                          </p>
                        )}
                        <p className="text-xs text-primary-600 font-semibold mt-1">
                          Уверенность: {Math.round(c.confidence * 100)}%
                          {c.matched_fields.length > 0 && ` · ${c.matched_fields.join(', ')}`}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => attachParent(c.contract_id)}
                        disabled={linking}
                      >
                        Привязать
                      </Button>
                    </div>
                  ))}
                </div>

                <div className="flex justify-end gap-3 mt-6">
                  <Button
                    variant="outline"
                    onClick={() => {
                      const cid = candidatesModal.contractId
                      setCandidatesModal(null)
                      router.push(`/contracts/${cid}`)
                    }}
                  >
                    Пропустить
                  </Button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}

function Step({ n, title, subtitle }: { n: number; title: string; subtitle: string }) {
  return (
    <div className="flex items-start mb-3">
      <div className="flex-shrink-0 w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center mr-3">
        <span className="text-white font-bold text-sm">{n}</span>
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-900">{title}</p>
        <p className="text-xs text-gray-600">{subtitle}</p>
      </div>
    </div>
  )
}
