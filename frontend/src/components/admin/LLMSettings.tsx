'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import api from '@/services/api'
import type { LLMStageSetting, LLMModel, LLMStageSettingUpdate } from '@/services/api'

const PROVIDER_COLORS: Record<string, string> = {
  deepseek: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  anthropic: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  openai: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  ollama: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
}

interface StageEdits {
  [stageId: string]: {
    model: string
    temperature: number
    max_tokens: number
    enabled: boolean
  }
}

export default function LLMSettings() {
  const queryClient = useQueryClient()
  const [edits, setEdits] = useState<StageEdits>({})
  const [routerMode, setRouterMode] = useState<string>('auto')

  const { data, isLoading, error } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: () => api.getLLMSettings(),
  })

  useEffect(() => {
    if (data) {
      setRouterMode(data.router_mode)
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: async () => {
      const updates: Record<string, LLMStageSettingUpdate> = {}
      for (const [stageId, edit] of Object.entries(edits)) {
        updates[stageId] = edit
      }
      if (Object.keys(updates).length > 0) {
        await api.updateAllLLMSettings(updates)
      }
    },
    onSuccess: () => {
      toast.success('Настройки LLM сохранены')
      setEdits({})
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
    },
    onError: () => {
      toast.error('Ошибка сохранения')
    },
  })

  const routerModeMutation = useMutation({
    mutationFn: (mode: string) => api.updateLLMRouterMode(mode),
    onSuccess: () => {
      toast.success('Режим маршрутизации обновлён')
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => api.resetLLMSettings(),
    onSuccess: () => {
      toast.success('Настройки сброшены к значениям по умолчанию')
      setEdits({})
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
    },
  })

  const getStageValue = useCallback(
    (stage: LLMStageSetting, field: keyof LLMStageSettingUpdate) => {
      if (edits[stage.stage_id] && edits[stage.stage_id][field] !== undefined) {
        return edits[stage.stage_id][field]
      }
      return stage[field]
    },
    [edits]
  )

  const updateStageField = (stageId: string, field: string, value: any, stage: LLMStageSetting) => {
    setEdits((prev) => ({
      ...prev,
      [stageId]: {
        model: prev[stageId]?.model ?? stage.model,
        temperature: prev[stageId]?.temperature ?? stage.temperature,
        max_tokens: prev[stageId]?.max_tokens ?? stage.max_tokens,
        enabled: prev[stageId]?.enabled ?? stage.enabled,
        [field]: value,
      },
    }))
  }

  const hasChanges = Object.keys(edits).length > 0

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-8 text-red-500 text-sm">
        Не удалось загрузить настройки LLM. Проверьте, что бэкенд запущен.
      </div>
    )
  }

  const models = data.available_models
  const stages = data.stages

  return (
    <div className="space-y-6">
      {/* Router Mode Toggle */}
      <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">
              Режим маршрутизации
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {routerMode === 'auto'
                ? 'Smart Router автоматически выбирает модель по сложности документа'
                : 'Фиксированные модели из настроек ниже для каждого этапа'}
            </p>
          </div>
          <div className="flex bg-gray-100 dark:bg-dark-700 rounded-lg p-0.5">
            {['auto', 'manual'].map((mode) => (
              <button
                key={mode}
                onClick={() => {
                  setRouterMode(mode)
                  routerModeMutation.mutate(mode)
                }}
                className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all ${
                  routerMode === mode
                    ? 'bg-white dark:bg-dark-600 text-gray-800 dark:text-gray-200 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {mode === 'auto' ? 'Smart Router' : 'Ручной'}
              </button>
            ))}
          </div>
        </div>

        {routerMode === 'auto' && (
          <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-100 dark:border-blue-800/30">
            <p className="text-xs text-blue-700 dark:text-blue-300">
              <span className="font-semibold">Smart Router:</span>{' '}
              Простые задачи (сложность &lt; 0.4) → Ollama (локально) |{' '}
              Стандартные (0.4-0.8) → DeepSeek |{' '}
              Сложные (&gt; 0.8) → Claude
            </p>
          </div>
        )}
      </div>

      {/* Models Legend */}
      <div className="flex flex-wrap gap-2">
        {models.map((m: LLMModel) => (
          <div
            key={m.id}
            className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-dark-800 rounded-lg border border-gray-200 dark:border-dark-700"
          >
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${PROVIDER_COLORS[m.provider] || 'bg-gray-100 text-gray-600'}`}>
              {m.provider}
            </span>
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{m.name}</span>
            <span className="text-[10px] text-gray-400">
              ${m.cost_input}/{m.cost_output}
            </span>
          </div>
        ))}
      </div>

      {/* Stage Settings */}
      <div className="space-y-3">
        {stages.map((stage: LLMStageSetting) => {
          const currentModel = getStageValue(stage, 'model') as string
          const currentTemp = getStageValue(stage, 'temperature') as number
          const currentTokens = getStageValue(stage, 'max_tokens') as number
          const currentEnabled = getStageValue(stage, 'enabled') as boolean
          const modelInfo = models.find((m: LLMModel) => m.id === currentModel)
          const isEdited = !!edits[stage.stage_id]

          return (
            <motion.div
              key={stage.stage_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`bg-white dark:bg-dark-800 rounded-xl border p-4 transition-colors ${
                isEdited
                  ? 'border-primary-300 dark:border-primary-700'
                  : 'border-gray-200 dark:border-dark-700'
              } ${!currentEnabled ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-gray-800 dark:text-gray-200">
                      {stage.stage_name}
                    </h4>
                    {stage.is_default && !isEdited && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">
                        по умолчанию
                      </span>
                    )}
                    {isEdited && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-100 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300">
                        изменено
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {stage.stage_description}
                  </p>
                </div>

                {/* Enable/Disable toggle */}
                <button
                  onClick={() => updateStageField(stage.stage_id, 'enabled', !currentEnabled, stage)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    currentEnabled ? 'bg-green-500' : 'bg-gray-300 dark:bg-dark-600'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                      currentEnabled ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              {/* Controls row */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Model selector */}
                <div>
                  <label className="block text-[10px] font-semibold text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
                    Модель
                  </label>
                  <select
                    value={currentModel}
                    onChange={(e) => updateStageField(stage.stage_id, 'model', e.target.value, stage)}
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-xs text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  >
                    {models.map((m: LLMModel) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.provider}) — ${m.cost_input}/${ m.cost_output}
                      </option>
                    ))}
                  </select>
                  {modelInfo && (
                    <span className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded font-medium ${PROVIDER_COLORS[modelInfo.provider] || ''}`}>
                      {modelInfo.provider}
                    </span>
                  )}
                </div>

                {/* Temperature */}
                <div>
                  <label className="block text-[10px] font-semibold text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
                    Температура: {currentTemp.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={currentTemp}
                    onChange={(e) => updateStageField(stage.stage_id, 'temperature', parseFloat(e.target.value), stage)}
                    className="w-full h-2 bg-gray-200 dark:bg-dark-700 rounded-lg appearance-none cursor-pointer accent-primary-600"
                  />
                  <div className="flex justify-between text-[9px] text-gray-400 mt-0.5">
                    <span>Точный</span>
                    <span>Креативный</span>
                  </div>
                </div>

                {/* Max Tokens */}
                <div>
                  <label className="block text-[10px] font-semibold text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
                    Макс. токенов
                  </label>
                  <select
                    value={currentTokens}
                    onChange={(e) => updateStageField(stage.stage_id, 'max_tokens', parseInt(e.target.value), stage)}
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-xs text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  >
                    {[512, 1024, 2048, 4096, 8192, 16384].map((v) => (
                      <option key={v} value={v}>{v.toLocaleString()}</option>
                    ))}
                  </select>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-2">
        <button
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending}
          className="px-4 py-2 text-xs font-medium text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
        >
          Сбросить всё к дефолтам
        </button>

        <div className="flex items-center gap-3">
          {hasChanges && (
            <button
              onClick={() => setEdits({})}
              className="px-4 py-2 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-lg transition-colors"
            >
              Отменить
            </button>
          )}
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!hasChanges || saveMutation.isPending}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg transition-colors"
          >
            {saveMutation.isPending ? 'Сохранение...' : 'Сохранить настройки'}
          </button>
        </div>
      </div>
    </div>
  )
}
