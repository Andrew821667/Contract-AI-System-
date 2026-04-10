'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useGraphDocuments, useGraphStats, useGraphPendingCandidates, useGraphReviewCandidate } from '@/hooks/useGraphRAG'

export default function GraphRAGPanel() {
  const [selectedLayer, setSelectedLayer] = useState<string | undefined>(undefined)
  const { data: stats, isLoading: statsLoading } = useGraphStats()
  const { data: docs, isLoading: docsLoading } = useGraphDocuments(selectedLayer, 50)
  const { data: pending } = useGraphPendingCandidates(20)
  const reviewCandidate = useGraphReviewCandidate()

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div>
        <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-3">Статистика графа</h3>
        {statsLoading ? (
          <p className="text-xs text-gray-400">Загрузка...</p>
        ) : stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Документов', value: stats.documents_total ?? 0 },
              { label: 'Узлов', value: stats.nodes_total ?? 0 },
              { label: 'Связей', value: stats.edges_total ?? 0 },
              { label: 'Сущностей', value: stats.entities_total ?? 0 },
            ].map((s) => (
              <div key={s.label} className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-xl p-3 text-center">
                <div className="text-xl font-bold text-primary-600">{s.value}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">Нет данных</p>
        )}

        {stats?.by_layer && Object.keys(stats.by_layer).length > 0 && (
          <div className="mt-3 flex gap-2">
            {Object.entries(stats.by_layer).map(([layer, count]) => (
              <span key={layer} className="text-xs bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-300 px-2 py-1 rounded-full">
                {layer}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Documents */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">Документы в графе</h3>
          <div className="flex gap-1">
            {[undefined, 'contract', 'npa'].map((layer) => (
              <button
                key={layer ?? 'all'}
                onClick={() => setSelectedLayer(layer)}
                className={`px-2.5 py-1 text-[10px] rounded-lg transition-colors ${
                  selectedLayer === layer
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-600'
                }`}
              >
                {layer ?? 'Все'}
              </button>
            ))}
          </div>
        </div>

        {docsLoading ? (
          <p className="text-xs text-gray-400">Загрузка...</p>
        ) : docs?.documents && docs.documents.length > 0 ? (
          <div className="space-y-2">
            {docs.documents.map((doc) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-xl p-3"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{doc.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        doc.layer === 'contract'
                          ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                          : 'bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300'
                      }`}>
                        {doc.layer}
                      </span>
                      <span className="text-[10px] text-gray-400">{doc.document_type}</span>
                      {doc.created_at && (
                        <span className="text-[10px] text-gray-400">
                          {new Date(doc.created_at).toLocaleDateString('ru-RU')}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3 text-[10px] text-gray-500 dark:text-gray-400 flex-shrink-0 ml-2">
                    <span>{doc.nodes_count} узлов</span>
                    <span>{doc.edges_count} связей</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400 text-center py-6">Нет документов в графе</p>
        )}
      </div>

      {/* Pending Candidates */}
      {pending && pending.count > 0 && (
        <div>
          <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-3">
            Ожидают ревью ({pending.count})
          </h3>
          <div className="space-y-2">
            {pending.candidates.map((c) => (
              <div
                key={c.id}
                className="bg-white dark:bg-dark-800 border border-amber-200 dark:border-amber-900/30 rounded-xl p-3"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-800 dark:text-gray-200">
                      {c.proposed_type}
                      <span className="ml-1.5 text-[10px] text-gray-400">({c.proposed_class})</span>
                    </p>
                    <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{c.rationale}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      Уверенность: {Math.round(c.confidence * 100)}%
                    </p>
                  </div>
                  <div className="flex gap-1 flex-shrink-0 ml-2">
                    <button
                      onClick={() => reviewCandidate.mutate({ candidateId: c.id, result: 'accepted' })}
                      disabled={reviewCandidate.isPending}
                      className="p-1.5 text-green-500 hover:bg-green-50 dark:hover:bg-green-900/10 rounded-lg transition-colors"
                      title="Принять"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                    <button
                      onClick={() => reviewCandidate.mutate({ candidateId: c.id, result: 'rejected' })}
                      disabled={reviewCandidate.isPending}
                      className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 rounded-lg transition-colors"
                      title="Отклонить"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
