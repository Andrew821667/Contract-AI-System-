'use client'

import { Suspense, useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'
import NegotiationWizard from '@/components/negotiations/NegotiationWizard'
import CommentThread from '@/components/negotiations/CommentThread'
import { useNegotiation } from '@/hooks/useNegotiation'
import { useVersionHistory, useCompareVersions } from '@/hooks/useVersionIntelligence'
import type { VersionHistoryItem, VersionCompareResult } from '@/services/api'

type Tab = 'negotiate' | 'comments' | 'versions'

export default function NegotiationsPageWrapper() {
  return (
    <Suspense fallback={null}>
      <NegotiationsPage />
    </Suspense>
  )
}

function NegotiationsPage() {
  const { isReady } = useAuthGuard()
  const searchParams = useSearchParams()
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('negotiate')
  const [negotiationId, setNegotiationId] = useState<string | null>(null)
  const [comparison, setComparison] = useState<VersionCompareResult | null>(null)
  const [fromVersion, setFromVersion] = useState<string>('')
  const [toVersion, setToVersion] = useState<string>('')

  const { data: negotiation } = useNegotiation(negotiationId)
  const { data: versions = [] } = useVersionHistory(documentId)
  const compareVersions = useCompareVersions()

  useEffect(() => {
    const doc = searchParams.get('doc')
    if (doc) setDocumentId(doc)
  }, [searchParams])

  const handleCompare = async () => {
    if (!documentId || !fromVersion || !toVersion) return
    const result = await compareVersions.mutateAsync({
      document_id: documentId,
      from_version_id: fromVersion,
      to_version_id: toVersion,
    })
    setComparison(result)
  }

  if (!isReady) return null

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    {
      key: 'negotiate',
      label: 'Переговоры',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
        </svg>
      ),
    },
    {
      key: 'comments',
      label: 'Комментарии',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
        </svg>
      ),
    },
    {
      key: 'versions',
      label: 'Версии',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ]

  return (
    <AppLayout title="Переговоры">
      <div className="max-w-5xl mx-auto">
        {/* Document selector */}
        {!documentId && (
          <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-8 text-center">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2">Переговоры по договору</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Перейдите на страницу договора и нажмите &laquo;Переговоры&raquo; для запуска
            </p>
          </div>
        )}

        {documentId && (
          <>
            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-dark-800 rounded-xl p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    activeTab === tab.key
                      ? 'bg-white dark:bg-dark-700 text-gray-800 dark:text-gray-200 shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === 'negotiate' && (
              <NegotiationWizard
                documentId={documentId}
                onComplete={setNegotiationId}
              />
            )}

            {activeTab === 'comments' && (
              <CommentThread documentId={documentId} />
            )}

            {activeTab === 'versions' && (
              <div className="space-y-4">
                <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-6">
                  <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 mb-4">
                    Сравнение версий
                  </h3>

                  {/* Version history */}
                  {versions.length > 0 ? (
                    <>
                      <div className="mb-4 space-y-2">
                        {versions.map((v: VersionHistoryItem) => (
                          <div
                            key={v.id}
                            className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 dark:bg-dark-900"
                          >
                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                              v.is_current ? 'bg-green-500 text-white' : 'bg-gray-300 dark:bg-dark-600 text-gray-600 dark:text-gray-400'
                            }`}>
                              {v.version_number}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                                {v.description || `Версия ${v.version_number}`}
                                {v.is_current && <span className="ml-2 text-green-600 dark:text-green-400">(текущая)</span>}
                              </p>
                              <p className="text-[10px] text-gray-400">
                                {v.source} {v.uploaded_at ? `| ${new Date(v.uploaded_at).toLocaleDateString('ru-RU')}` : ''}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Compare selector */}
                      <div className="flex items-end gap-3">
                        <div className="flex-1">
                          <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">От версии</label>
                          <select
                            value={fromVersion}
                            onChange={(e) => setFromVersion(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200"
                          >
                            <option value="">Выберите...</option>
                            {versions.map((v: VersionHistoryItem) => (
                              <option key={v.id} value={v.id}>{v.version_number}: {v.description || v.source}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex-1">
                          <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">До версии</label>
                          <select
                            value={toVersion}
                            onChange={(e) => setToVersion(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200"
                          >
                            <option value="">Выберите...</option>
                            {versions.map((v: VersionHistoryItem) => (
                              <option key={v.id} value={v.id}>{v.version_number}: {v.description || v.source}</option>
                            ))}
                          </select>
                        </div>
                        <button
                          onClick={handleCompare}
                          disabled={!fromVersion || !toVersion || compareVersions.isPending}
                          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                        >
                          {compareVersions.isPending ? 'Анализ...' : 'Сравнить'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-6">
                      Нет загруженных версий
                    </p>
                  )}
                </div>

                {/* Comparison result */}
                {comparison && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-6"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200">
                        Результат сравнения
                      </h3>
                      <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
                        {comparison.total_changes} изменений
                      </span>
                    </div>

                    <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
                      {comparison.executive_summary}
                    </p>

                    <div className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-dark-900 rounded-lg p-3">
                      <p className="font-medium mb-1">Оценка: {comparison.overall_assessment}</p>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {Object.entries(comparison.by_category).map(([cat, count]) => (
                          <span key={cat} className="px-2 py-0.5 rounded bg-gray-200 dark:bg-dark-700">
                            {cat}: {count}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Material changes */}
                    {comparison.material_changes.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300">
                          Существенные изменения ({comparison.material_changes.length})
                        </h4>
                        {comparison.material_changes.map((change) => (
                          <div
                            key={change.change_id}
                            className={`p-3 rounded-lg border ${
                              change.requires_review
                                ? 'border-red-200 dark:border-red-900/30 bg-red-50/50 dark:bg-red-900/10'
                                : 'border-gray-200 dark:border-dark-700'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                change.severity === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                                change.severity === 'high' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' :
                                'bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400'
                              }`}>
                                {change.change_type}
                              </span>
                              {change.section_name && (
                                <span className="text-[10px] text-gray-400">{change.section_name}</span>
                              )}
                              {change.requires_review && (
                                <span className="text-[10px] text-red-500 font-medium">Требует ревью</span>
                              )}
                            </div>
                            {change.semantic_description && (
                              <p className="text-xs text-gray-700 dark:text-gray-300">{change.semantic_description}</p>
                            )}
                            {change.recommendation && (
                              <p className="text-[10px] text-primary-600 dark:text-primary-400 mt-1">{change.recommendation}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  )
}
