'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import PlanStepItem from './PlanStepItem'
import { useOrchestratorRun, useRunSteps, useCreateRun, useContinueRun, useCancelRun } from '@/hooks/useOrchestratorRun'
import { useAIPanelStore } from '@/stores/aiPanelStore'

interface ExecutionPlanProps {
  compact?: boolean
}

export default function ExecutionPlan({ compact }: ExecutionPlanProps) {
  const [goal, setGoal] = useState('')
  const { runId, setRunId, selectedDocId } = useAIPanelStore()

  const { data: run } = useOrchestratorRun(runId)
  const { data: stepsData } = useRunSteps(runId)
  const createRun = useCreateRun()
  const continueRun = useContinueRun()
  const cancelRun = useCancelRun()

  const steps = stepsData?.steps || []
  const isActive = run?.status === 'running' || run?.status === 'planning'
  const isPaused = run?.status === 'paused'
  const isFinished = run?.status === 'completed' || run?.status === 'failed' || run?.status === 'cancelled'

  const handleLaunch = async () => {
    if (!goal.trim()) return
    try {
      const newRun = await createRun.mutateAsync({
        goal: goal.trim(),
        documentId: selectedDocId || undefined,
      })
      setRunId(newRun.id)
      setGoal('')
    } catch {
      // error handled by react-query
    }
  }

  const progressPercent = run ? Math.round((run.steps_completed / Math.max(run.steps_total, 1)) * 100) : 0

  return (
    <div className={`flex flex-col ${compact ? 'gap-3' : 'gap-4'}`}>
      {/* Goal input */}
      <div>
        <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 block">
          Цель
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLaunch()}
            placeholder="Например: Проанализировать риски и создать отчёт"
            disabled={isActive}
            className={`flex-1 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-lg px-3 text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50 ${compact ? 'py-1.5 text-xs' : 'py-2 text-sm'}`}
          />
          <button
            onClick={handleLaunch}
            disabled={isActive || !goal.trim() || createRun.isPending}
            className={`flex-shrink-0 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white rounded-lg font-medium transition-colors ${compact ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'}`}
          >
            {createRun.isPending ? '...' : 'Запустить'}
          </button>
        </div>
      </div>

      {/* Active run */}
      {run && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-xl p-4"
        >
          {/* Run header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {isActive && (
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              )}
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                isActive ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                isPaused ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
                run.status === 'completed' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                run.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
              }`}>
                {run.status === 'running' ? 'Выполняется' :
                 run.status === 'planning' ? 'Планирование' :
                 run.status === 'paused' ? 'Пауза' :
                 run.status === 'completed' ? 'Завершено' :
                 run.status === 'failed' ? 'Ошибка' : 'Отменено'}
              </span>
            </div>
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              {run.steps_completed}/{run.steps_total} шагов
            </span>
          </div>

          {/* Goal display */}
          <p className={`${compact ? 'text-xs' : 'text-sm'} text-gray-700 dark:text-gray-300 mb-3`}>
            {run.goal}
          </p>

          {/* Progress bar */}
          <div className="h-1.5 bg-gray-100 dark:bg-dark-700 rounded-full overflow-hidden mb-3">
            <motion.div
              className={`h-full rounded-full ${
                run.status === 'failed' ? 'bg-red-500' :
                run.status === 'completed' ? 'bg-green-500' : 'bg-primary-500'
              }`}
              initial={{ width: 0 }}
              animate={{ width: `${progressPercent}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>

          {/* Steps list */}
          {steps.length > 0 && (
            <div className={`border-t border-gray-100 dark:border-dark-700 pt-2 ${compact ? 'max-h-48' : 'max-h-64'} overflow-y-auto`}>
              {steps.map((step) => (
                <PlanStepItem key={step.id} step={step} compact={compact} />
              ))}
            </div>
          )}

          {/* Error display */}
          {run.error && (
            <div className="mt-2 text-xs text-red-500 bg-red-50 dark:bg-red-900/20 rounded-lg p-2">
              {run.error}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 mt-3">
            {isPaused && (
              <button
                onClick={() => continueRun.mutate(run.id)}
                disabled={continueRun.isPending}
                className="text-xs font-medium px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white transition-colors disabled:opacity-50"
              >
                Продолжить
              </button>
            )}
            {(isActive || isPaused) && (
              <button
                onClick={() => cancelRun.mutate(run.id)}
                disabled={cancelRun.isPending}
                className="text-xs font-medium px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-dark-700 dark:hover:bg-dark-600 dark:text-gray-300 transition-colors disabled:opacity-50"
              >
                Отменить
              </button>
            )}
            {isFinished && (
              <button
                onClick={() => setRunId(null)}
                className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                Закрыть
              </button>
            )}
          </div>

          {/* Context info */}
          {run.tokens_used && !compact && (
            <div className="mt-3 pt-2 border-t border-gray-100 dark:border-dark-700 flex items-center gap-4 text-[10px] text-gray-400 dark:text-gray-500">
              {run.tokens_used && <span>Токены: {run.tokens_used.toLocaleString()}</span>}
              {run.model && <span>Модель: {run.model}</span>}
              <span>{new Date(run.created_at).toLocaleString('ru-RU')}</span>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
