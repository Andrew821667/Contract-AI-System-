'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import api from '@/services/api'

const contractTypes = [
  { value: 'supply', label: 'Договор поставки', icon: '📦', description: 'Поставка товаров и продукции' },
  { value: 'service', label: 'Договор оказания услуг', icon: '🛠️', description: 'Оказание различных услуг' },
  { value: 'lease', label: 'Договор аренды', icon: '🏢', description: 'Аренда помещений и имущества' },
  { value: 'purchase', label: 'Договор купли-продажи', icon: '💰', description: 'Купля-продажа имущества' },
  { value: 'confidentiality', label: 'Соглашение о конфиденциальности (NDA)', icon: '🔒', description: 'Защита конфиденциальной информации' },
  { value: 'employment', label: 'Трудовой договор', icon: '👔', description: 'Трудовые отношения' },
]

const templates = [
  { id: 'tpl_supply_001', name: 'Базовый шаблон поставки', type: 'supply' },
  { id: 'tpl_service_001', name: 'Базовый шаблон услуг', type: 'service' },
  { id: 'tpl_lease_001', name: 'Базовый шаблон аренды', type: 'lease' },
]

export default function GenerateContractPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [generating, setGenerating] = useState(false)
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
  }

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

  const isStep1Valid = formData.contractType && formData.templateId
  const isStep2Valid = formData.partyA && formData.partyB && formData.amount

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <Button
            variant="outline"
            onClick={() => router.back()}
            className="mb-4"
          >
            ← Назад
          </Button>
          <h1 className="text-4xl font-bold gradient-text mb-2">
            Генератор договоров
          </h1>
          <p className="text-slate-600">
            Создайте профессиональный договор за несколько минут с помощью AI
          </p>
        </motion.div>

        {/* Progress Steps */}
        <div className="flex items-center justify-between mb-8">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all ${
                  step >= s
                    ? 'bg-gradient-primary text-white'
                    : 'bg-slate-200 text-slate-400'
                }`}
              >
                {s}
              </div>
              {s < 3 && (
                <div
                  className={`flex-1 h-1 mx-2 transition-all ${
                    step > s ? 'bg-gradient-primary' : 'bg-slate-200'
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
                    onClick={() => handleInputChange('contractType', type.value)}
                    className={`p-4 border-2 rounded-xl cursor-pointer transition-all ${
                      formData.contractType === type.value
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-slate-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-3xl">{type.icon}</span>
                      <div className="flex-1">
                        <h3 className="font-semibold text-slate-800 mb-1">
                          {type.label}
                        </h3>
                        <p className="text-sm text-slate-600">{type.description}</p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </Card>

            {formData.contractType && (
              <Card>
                <h2 className="text-2xl font-bold mb-4">Выберите шаблон</h2>
                <div className="space-y-3">
                  {templates
                    .filter((t) => t.type === formData.contractType)
                    .map((template) => (
                      <motion.div
                        key={template.id}
                        whileHover={{ scale: 1.01 }}
                        onClick={() => handleInputChange('templateId', template.id)}
                        className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                          formData.templateId === template.id
                            ? 'border-primary-500 bg-primary-50'
                            : 'border-slate-200 hover:border-primary-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-semibold text-slate-800">
                              {template.name}
                            </h4>
                            <p className="text-sm text-slate-500">{template.id}</p>
                          </div>
                          {formData.templateId === template.id && (
                            <span className="text-primary-500 text-xl">✓</span>
                          )}
                        </div>
                      </motion.div>
                    ))}
                </div>
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
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Сторона А (Заказчик/Покупатель)
                    </label>
                    <input
                      type="text"
                      value={formData.partyA}
                      onChange={(e) => handleInputChange('partyA', e.target.value)}
                      placeholder="ООО 'Компания'"
                      className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Сторона Б (Исполнитель/Продавец)
                    </label>
                    <input
                      type="text"
                      value={formData.partyB}
                      onChange={(e) => handleInputChange('partyB', e.target.value)}
                      placeholder="ООО 'Контрагент'"
                      className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                {/* Amount */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Сумма договора (₽)
                  </label>
                  <input
                    type="number"
                    value={formData.amount}
                    onChange={(e) => handleInputChange('amount', e.target.value)}
                    placeholder="100000"
                    min="0"
                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                {/* Dates */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Дата начала
                    </label>
                    <input
                      type="date"
                      value={formData.startDate}
                      onChange={(e) => handleInputChange('startDate', e.target.value)}
                      className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Дата окончания (опционально)
                    </label>
                    <input
                      type="date"
                      value={formData.endDate}
                      onChange={(e) => handleInputChange('endDate', e.target.value)}
                      className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                {/* Additional Terms */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Дополнительные условия (опционально)
                  </label>
                  <textarea
                    value={formData.additionalTerms}
                    onChange={(e) => handleInputChange('additionalTerms', e.target.value)}
                    placeholder="Укажите особые условия договора..."
                    rows={4}
                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
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
                <div className="p-4 bg-slate-50 rounded-lg">
                  <h3 className="font-semibold text-slate-700 mb-2">Тип договора</h3>
                  <p className="text-slate-900">
                    {contractTypes.find((t) => t.value === formData.contractType)?.label}
                  </p>
                </div>

                <div className="p-4 bg-slate-50 rounded-lg">
                  <h3 className="font-semibold text-slate-700 mb-2">Шаблон</h3>
                  <p className="text-slate-900">
                    {templates.find((t) => t.id === formData.templateId)?.name}
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <h3 className="font-semibold text-slate-700 mb-2">Сторона А</h3>
                    <p className="text-slate-900">{formData.partyA}</p>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <h3 className="font-semibold text-slate-700 mb-2">Сторона Б</h3>
                    <p className="text-slate-900">{formData.partyB}</p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 rounded-lg">
                  <h3 className="font-semibold text-slate-700 mb-2">Сумма</h3>
                  <p className="text-slate-900">
                    {Number(formData.amount).toLocaleString('ru-RU')} ₽
                  </p>
                </div>

                {formData.startDate && (
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <h3 className="font-semibold text-slate-700 mb-2">Срок действия</h3>
                    <p className="text-slate-900">
                      С {formData.startDate}
                      {formData.endDate && ` по ${formData.endDate}`}
                    </p>
                  </div>
                )}

                {formData.additionalTerms && (
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <h3 className="font-semibold text-slate-700 mb-2">
                      Дополнительные условия
                    </h3>
                    <p className="text-slate-900 whitespace-pre-wrap">
                      {formData.additionalTerms}
                    </p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-primary-200">
              <div className="flex items-start gap-4">
                <span className="text-3xl">✨</span>
                <div className="flex-1">
                  <h3 className="font-bold text-slate-800 mb-2">
                    Готовы к генерации?
                  </h3>
                  <p className="text-slate-600 mb-4">
                    AI создаст профессиональный договор на основе указанных данных.
                    Процесс займёт около 30 секунд.
                  </p>
                  <ul className="space-y-2 text-sm text-slate-600 mb-4">
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
                className="bg-gradient-primary"
              >
                {generating ? 'Генерация...' : '✨ Сгенерировать договор'}
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
