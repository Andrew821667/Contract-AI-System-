'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Objection, NegotiationPosition } from '@/services/api'
import { useStartNegotiation, useGenerateObjections, useSelectObjections, usePreparePosition } from '@/hooks/useNegotiation'
import ObjectionCard from './ObjectionCard'
import PositionView from './PositionView'

interface NegotiationWizardProps {
  documentId: string
  analysisId?: string
  onComplete?: (negotiationId: string) => void
}

type Step = 'goal' | 'objections' | 'selection' | 'position'

export default function NegotiationWizard({ documentId, analysisId, onComplete }: NegotiationWizardProps) {
  const [step, setStep] = useState<Step>('goal')
  const [goal, setGoal] = useState('')
  const [negotiationId, setNegotiationId] = useState<string | null>(null)
  const [objections, setObjections] = useState<Objection[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [position, setPosition] = useState<NegotiationPosition | null>(null)
  const [strategy, setStrategy] = useState('balanced')

  const startNeg = useStartNegotiation()
  const generateObj = useGenerateObjections()
  const selectObj = useSelectObjections()
  const preparePos = usePreparePosition()

  const handleStart = async () => {
    if (!goal.trim()) return
    const result = await startNeg.mutateAsync({
      document_id: documentId,
      goal: goal.trim(),
      analysis_id: analysisId,
    })
    setNegotiationId(result.negotiation_id)
    // Auto-generate objections
    const objs = await generateObj.mutateAsync({
      negotiation_id: result.negotiation_id,
    })
    setObjections(objs)
    setSelectedIds(new Set(objs.map(o => o.objection_id)))
    setStep('objections')
  }

  const handleSelectConfirm = async () => {
    if (!negotiationId || selectedIds.size === 0) return
    await selectObj.mutateAsync({
      negotiation_id: negotiationId,
      selected_objection_ids: Array.from(selectedIds),
    })
    setStep('selection')
  }

  const handlePreparePosition = async () => {
    if (!negotiationId) return
    const pos = await preparePos.mutateAsync({
      negotiation_id: negotiationId,
      strategy,
    })
    setPosition(pos)
    setStep('position')
    onComplete?.(negotiationId)
  }

  const toggleObjection = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const steps: { key: Step; label: string; num: number }[] = [
    { key: 'goal', label: 'Цель', num: 1 },
    { key: 'objections', label: 'Возражения', num: 2 },
    { key: 'selection', label: 'Стратегия', num: 3 },
    { key: 'position', label: 'Позиция', num: 4 },
  ]

  const currentIdx = steps.findIndex(s => s.key === step)

  return (
    <div className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
              i < currentIdx ? 'bg-green-500 text-white' :
              i === currentIdx ? 'bg-primary-600 text-white' :
              'bg-gray-200 dark:bg-dark-700 text-gray-500 dark:text-gray-400'
            }`}>
              {i < currentIdx ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : s.num}
            </div>
            <span className={`text-xs font-medium hidden sm:inline ${
              i === currentIdx ? 'text-gray-800 dark:text-gray-200' : 'text-gray-400 dark:text-gray-500'
            }`}>
              {s.label}
            </span>
            {i < steps.length - 1 && (
              <div className={`w-8 h-0.5 ${i < currentIdx ? 'bg-green-500' : 'bg-gray-200 dark:bg-dark-700'}`} />
            )}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {/* Step 1: Goal */}
        {step === 'goal' && (
          <motion.div
            key="goal"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-6"
          >
            <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">
              Цель переговоров
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Опишите, чего вы хотите добиться в переговорах по этому договору
            </p>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Например: Снизить риски по финансовым условиям и добиться более справедливых условий расторжения"
              rows={3}
              className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-4 py-3 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
            />
            <div className="flex justify-end mt-4">
              <button
                onClick={handleStart}
                disabled={!goal.trim() || startNeg.isPending || generateObj.isPending}
                className="px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                {(startNeg.isPending || generateObj.isPending) && (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                {startNeg.isPending ? 'Запуск...' : generateObj.isPending ? 'Генерация возражений...' : 'Начать переговоры'}
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 2: Objections */}
        {step === 'objections' && (
          <motion.div
            key="objections"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200">
                  AI-возражения ({objections.length})
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Выберите возражения для включения в переговорную позицию
                </p>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
                Выбрано: {selectedIds.size}/{objections.length}
              </span>
            </div>
            <div className="space-y-3">
              {objections.map((obj) => (
                <ObjectionCard
                  key={obj.objection_id}
                  objection={obj}
                  selected={selectedIds.has(obj.objection_id)}
                  onToggle={() => toggleObjection(obj.objection_id)}
                />
              ))}
            </div>
            <div className="flex justify-between mt-6">
              <button
                onClick={() => setStep('goal')}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Назад
              </button>
              <button
                onClick={handleSelectConfirm}
                disabled={selectedIds.size === 0 || selectObj.isPending}
                className="px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Подтвердить выбор
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 3: Strategy */}
        {step === 'selection' && (
          <motion.div
            key="strategy"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-6"
          >
            <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">
              Стратегия переговоров
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Выберите подход к формированию переговорной позиции
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { key: 'aggressive', label: 'Агрессивная', desc: 'Максимальное давление, жёсткие требования', icon: '🔴' },
                { key: 'balanced', label: 'Сбалансированная', desc: 'Баланс интересов, поиск компромисса', icon: '🟡' },
                { key: 'cooperative', label: 'Кооперативная', desc: 'Фокус на долгосрочных отношениях', icon: '🟢' },
              ].map(s => (
                <button
                  key={s.key}
                  onClick={() => setStrategy(s.key)}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    strategy === s.key
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-200 dark:border-dark-700 hover:border-gray-300 dark:hover:border-dark-600'
                  }`}
                >
                  <span className="text-2xl">{s.icon}</span>
                  <p className="text-sm font-bold text-gray-800 dark:text-gray-200 mt-2">{s.label}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{s.desc}</p>
                </button>
              ))}
            </div>
            <div className="flex justify-between mt-6">
              <button
                onClick={() => setStep('objections')}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Назад
              </button>
              <button
                onClick={handlePreparePosition}
                disabled={preparePos.isPending}
                className="px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                {preparePos.isPending && (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                {preparePos.isPending ? 'Подготовка...' : 'Подготовить позицию'}
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 4: Position */}
        {step === 'position' && position && (
          <motion.div
            key="position"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <PositionView position={position} />
            <div className="flex justify-between mt-6">
              <button
                onClick={() => setStep('selection')}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Изменить стратегию
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
