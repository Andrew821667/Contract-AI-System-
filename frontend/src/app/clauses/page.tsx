'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import api, { ExtractedClause, ClauseStats } from '@/services/api'

const CLAUSE_TYPES = [
  { value: '', label: 'Все типы' },
  { value: 'financial', label: 'Финансовые' },
  { value: 'temporal', label: 'Временные' },
  { value: 'liability', label: 'Ответственность' },
  { value: 'termination', label: 'Расторжение' },
  { value: 'confidentiality', label: 'Конфиденциальность' },
  { value: 'dispute_resolution', label: 'Разрешение споров' },
  { value: 'force_majeure', label: 'Форс-мажор' },
  { value: 'warranties', label: 'Гарантии' },
  { value: 'intellectual_property', label: 'Интел. собственность' },
  { value: 'definitions', label: 'Определения' },
  { value: 'general', label: 'Общие' },
]

const RISK_LEVELS = [
  { value: '', label: 'Все уровни' },
  { value: 'critical', label: 'Критический', color: 'bg-red-100 text-red-800' },
  { value: 'high', label: 'Высокий', color: 'bg-orange-100 text-orange-800' },
  { value: 'medium', label: 'Средний', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'low', label: 'Низкий', color: 'bg-green-100 text-green-800' },
  { value: 'none', label: 'Нет', color: 'bg-gray-100 text-gray-600' },
]

function getRiskBadge(level: string | null) {
  const found = RISK_LEVELS.find(r => r.value === level)
  if (!found || !found.value) return { label: 'Нет', color: 'bg-gray-100 text-gray-600' }
  return found
}

function getTypeLabel(type: string) {
  const found = CLAUSE_TYPES.find(t => t.value === type)
  return found ? found.label : type
}

