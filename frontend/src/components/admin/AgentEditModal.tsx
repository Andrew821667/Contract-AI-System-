'use client'

import { useState, useEffect } from 'react'
import { AgentDefinition, AgentDefinitionUpdate } from '@/services/api'
import { useTools } from '@/hooks/useOrganization'

const AUTONOMY_LEVELS = [
  { value: 'advisor', label: 'Советник — только рекомендации' },
  { value: 'copilot', label: 'Копилот — действует с подтверждением' },
  { value: 'processor', label: 'Процессор — автоматически' },
  { value: 'autonomous', label: 'Автономный — полная самостоятельность' },
]

const LLM_PROVIDERS = ['deepseek', 'openai', 'anthropic', 'yandex', 'qwen', 'ollama']
const LLM_MODELS: Record<string, string[]> = {
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
  yandex: ['yandexgpt-lite', 'yandexgpt'],
  qwen: ['qwen-plus', 'qwen-max'],
  ollama: ['qwen3:7b', 'llama3:8b', 'mistral:7b'],
}

interface Props {
  agent: AgentDefinition
  onSave: (agentId: string, data: AgentDefinitionUpdate) => void
  onClose: () => void
  saving: boolean
}

export default function AgentEditModal({ agent, onSave, onClose, saving }: Props) {
  const { data: allTools = [] } = useTools()

  const [allowedTools, setAllowedTools] = useState<string[]>(agent.allowed_tools ?? agent.tools ?? [])
  const [autonomyLevel, setAutonomyLevel] = useState(agent.autonomy_level ?? 'copilot')
  const [confidenceThreshold, setConfidenceThreshold] = useState(agent.confidence_threshold ?? 0.8)
  const [active, setActive] = useState(agent.active)
  const [description, setDescription] = useState(agent.description ?? '')

  const initProfile = agent.model_profile ?? {}
  const [provider, setProvider] = useState<string>(initProfile.provider ?? 'deepseek')
  const [model, setModel] = useState<string>(initProfile.model ?? '')
  const [temperature, setTemperature] = useState<number>(initProfile.temperature ?? 0.7)
  const [maxTokens, setMaxTokens] = useState<number>(initProfile.max_tokens ?? 4000)

  // When provider changes, reset model to first available
  useEffect(() => {
    const models = LLM_MODELS[provider] ?? []
    if (!models.includes(model)) setModel(models[0] ?? '')
  }, [provider])

  const toggleTool = (toolName: string) => {
    setAllowedTools(prev =>
      prev.includes(toolName) ? prev.filter(t => t !== toolName) : [...prev, toolName]
    )
  }

  const handleSave = () => {
    const data: AgentDefinitionUpdate = {
      allowed_tools: allowedTools,
      autonomy_level: autonomyLevel,
      confidence_threshold: confidenceThreshold,
      active,
      description: description || undefined,
      model_profile: { provider, model, temperature, max_tokens: maxTokens },
    }
    onSave(agent.id, data)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-dark-700">
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-gray-100">
              Редактировать агента
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 font-mono">{agent.agent_id ?? agent.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">✕</button>
        </div>

        <div className="p-5 space-y-6">
          {/* Active toggle */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Активен</span>
            <button
              onClick={() => setActive(v => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${active ? 'bg-primary-600' : 'bg-gray-300 dark:bg-dark-600'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${active ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={2}
              className="w-full text-sm rounded-lg border border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 px-3 py-2 text-gray-800 dark:text-gray-200 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* Autonomy level */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Уровень автономности</label>
            <div className="grid grid-cols-2 gap-2">
              {AUTONOMY_LEVELS.map(lvl => (
                <button
                  key={lvl.value}
                  onClick={() => setAutonomyLevel(lvl.value)}
                  className={`text-left text-xs px-3 py-2 rounded-lg border transition-colors ${
                    autonomyLevel === lvl.value
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 font-semibold'
                      : 'border-gray-200 dark:border-dark-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'
                  }`}
                >
                  {lvl.label}
                </button>
              ))}
            </div>
          </div>

          {/* Confidence threshold */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
              Порог уверенности: <span className="text-primary-600 font-bold">{confidenceThreshold.toFixed(2)}</span>
            </label>
            <input
              type="range" min={0.5} max={1.0} step={0.05}
              value={confidenceThreshold}
              onChange={e => setConfidenceThreshold(parseFloat(e.target.value))}
              className="w-full accent-primary-600"
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
              <span>0.50 (мягкий)</span><span>1.00 (строгий)</span>
            </div>
          </div>

          {/* LLM Profile */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Языковая модель</label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">Провайдер</label>
                <select
                  value={provider}
                  onChange={e => setProvider(e.target.value)}
                  className="w-full text-sm rounded-lg border border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 px-2 py-1.5 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {LLM_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">Модель</label>
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="w-full text-sm rounded-lg border border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 px-2 py-1.5 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {(LLM_MODELS[provider] ?? []).map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">Temperature: {temperature}</label>
                <input
                  type="range" min={0} max={1} step={0.05}
                  value={temperature}
                  onChange={e => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-primary-600"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">Max tokens</label>
                <select
                  value={maxTokens}
                  onChange={e => setMaxTokens(parseInt(e.target.value))}
                  className="w-full text-sm rounded-lg border border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 px-2 py-1.5 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {[1000, 2000, 4000, 8000, 16000, 32000].map(v => <option key={v} value={v}>{v.toLocaleString()}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Tools */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
              Инструменты ({allowedTools.length} выбрано)
            </label>
            {allTools.length === 0 ? (
              <p className="text-xs text-gray-400">Инструменты не зарегистрированы</p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto pr-1">
                {allTools.map((t: any) => {
                  const toolName = t.name ?? t.tool_id ?? t.id
                  const checked = allowedTools.includes(toolName)
                  return (
                    <button
                      key={toolName}
                      onClick={() => toggleTool(toolName)}
                      className={`text-left text-xs px-2.5 py-1.5 rounded-lg border transition-colors flex items-center gap-1.5 ${
                        checked
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                          : 'border-gray-200 dark:border-dark-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'
                      }`}
                    >
                      <span className={`w-3 h-3 rounded border flex-shrink-0 flex items-center justify-center text-[9px] ${
                        checked ? 'bg-primary-500 border-primary-500 text-white' : 'border-gray-300 dark:border-dark-500'
                      }`}>
                        {checked ? '✓' : ''}
                      </span>
                      <span className="font-mono truncate">{toolName}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-200 dark:border-dark-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 text-sm font-semibold bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition disabled:opacity-50"
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}
