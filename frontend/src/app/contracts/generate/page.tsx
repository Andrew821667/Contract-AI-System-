'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import api from '@/services/api'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'

type ContractTypeCard = {
  value: string
  label: string
  icon: string
  description: string
  source: 'builtin' | 'analysis'
  hasTemplate?: boolean
}

// Все поимённованные договоры ГК РФ (части II и IV) + практические
const contractTypeMeta: Record<string, { label: string; icon: string; description: string }> = {
  // Передача имущества в собственность (гл. 30–33)
  purchase:        { label: 'Договор купли-продажи', icon: '💰', description: 'Купля-продажа имущества (гл. 30 ГК РФ)' },
  supply:          { label: 'Договор поставки', icon: '📦', description: 'Поставка товаров и продукции (§3 гл. 30)' },
  supply_state:    { label: 'Госконтракт на поставку', icon: '🏛️', description: 'Поставка для государственных нужд (§4 гл. 30)' },
  energy:          { label: 'Договор энергоснабжения', icon: '⚡', description: 'Снабжение энергией (§6 гл. 30)' },
  real_estate_sale:{ label: 'Купля-продажа недвижимости', icon: '🏠', description: 'Продажа недвижимости (§7 гл. 30)' },
  enterprise_sale: { label: 'Продажа предприятия', icon: '🏭', description: 'Продажа предприятия как имущ. комплекса (§8 гл. 30)' },
  exchange:        { label: 'Договор мены', icon: '🔄', description: 'Обмен товарами (гл. 31 ГК РФ)' },
  donation:        { label: 'Договор дарения', icon: '🎁', description: 'Безвозмездная передача имущества (гл. 32)' },
  annuity:         { label: 'Договор ренты', icon: '📅', description: 'Рента и пожизненное содержание (гл. 33)' },
  // Передача имущества в пользование (гл. 34–36)
  lease:           { label: 'Договор аренды', icon: '🏢', description: 'Аренда помещений и имущества (гл. 34)' },
  vehicle_lease:   { label: 'Аренда транспорта', icon: '🚗', description: 'Аренда ТС с/без экипажа (§2–3 гл. 34)' },
  real_estate_lease:{ label: 'Аренда недвижимости', icon: '🏘️', description: 'Аренда зданий и сооружений (§4 гл. 34)' },
  leasing:         { label: 'Договор лизинга (финаренда)', icon: '📋', description: 'Финансовая аренда (§6 гл. 34)' },
  free_use:        { label: 'Договор безвозмездного пользования', icon: '🤝', description: 'Ссуда — безвозмездное пользование (гл. 36)' },
  // Подряд и услуги (гл. 37–41)
  contract_work:   { label: 'Договор подряда', icon: '🏗️', description: 'Подряд, строительство, ремонт (гл. 37)' },
  construction:    { label: 'Договор строительного подряда', icon: '🏛️', description: 'Строительный подряд (§3 гл. 37)' },
  design:          { label: 'Договор на проектные работы', icon: '📐', description: 'Проектные и изыскательские работы (§4 гл. 37)' },
  service:         { label: 'Договор оказания услуг', icon: '🛠️', description: 'Возмездное оказание услуг (гл. 39)' },
  transport:       { label: 'Договор перевозки', icon: '🚛', description: 'Перевозка грузов, пассажиров (гл. 40)' },
  forwarding:      { label: 'Договор транспортной экспедиции', icon: '📬', description: 'Экспедиционные услуги (гл. 41)' },
  // Финансы (гл. 42–46)
  loan:            { label: 'Договор займа', icon: '🏦', description: 'Займ денежных средств (гл. 42)' },
  credit:          { label: 'Кредитный договор', icon: '💳', description: 'Банковский кредит (§2 гл. 42)' },
  factoring:       { label: 'Договор факторинга', icon: '📊', description: 'Финансирование под уступку требования (гл. 43)' },
  bank_account:    { label: 'Договор банковского счёта', icon: '🏧', description: 'Банковский счёт (гл. 45)' },
  // Хранение и страхование (гл. 47–48)
  storage:         { label: 'Договор хранения', icon: '📦', description: 'Хранение имущества (гл. 47)' },
  insurance:       { label: 'Договор страхования', icon: '🛡️', description: 'Имущественное/личное страхование (гл. 48)' },
  // Поручения и комиссия (гл. 49–52)
  mandate:         { label: 'Договор поручения', icon: '✍️', description: 'Юридические действия от имени доверителя (гл. 49)' },
  commission:      { label: 'Договор комиссии', icon: '🤝', description: 'Комиссионная торговля (гл. 51)' },
  agency:          { label: 'Агентский договор', icon: '👥', description: 'Агентские действия от своего/чужого имени (гл. 52)' },
  // Управление и концессия (гл. 53–54)
  trust_management:{ label: 'Договор доверительного управления', icon: '⚖️', description: 'Доверительное управление имуществом (гл. 53)' },
  franchise:       { label: 'Договор коммерческой концессии', icon: '🏪', description: 'Франчайзинг (гл. 54)' },
  // Трудовые и интеллект. собственность
  employment:      { label: 'Трудовой договор', icon: '👔', description: 'Трудовые отношения (ТК РФ)' },
  licensing:       { label: 'Лицензионный договор', icon: '📄', description: 'Передача прав на использование (ч. IV ГК РФ)' },
  confidentiality: { label: 'Соглашение о конфиденциальности (NDA)', icon: '🔒', description: 'Защита конфиденциальной информации' },
}