export default function ClauseLibraryPage() {
  const router = useRouter()
  const [page, setPage] = useState(1)
  const [clauseType, setClauseType] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedClause, setSelectedClause] = useState<ExtractedClause | null>(null)

  // Check auth
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) router.push('/login')
  }, [router])

  // Fetch stats
  const { data: stats } = useQuery<ClauseStats>({
    queryKey: ['clauseStats'],
    queryFn: () => api.getClauseStats(),
    staleTime: 60000,
  })

  // Fetch clauses (list or search)
  const { data: clausesData, isLoading } = useQuery({
    queryKey: ['clauses', page, clauseType, riskLevel, searchQuery],
    queryFn: () => {
      if (searchQuery) {
        return api.searchClauses(searchQuery, clauseType || undefined)
      }
      return api.getClauseLibrary({
        page,
        page_size: 20,
        clause_type: clauseType || undefined,
        risk_level: riskLevel || undefined,
      })
    },
    staleTime: 30000,
  })

  // Fetch clause detail
  const { data: clauseDetail } = useQuery({
    queryKey: ['clauseDetail', selectedClause?.id],
    queryFn: () => selectedClause ? api.getClause(selectedClause.id) : null,
    enabled: !!selectedClause,
  })

  const handleSearch = useCallback(() => {
    setPage(1)
    setSearchQuery(searchInput)
  }, [searchInput])

  const handleClearSearch = () => {
    setSearchInput('')
    setSearchQuery('')
    setPage(1)
  }

  const totalClauses = stats?.total_clauses || 0
  const byType = stats?.by_type || {}

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="p-2 hover:bg-gray-100 rounded-xl transition"
              >
                <svg className="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div>
                <h1 className="text-2xl font-bold text-stone-800">Библиотека клаузул</h1>
                <p className="text-sm text-gray-500">{totalClauses} клаузул в библиотеке</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 mb-1">Всего клаузул</p>
            <p className="text-3xl font-bold text-stone-800">{totalClauses}</p>
          </div>
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 mb-1">Договоров</p>
            <p className="text-3xl font-bold text-stone-800">{stats?.contracts_with_clauses || 0}</p>
          </div>
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 mb-1">Ср. серьёзность</p>
            <p className="text-3xl font-bold text-stone-800">{((stats?.average_severity || 0) * 100).toFixed(0)}%</p>
          </div>
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 mb-1">Типов</p>
            <p className="text-3xl font-bold text-stone-800">{Object.keys(byType).length}</p>
          </div>
        </div>

        {/* Filters & Search */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 flex gap-2">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Поиск по тексту клаузул..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none transition"
              />
              <button
                onClick={handleSearch}
                className="px-4 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition"
              >
                Поиск
              </button>
              {searchQuery && (
                <button
                  onClick={handleClearSearch}
                  className="px-3 py-2.5 text-gray-500 hover:text-gray-700 rounded-xl hover:bg-gray-100 transition"
                >
                  Сброс
                </button>
              )}
            </div>

            {/* Type filter */}
            <select
              value={clauseType}
              onChange={(e) => { setClauseType(e.target.value); setPage(1) }}
              className="px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 outline-none bg-white"
            >
              {CLAUSE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>

            {/* Risk level filter */}
            <select
              value={riskLevel}
              onChange={(e) => { setRiskLevel(e.target.value); setPage(1) }}
              className="px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 outline-none bg-white"
            >
              {RISK_LEVELS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Clauses Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex justify-center py-16">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full"
              />
            </div>
          ) : clausesData && clausesData.clauses.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">#</th>
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">Тип</th>
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">Заголовок</th>
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">Текст</th>
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">Риск</th>
                      <th className="text-left px-6 py-3.5 text-sm font-semibold text-gray-600">Теги</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clausesData.clauses.map((clause: ExtractedClause, idx: number) => {
                      const risk = getRiskBadge(clause.risk_level)
                      return (
                        <motion.tr
                          key={clause.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: idx * 0.02 }}
                          onClick={() => setSelectedClause(clause)}
                          className="border-b border-gray-50 hover:bg-primary-50/50 cursor-pointer transition-colors"
                        >
                          <td className="px-6 py-4 text-sm text-gray-500">{clause.clause_number}</td>
                          <td className="px-6 py-4">
                            <span className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                              {getTypeLabel(clause.clause_type)}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm font-medium text-stone-800 max-w-[200px] truncate">
                            {clause.title}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-600 max-w-[300px] truncate">
                            {clause.text}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2.5 py-1 rounded-lg text-xs font-medium ${risk.color}`}>
                              {risk.label}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex gap-1 flex-wrap max-w-[150px]">
                              {(clause.tags || []).slice(0, 2).map((tag, i) => (
                                <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {clausesData.total_pages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    Показано {(page - 1) * 20 + 1}–{Math.min(page * 20, clausesData.total)} из {clausesData.total}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm disabled:opacity-50 hover:bg-gray-50 transition"
                    >
                      Назад
                    </button>
                    <span className="px-3 py-1.5 text-sm text-gray-600">
                      {page} / {clausesData.total_pages}
                    </span>
                    <button
                      onClick={() => setPage(p => Math.min(clausesData.total_pages, p + 1))}
                      disabled={page >= clausesData.total_pages}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm disabled:opacity-50 hover:bg-gray-50 transition"
                    >
                      Далее
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-16">
              <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 rounded-2xl flex items-center justify-center">
                <svg className="h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">Нет клаузул</h3>
              <p className="text-gray-500">
                {searchQuery ? 'Попробуйте изменить поисковый запрос' : 'Клаузулы появятся после анализа договоров'}
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Clause Detail Modal */}
      <AnimatePresence>
        {selectedClause && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedClause(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto"
            >
              <div className="p-6 border-b border-gray-100 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-stone-800 mb-1">
                    Клаузула #{selectedClause.clause_number}
                  </h2>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                      {getTypeLabel(selectedClause.clause_type)}
                    </span>
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-medium ${getRiskBadge(selectedClause.risk_level).color}`}>
                      {getRiskBadge(selectedClause.risk_level).label}
                    </span>
                    {selectedClause.severity_score != null && (
                      <span className="text-xs text-gray-500">
                        Score: {(selectedClause.severity_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedClause(null)}
                  className="p-2 hover:bg-gray-100 rounded-xl transition"
                >
                  <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="p-6 space-y-6">
                {/* Title */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 mb-2">Заголовок</h3>
                  <p className="text-stone-800 font-medium">{selectedClause.title}</p>
                </div>

                {/* Text */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 mb-2">Текст клаузулы</h3>
                  <div className="p-4 bg-gray-50 rounded-xl text-sm text-stone-700 whitespace-pre-wrap leading-relaxed">
                    {selectedClause.text}
                  </div>
                </div>

                {/* Tags */}
                {selectedClause.tags && selectedClause.tags.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 mb-2">Теги</h3>
                    <div className="flex gap-2 flex-wrap">
                      {selectedClause.tags.map((tag, i) => (
                        <span key={i} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Analysis from detail query */}
                {clauseDetail?.analysis && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 mb-2">Анализ LLM</h3>

                    {/* Risks */}
                    {clauseDetail.analysis.risks && clauseDetail.analysis.risks.length > 0 && (
                      <div className="mb-4">
                        <p className="text-sm font-medium text-stone-700 mb-2">Риски:</p>
                        <div className="space-y-2">
                          {clauseDetail.analysis.risks.map((risk: any, i: number) => (
                            <div key={i} className="p-3 bg-red-50 rounded-xl border-l-4 border-l-red-400">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-red-800 text-sm">{risk.title || risk.risk_type}</span>
                                <span className="text-xs text-red-600">{risk.severity}</span>
                              </div>
                              <p className="text-sm text-red-700">{risk.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {clauseDetail.analysis.recommendations && clauseDetail.analysis.recommendations.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-stone-700 mb-2">Рекомендации:</p>
                        <div className="space-y-2">
                          {clauseDetail.analysis.recommendations.map((rec: any, i: number) => (
                            <div key={i} className="p-3 bg-blue-50 rounded-xl border-l-4 border-l-blue-400">
                              <p className="font-medium text-blue-800 text-sm mb-1">{rec.title}</p>
                              <p className="text-sm text-blue-700">{rec.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Scores */}
                    {clauseDetail.analysis.clarity_score != null && (
                      <div className="mt-4 flex gap-4">
                        <div className="px-4 py-2 bg-gray-50 rounded-xl">
                          <p className="text-xs text-gray-500">Ясность</p>
                          <p className="text-lg font-bold text-stone-800">{clauseDetail.analysis.clarity_score}/10</p>
                        </div>
                        {clauseDetail.analysis.legal_compliance?.score != null && (
                          <div className="px-4 py-2 bg-gray-50 rounded-xl">
                            <p className="text-xs text-gray-500">Соответствие</p>
                            <p className="text-lg font-bold text-stone-800">{clauseDetail.analysis.legal_compliance.score}/10</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
