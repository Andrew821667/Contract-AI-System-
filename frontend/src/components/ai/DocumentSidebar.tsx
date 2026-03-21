'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import api from '@/services/api'
import { useAIPanelStore } from '@/stores/aiPanelStore'
import { useAISessions, useCreateAISession } from '@/hooks/useAISession'

export default function DocumentSidebar() {
  const [search, setSearch] = useState('')
  const { selectedDocId, setSelectedDocId, setSessionId } = useAIPanelStore()

  // Fetch user's contracts
  const { data: contractsData, isLoading: loadingContracts } = useQuery({
    queryKey: ['contracts-list'],
    queryFn: () => api.listContracts({ limit: 100 }),
  })

  const contracts = contractsData?.contracts || []
  const filtered = search
    ? contracts.filter((c: any) =>
        c.file_name?.toLowerCase().includes(search.toLowerCase()) ||
        c.contract_type?.toLowerCase().includes(search.toLowerCase())
      )
    : contracts

  // Sessions for selected doc
  const { data: sessionsData, isLoading: loadingSessions } = useAISessions(selectedDocId)
  const sessions = sessionsData?.sessions || []
  const createSession = useCreateAISession()

  const handleNewSession = async () => {
    if (!selectedDocId) return
    try {
      const session = await createSession.mutateAsync({ documentId: selectedDocId })
      setSessionId(session.id)
    } catch {
      // error handled
    }
  }

  const statusIcons: Record<string, string> = {
    pending: '⏳',
    analyzing: '🔄',
    analyzed: '✅',
    error: '❌',
    generated: '📄',
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-dark-700">
        <h2 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-2">Документы</h2>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск..."
          className="w-full text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 text-gray-700 dark:text-gray-300 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto">
        {loadingContracts ? (
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-gray-100 dark:bg-dark-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-4 text-center text-xs text-gray-400 dark:text-gray-500">
            {search ? 'Ничего не найдено' : 'Нет документов'}
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {filtered.map((contract: any) => {
              const isSelected = selectedDocId === String(contract.id)
              return (
                <button
                  key={contract.id}
                  onClick={() => setSelectedDocId(String(contract.id))}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-all ${
                    isSelected
                      ? 'bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-700'
                      : 'hover:bg-gray-50 dark:hover:bg-dark-800 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>{statusIcons[contract.status] || '📄'}</span>
                    <span className={`font-medium truncate ${
                      isSelected ? 'text-primary-700 dark:text-primary-300' : 'text-gray-700 dark:text-gray-300'
                    }`}>
                      {contract.file_name || 'Без имени'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 ml-6">
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {contract.contract_type || '—'}
                    </span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {new Date(contract.created_at).toLocaleDateString('ru-RU')}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Sessions section */}
      <AnimatePresence>
        {selectedDocId && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-gray-200 dark:border-dark-700 overflow-hidden"
          >
            <div className="px-4 py-2 flex items-center justify-between">
              <h3 className="text-xs font-bold text-gray-600 dark:text-gray-400">AI Сессии</h3>
              <button
                onClick={handleNewSession}
                disabled={createSession.isPending}
                className="text-[10px] font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 disabled:opacity-50"
              >
                + Новая
              </button>
            </div>
            <div className="px-2 pb-2 max-h-40 overflow-y-auto">
              {loadingSessions ? (
                <div className="text-center py-2 text-xs text-gray-400">Загрузка...</div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-2 text-xs text-gray-400 dark:text-gray-500">
                  Нет сессий. Создайте новую.
                </div>
              ) : (
                <div className="space-y-0.5">
                  {sessions.map((session: any) => (
                    <button
                      key={session.id}
                      onClick={() => setSessionId(session.id)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${
                        useAIPanelStore.getState().sessionId === session.id
                          ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-800'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate">
                          {session.stage === 'analysis' ? 'Анализ' :
                           session.stage === 'review' ? 'Обзор' :
                           session.stage === 'generation' ? 'Генерация' : session.stage}
                        </span>
                        <span className="text-[10px] text-gray-400 flex-shrink-0 ml-2">
                          {session.turns_count} ход.
                        </span>
                      </div>
                      <div className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                        {new Date(session.created_at).toLocaleString('ru-RU', {
                          day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                        })}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