const defaultContractTypes: ContractTypeCard[] = Object.entries(contractTypeMeta).map(([value, meta]) => ({
  value,
  label: meta.label,
  icon: meta.icon,
  description: meta.description,
  source: 'builtin',
  hasTemplate: ['supply', 'service', 'lease', 'purchase', 'loan', 'employment', 'contract_work', 'confidentiality'].includes(value),
}))

interface TemplateItem {
  id: string;
  name: string;
  type: string;
  source_file_name?: string;
}

export default function GenerateContractPage() {
  const { isReady } = useAuthGuard()
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [generating, setGenerating] = useState(false)
  const [contractTypes, setContractTypes] = useState<ContractTypeCard[]>(defaultContractTypes)
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [loadingTemplates, setLoadingTemplates] = useState(false)

  // Load templates from API when contract type changes
  const loadTemplates = async (contractType: string) => {
    setLoadingTemplates(true)
    try {
      const data = await api.listTemplates(contractType)
      setTemplates(data.map(t => ({
        id: t.id,
        name: t.name,
        type: t.contract_type,
        source_file_name: t.source_file_name,
      })))
    } catch {
      setTemplates([])
    } finally {
      setLoadingTemplates(false)
    }
  }
  const [formData, setFormData] = useState({
    contractType: '',
    templateId: '',
    partyA: '',
    partyB: '',
    amount: '',
    startDate: '',
    endDate: '',
    additionalTerms: '',
  })

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    if (field === 'contractType') {
      setFormData(prev => ({ ...prev, contractType: value, templateId: '' }))
      loadTemplates(value)
    }
  }

  useEffect(() => {
    let active = true

    api.getGenerationContractTypes()
      .then((items) => {
        if (!active || !items.length) return

        const mapped: ContractTypeCard[] = items.map((item) => {
          const known = contractTypeMeta[item.code]
          return {
            value: item.code,
            label: item.name || known?.label || item.code,
            icon: known?.icon || (item.source === 'analysis' ? '🧠' : '🧾'),
            description: known?.description || (
              item.source === 'analysis'
                ? 'Добавлен автоматически из ранее проанализированного договора'
                : 'Тип договора'
            ),
            source: item.source === 'analysis' ? 'analysis' : 'builtin',
            hasTemplate: item.has_template,
          }
        })

        setContractTypes(mapped)
      })
      .catch(() => {
        if (active) {
          setContractTypes(defaultContractTypes)
        }
      })

    return () => {
      active = false
    }
  }, [])

  const availableTemplates = useMemo(
    () => templates.filter((t) => t.type === formData.contractType),
    [formData.contractType]
  )

  const selectedType = useMemo(
    () => contractTypes.find((type) => type.value === formData.contractType),
    [contractTypes, formData.contractType]
  )

  const handleGenerate = async () => {
    setGenerating(true)

    try {
      const result = await api.generateContract({
        contract_type: formData.contractType,
        template_id: formData.templateId || undefined,
        params: {
          party_a: formData.partyA,
          party_b: formData.partyB,
          amount: formData.amount,
          start_date: formData.startDate,
          end_date: formData.endDate,
          additional_terms: formData.additionalTerms,
        },
      })

      toast.success('Договор успешно сгенерирован!')
      router.push(`/contracts/${result.contract_id}`)
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Ошибка генерации договора'
      toast.error(message)
    } finally {
      setGenerating(false)
    }
  }

  const isStep1Valid = Boolean(formData.contractType) && (availableTemplates.length === 0 || Boolean(formData.templateId))
  const isStep2Valid = formData.partyA && formData.partyB && formData.amount

  if (!isReady) return null

  return (
    <AppLayout title="Генерация договора">
      <div className="max-w-4xl mx-auto">

        {/* Progress Steps */}
        <div className="flex items-center justify-between mb-8">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all ${
                  step >= s
                    ? 'bg-primary-600 text-white'
                    : 'bg-stone-200 text-stone-400'
                }`}
              >
                {s}
              </div>
              {s < 3 && (
                <div
                  className={`flex-1 h-1 mx-2 transition-all ${
                    step > s ? 'bg-primary-600' : 'bg-stone-200'
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Choose Contract Type */}
        {step === 1 && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <Card className="mb-6">
              <h2 className="text-2xl font-bold mb-4">Шаг 1: Выберите тип договора</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {contractTypes.map((type) => (
                  <motion.div
                    key={type.value}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setFormData((prev) => ({ ...prev, contractType: type.value, templateId: '' }))}
                    className={`p-4 border-2 rounded-xl cursor-pointer transition-all ${
                      formData.contractType === type.value
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-stone-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-3xl">{type.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-stone-800">
                            {type.label}
                          </h3>
                          {type.source === 'analysis' && (
                            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wide rounded-full bg-amber-100 text-amber-700">
                              Из анализа
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-stone-600">{type.description}</p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </Card>

            {formData.contractType && (
              <Card>
                <h2 className="text-2xl font-bold mb-4">Шаблон</h2>
                {loadingTemplates ? (
                  <p className="text-stone-500 py-4 text-center">Загрузка шаблонов...</p>
                ) : availableTemplates.length > 0 ? (
                  <div className="space-y-3">
                    {availableTemplates.map((template) => (
                      <motion.div
                        key={template.id}
                        whileHover={{ scale: 1.01 }}
                        onClick={() => handleInputChange('templateId', template.id)}
                        className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                          formData.templateId === template.id
                            ? 'border-primary-500 bg-primary-50'
                            : 'border-stone-200 hover:border-primary-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-semibold text-stone-800">
                              {template.name}
                            </h4>
                            {template.source_file_name && (
                              <p className="text-sm text-stone-500">
                                Создан из: {template.source_file_name}
                              </p>
                            )}
                          </div>
                          {formData.templateId === template.id && (
                            <span className="text-primary-500 text-xl">✓</span>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900">
                    <p className="font-semibold mb-1">
                      Для типа «{selectedType?.label || formData.contractType}» отдельный шаблон пока не найден.
                    </p>
                    <p className="text-sm">
                      Генерация будет выполнена в универсальном AI-режиме без заранее заданного шаблона.
                    </p>
                  </div>
                )}
              </Card>
            )}

            <div className="flex justify-end mt-6">
              <Button
                onClick={() => setStep(2)}
                disabled={!isStep1Valid}
              >
                Далее →
              </Button>
            </div>
          </motion.div>
        )}

        {/* Step 2: Fill Details */}
        {step === 2 && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <Card>
              <h2 className="text-2xl font-bold mb-6">Шаг 2: Заполните детали договора</h2>

              <div className="space-y-6">
                {/* Parties */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-stone-700 mb-2">
                      Сторона А (Заказчик/Покупатель)
                    </label>
                    <input
                      type="text"
                      value={formData.partyA}
                      onChange={(e) => handleInputChange('partyA', e.target.value)}
                      placeholder="ООО 'Компания'"
                      className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 mb-2">
                      Сторона Б (Исполнитель/Продавец)
                    </label>
                    <input
                      type="text"
                      value={formData.partyB}
                      onChange={(e) => handleInputChange('partyB', e.target.value)}
                      placeholder="ООО 'Контрагент'"
                      className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                {/* Amount */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-2">
                    Сумма договора (₽)
                  </label>
                  <input
                    type="number"
                    value={formData.amount}
                    onChange={(e) => handleInputChange('amount', e.target.value)}
                    placeholder="100000"
                    min="0"
                    className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                {/* Dates */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-stone-700 mb-2">
                      Дата начала
                    </label>
                    <input
                      type="date"
                      value={formData.startDate}
                      onChange={(e) => handleInputChange('startDate', e.target.value)}
                      className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 mb-2">
                      Дата окончания (опционально)
                    </label>
                    <input
                      type="date"
                      value={formData.endDate}
                      onChange={(e) => handleInputChange('endDate', e.target.value)}
                      className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                {/* Additional Terms */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-2">
                    Дополнительные условия (опционально)
                  </label>
                  <textarea
                    value={formData.additionalTerms}
                    onChange={(e) => handleInputChange('additionalTerms', e.target.value)}
                    placeholder="Укажите особые условия договора..."
                    rows={4}
                    className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
            </Card>

            <div className="flex justify-between mt-6">
              <Button variant="outline" onClick={() => setStep(1)}>
                ← Назад
              </Button>
              <Button onClick={() => setStep(3)} disabled={!isStep2Valid}>
                Далее →
              </Button>
            </div>
          </motion.div>
        )}

        {/* Step 3: Review & Generate */}
        {step === 3 && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <Card className="mb-6">
              <h2 className="text-2xl font-bold mb-6">Шаг 3: Проверьте и сгенерируйте</h2>

              <div className="space-y-4">
                <div className="p-4 bg-stone-50 rounded-lg">
                  <h3 className="font-semibold text-stone-700 mb-2">Тип договора</h3>
                  <p className="text-stone-900">
                    {contractTypes.find((t) => t.value === formData.contractType)?.label}
                  </p>
                </div>

                <div className="p-4 bg-stone-50 rounded-lg">
                  <h3 className="font-semibold text-stone-700 mb-2">Шаблон</h3>
                  <p className="text-stone-900">
                    {templates.find((t) => t.id === formData.templateId)?.name}
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-stone-50 rounded-lg">
                    <h3 className="font-semibold text-stone-700 mb-2">Сторона А</h3>
                    <p className="text-stone-900">{formData.partyA}</p>
                  </div>
                  <div className="p-4 bg-stone-50 rounded-lg">
                    <h3 className="font-semibold text-stone-700 mb-2">Сторона Б</h3>
                    <p className="text-stone-900">{formData.partyB}</p>
                  </div>
                </div>

                <div className="p-4 bg-stone-50 rounded-lg">
                  <h3 className="font-semibold text-stone-700 mb-2">Сумма</h3>
                  <p className="text-stone-900">
                    {Number(formData.amount).toLocaleString('ru-RU')} ₽
                  </p>
                </div>

                {formData.startDate && (
                  <div className="p-4 bg-stone-50 rounded-lg">
                    <h3 className="font-semibold text-stone-700 mb-2">Срок действия</h3>
                    <p className="text-stone-900">
                      С {formData.startDate}
                      {formData.endDate && ` по ${formData.endDate}`}
                    </p>
                  </div>
                )}

                {formData.additionalTerms && (
                  <div className="p-4 bg-stone-50 rounded-lg">
                    <h3 className="font-semibold text-stone-700 mb-2">
                      Дополнительные условия
                    </h3>
                    <p className="text-stone-900 whitespace-pre-wrap">
                      {formData.additionalTerms}
                    </p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="bg-stone-50 border-2 border-primary-200">
              <div className="flex items-start gap-4">
                <span className="text-3xl">✨</span>
                <div className="flex-1">
                  <h3 className="font-bold text-stone-800 mb-2">
                    Готовы к генерации?
                  </h3>
                  <p className="text-stone-600 mb-4">
                    AI создаст профессиональный договор на основе указанных данных.
                    Процесс займёт около 30 секунд.
                  </p>
                  <ul className="space-y-2 text-sm text-stone-600 mb-4">
                    <li className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      Соответствие ГК РФ
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      Защита интересов сторон
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      Готовность к подписанию
                    </li>
                  </ul>
                </div>
              </div>
            </Card>

            <div className="flex justify-between mt-6">
              <Button variant="outline" onClick={() => setStep(2)}>
                ← Назад
              </Button>
              <Button
                onClick={handleGenerate}
                loading={generating}
              >
                {generating ? 'Генерация...' : 'Сгенерировать договор'}
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </AppLayout>
  )
}
