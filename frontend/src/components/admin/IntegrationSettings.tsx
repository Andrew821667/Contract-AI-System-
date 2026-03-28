'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  useWebhooks,
  useCreateWebhook,
  useDeactivateWebhook,
  useWebhookDeliveries,
  useRetryDeliveries,
  useDomainEvents,
  useEventTypes,
} from '@/hooks/useIntegrations'
import type { WebhookConfig, WebhookDelivery, DomainEvent, EventTypeInfo } from '@/services/api'

type SubTab = 'webhooks' | 'events' | 'types'

const severityColors: Record<string, string> = {
  info: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  warning: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

const statusColors: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  delivered: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

export default function IntegrationSettings() {
  const [subTab, setSubTab] = useState<SubTab>('webhooks')
  const [showCreateWebhook, setShowCreateWebhook] = useState(false)
  const [selectedWebhookId, setSelectedWebhookId] = useState<string | null>(null)

  // Webhook form state
  const [whName, setWhName] = useState('')
  const [whUrl, setWhUrl] = useState('')
  const [whSecret, setWhSecret] = useState('')
  const [whEventFilter, setWhEventFilter] = useState('')

  // Event filters
  const [eventEntityType, setEventEntityType] = useState<string | undefined>(undefined)
  const [eventType, setEventType] = useState<string | undefined>(undefined)

  // Data
  const { data: webhooks = [], isLoading: whLoading } = useWebhooks()
  const { data: deliveries = [], isLoading: delLoading } = useWebhookDeliveries(selectedWebhookId)
  const { data: events = [], isLoading: evLoading } = useDomainEvents({
    entity_type: eventEntityType,
    event_type: eventType,
    limit: 100,
  })
  const { data: eventTypes = [] } = useEventTypes()

  const createWebhook = useCreateWebhook()
  const deactivateWebhook = useDeactivateWebhook()
  const retryDeliveries = useRetryDeliveries()

  const handleCreate = async () => {
    if (!whName.trim() || !whUrl.trim()) return
    const eventFilter = whEventFilter.trim()
      ? whEventFilter.split(',').map(s => s.trim()).filter(Boolean)
      : undefined
    await createWebhook.mutateAsync({
      name: whName.trim(),
      url: whUrl.trim(),
      secret: whSecret.trim() || undefined,
      event_filter: eventFilter,
    })
    setShowCreateWebhook(false)
    setWhName('')
    setWhUrl('')
    setWhSecret('')
    setWhEventFilter('')
  }

  const handleDeactivate = async (id: string) => {
    await deactivateWebhook.mutateAsync(id)
    if (selectedWebhookId === id) setSelectedWebhookId(null)
  }

  const handleRetry = async () => {
    await retryDeliveries.mutateAsync(50)
  }

  const entityTypes = Array.from(new Set(eventTypes.map(et => et.entity_type)))

  return (
    <div>
      {/* Sub-tabs */}
      <div className="flex gap-1 mb-5 bg-gray-50 dark:bg-dark-900 rounded-lg p-1">
        {([
          { key: 'webhooks' as SubTab, label: 'Вебхуки', count: webhooks.filter(w => w.active).length },
          { key: 'events' as SubTab, label: 'События' },
          { key: 'types' as SubTab, label: 'Типы событий', count: eventTypes.length },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setSubTab(t.key)}
            className={`flex-1 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
              subTab === t.key
                ? 'bg-white dark:bg-dark-700 text-gray-800 dark:text-gray-200 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 text-[10px] bg-gray-200 dark:bg-dark-600 px-1.5 py-0.5 rounded-full">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Webhooks ── */}
      {subTab === 'webhooks' && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* Left: webhook list */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">Вебхуки</h3>
              <button
                onClick={() => setShowCreateWebhook(!showCreateWebhook)}
                className="text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                {showCreateWebhook ? 'Отмена' : '+ Создать'}
              </button>
            </div>

            <AnimatePresence>
              {showCreateWebhook && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4 mb-3 overflow-hidden"
                >
                  <input
                    type="text"
                    value={whName}
                    onChange={e => setWhName(e.target.value)}
                    placeholder="Название"
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <input
                    type="url"
                    value={whUrl}
                    onChange={e => setWhUrl(e.target.value)}
                    placeholder="URL (https://...)"
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <input
                    type="text"
                    value={whSecret}
                    onChange={e => setWhSecret(e.target.value)}
                    placeholder="Secret (HMAC, необязательно)"
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <input
                    type="text"
                    value={whEventFilter}
                    onChange={e => setWhEventFilter(e.target.value)}
                    placeholder="Фильтр событий (через запятую, пусто = все)"
                    className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <button
                    onClick={handleCreate}
                    disabled={!whName.trim() || !whUrl.trim() || createWebhook.isPending}
                    className="w-full px-3 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                  >
                    {createWebhook.isPending ? 'Создание...' : 'Создать'}
                  </button>
                  {createWebhook.isError && (
                    <p className="text-[10px] text-red-500 mt-1">
                      {(createWebhook.error as any)?.response?.data?.detail || 'Ошибка создания'}
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {whLoading ? (
              <p className="text-xs text-gray-400 text-center py-6">Загрузка...</p>
            ) : (
              <div className="space-y-2">
                {webhooks.map((wh: WebhookConfig) => (
                  <button
                    key={wh.id}
                    onClick={() => setSelectedWebhookId(wh.id)}
                    className={`w-full text-left p-3 rounded-xl border transition-colors ${
                      selectedWebhookId === wh.id
                        ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/10'
                        : 'border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{wh.name}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        wh.active
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        {wh.active ? 'Активен' : 'Отключён'}
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 font-mono truncate">{wh.config?.url}</p>
                    {wh.config?.event_filter && wh.config.event_filter.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {wh.config.event_filter.slice(0, 3).map((ev, i) => (
                          <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">{ev}</span>
                        ))}
                        {wh.config.event_filter.length > 3 && (
                          <span className="text-[9px] text-gray-400">+{wh.config.event_filter.length - 3}</span>
                        )}
                      </div>
                    )}
                  </button>
                ))}
                {webhooks.length === 0 && !showCreateWebhook && (
                  <p className="text-xs text-gray-400 text-center py-6">Нет вебхуков</p>
                )}
              </div>
            )}
          </div>

          {/* Right: delivery history */}
          <div className="lg:col-span-3">
            {selectedWebhookId ? (
              <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">
                    История доставок
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleRetry}
                      disabled={retryDeliveries.isPending}
                      className="text-[10px] px-2 py-1 bg-amber-600 hover:bg-amber-700 disabled:opacity-40 text-white font-medium rounded-lg transition-colors"
                    >
                      {retryDeliveries.isPending ? 'Retry...' : 'Retry failed'}
                    </button>
                    {webhooks.find(w => w.id === selectedWebhookId)?.active && (
                      <button
                        onClick={() => handleDeactivate(selectedWebhookId)}
                        disabled={deactivateWebhook.isPending}
                        className="text-[10px] px-2 py-1 bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white font-medium rounded-lg transition-colors"
                      >
                        Отключить
                      </button>
                    )}
                  </div>
                </div>

                {delLoading ? (
                  <p className="text-xs text-gray-400 text-center py-6">Загрузка...</p>
                ) : deliveries.length === 0 ? (
                  <p className="text-xs text-gray-400 text-center py-6">Нет доставок</p>
                ) : (
                  <div className="space-y-2 max-h-[500px] overflow-y-auto">
                    {deliveries.map((d: WebhookDelivery) => (
                      <div key={d.id} className="p-3 rounded-lg bg-gray-50 dark:bg-dark-900">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{d.event_type}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusColors[d.status] || ''}`}>
                            {d.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-gray-400">
                          {d.response_code && <span>HTTP {d.response_code}</span>}
                          <span>Попыток: {d.attempts}</span>
                          <span>{new Date(d.created_at).toLocaleString('ru-RU')}</span>
                          {d.delivered_at && <span className="text-green-500">{new Date(d.delivered_at).toLocaleString('ru-RU')}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-sm text-gray-400">Выберите вебхук для просмотра истории доставок</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Events ── */}
      {subTab === 'events' && (
        <div>
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <select
              value={eventEntityType || ''}
              onChange={e => setEventEntityType(e.target.value || undefined)}
              className="bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2 py-1.5 text-xs text-gray-800 dark:text-gray-200"
            >
              <option value="">Все сущности</option>
              {entityTypes.map(et => (
                <option key={et} value={et}>{et}</option>
              ))}
            </select>
            <select
              value={eventType || ''}
              onChange={e => setEventType(e.target.value || undefined)}
              className="bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2 py-1.5 text-xs text-gray-800 dark:text-gray-200"
            >
              <option value="">Все типы</option>
              {eventTypes
                .filter(et => !eventEntityType || et.entity_type === eventEntityType)
                .map(et => (
                  <option key={et.name} value={et.name}>{et.name}</option>
                ))
              }
            </select>
          </div>

          {evLoading ? (
            <p className="text-xs text-gray-400 text-center py-8">Загрузка...</p>
          ) : events.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">Нет событий</p>
          ) : (
            <div className="space-y-2">
              {events.map((ev: DomainEvent) => {
                const typeInfo = eventTypes.find(t => t.name === ev.event_type)
                return (
                  <div key={ev.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{ev.event_type}</span>
                        {typeInfo && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${severityColors[typeInfo.severity] || ''}`}>
                            {typeInfo.severity}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-gray-400">
                        {new Date(ev.created_at).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-gray-400 mb-1">
                      <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700">{ev.entity_type}</span>
                      <span className="font-mono">{ev.entity_id.slice(0, 12)}...</span>
                      {ev.emitted_by && <span>от: {ev.emitted_by}</span>}
                    </div>
                    {ev.payload && Object.keys(ev.payload).length > 0 && (
                      <details className="mt-2">
                        <summary className="text-[10px] text-gray-400 cursor-pointer hover:text-gray-600">
                          Payload
                        </summary>
                        <pre className="text-[10px] text-gray-500 bg-gray-50 dark:bg-dark-900 rounded-lg p-2 mt-1 overflow-x-auto max-h-32">
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Event Types ── */}
      {subTab === 'types' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {eventTypes.map((et: EventTypeInfo) => (
            <div key={et.name} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-medium text-gray-800 dark:text-gray-200">{et.name}</h4>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${severityColors[et.severity] || ''}`}>
                  {et.severity}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{et.description}</p>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">{et.entity_type}</span>
            </div>
          ))}
          {eventTypes.length === 0 && (
            <div className="md:col-span-2 text-center py-8">
              <p className="text-xs text-gray-400">Нет зарегистрированных типов событий</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
