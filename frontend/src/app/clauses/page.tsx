'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import api, { ExtractedClause, ClauseStats } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import AppLayout from '@/components/AppLayout'

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
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [clauseType, setClauseType] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedClause, setSelectedClause] = useState<ExtractedClause | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editText, setEditText] = useState('')
  const [editType, setEditType] = useState('')
  const [editRiskLevel, setEditRiskLevel] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createTitle, setCreateTitle] = useState('')
  const [createText, setCreateText] = useState('')
  const [createType, setCreateType] = useState('general')
  const [createRiskLevel, setCreateRiskLevel] = useState('none')

  useEffect(() => {
    const token = useAuthStore.getState().accessToken
    if (!token) router.push('/login')
  }, [router])

  const { data: stats } = useQuery<ClauseStats>({
    queryKey: ['clauseStats'],
    queryFn: () => api.getClauseStats(),
    staleTime: 60000,
  })

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

  const { data: clauseDetail } = useQuery({
    queryKey: ['clauseDetail', selectedClause?.id],
    queryFn: () => selectedClause ? api.getClause(selectedClause.id) : null,
    enabled: !!selectedClause,
  })

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; text?: string; clause_type?: string; risk_level?: string }) =>
      api.updateClause(selectedClause!.id, data),
    onSuccess: (updated) => {
      toast.success('Условие обновлено')
      setSelectedClause(updated)
      setIsEditing(false)
      queryClient.invalidateQueries({ queryKey: ['clauses'] })
      queryClient.invalidateQueries({ queryKey: ['clauseDetail', selectedClause?.id] })
      queryClient.invalidateQueries({ queryKey: ['clauseStats'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Ошибка обновления')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteClause(selectedClause!.id),
    onSuccess: () => {
      toast.success('Условие удалено')
      setSelectedClause(null)
      setShowDeleteConfirm(false)
      queryClient.invalidateQueries({ queryKey: ['clauses'] })
      queryClient.invalidateQueries({ queryKey: ['clauseStats'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Ошибка удаления')
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: { title: string; text: string; clause_type: string; risk_level: string }) =>
      api.createClause(data),
    onSuccess: () => {
      toast.success('Условие создано')
      setShowCreateModal(false)
      setCreateTitle('')
      setCreateText('')
      setCreateType('general')
      setCreateRiskLevel('none')
      queryClient.invalidateQueries({ queryKey: ['clauses'] })
      queryClient.invalidateQueries({ queryKey: ['clauseStats'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Ошибка создания')
    },
  })

  const handleCreate = () => {
    if (!createTitle.trim() || !createText.trim()) {
      toast.error('Заполните заголовок и текст')
      return
    }
    createMutation.mutate({
      title: createTitle,
      text: createText,
      clause_type: createType,
      risk_level: createRiskLevel,
    })
  }

  const handleSearch = useCallback(() => {
    setPage(1)
    setSearchQuery(searchInput)
  }, [searchInput])

  const handleClearSearch = () => {
    setSearchInput('')
    setSearchQuery('')
    setPage(1)
  }

  const startEditing = () => {
    if (!selectedClause) return
    setEditTitle(selectedClause.title)
    setEditText(selectedClause.text)
    setEditType(selectedClause.clause_type)
    setEditRiskLevel(selectedClause.risk_level || 'none')
    setIsEditing(true)
  }

  const handleSaveEdit = () => {
    const changes: Record<string, string> = {}
    if (editTitle !== selectedClause?.title) changes.title = editTitle
    if (editText !== selectedClause?.text) changes.text = editText
    if (editType !== selectedClause?.clause_type) changes.clause_type = editType
    if (editRiskLevel !== (selectedClause?.risk_level || 'none')) changes.risk_level = editRiskLevel

    if (Object.keys(changes).length === 0) {
      setIsEditing(false)
      return
    }
    updateMutation.mutate(changes)
  }

  const totalClauses = stats?.total_clauses || 0
  const byType = stats?.by_type || {}

  return (
    <AppLayout title="Условия договоров">
      <div>
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 mb-1">Всего условий</p>
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
            <div className="flex-1 flex gap-2">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Поиск по тексту условий..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none transition"
              />
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2.5 bg-green-600 text-white rounded-xl font-medium hover:bg-green-700 transition whitespace-nowrap"
              >
                + Создать
              </button>
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
            <select
              value={clauseType}
              onChange={(e) => { setClauseType(e.target.value); setPage(1) }}
              className="px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 outline-none bg-white"
            >
              {CLAUSE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
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
                          onClick={() => { setSelectedClause(clause); setIsEditing(false); setShowDeleteConfirm(false) }}
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
              <h3 className="text-lg font-bold text-gray-900 mb-2">Нет условий</h3>
              <p className="text-gray-500">
                {searchQuery ? 'Попробуйте изменить поисковый запрос' : 'Условия появятся после анализа договоров'}
              </p>
            </div>
          )}
        </div>

      {/* Clause Detail / Edit Modal */}
      <AnimatePresence>
        {selectedClause && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => { setSelectedClause(null); setIsEditing(false); setShowDeleteConfirm(false) }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto"
            >
              {/* Header */}
              <div className="p-6 border-b border-gray-100 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-stone-800 mb-1">
                    Условие #{selectedClause.clause_number}
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
                <div className="flex items-center gap-2">
                  {!isEditing && (
                    <>
                      <button
                        onClick={startEditing}
                        className="p-2 hover:bg-blue-50 rounded-xl transition text-blue-600"
                        title="Редактировать"
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="p-2 hover:bg-red-50 rounded-xl transition text-red-500"
                        title="Удалить"
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => { setSelectedClause(null); setIsEditing(false); setShowDeleteConfirm(false) }}
                    className="p-2 hover:bg-gray-100 rounded-xl transition"
                  >
                    <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Delete confirmation */}
              {showDeleteConfirm && (
                <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-xl">
                  <p className="text-sm text-red-800 mb-3">Удалить это условие? Действие необратимо.</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteMutation.isPending}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition disabled:opacity-50"
                    >
                      {deleteMutation.isPending ? 'Удаление...' : 'Да, удалить'}
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              )}

              <div className="p-6 space-y-6">
                {isEditing ? (
                  /* ---- Edit Mode ---- */
                  <>
                    <div>
                      <label className="text-sm font-semibold text-gray-500 mb-2 block">Заголовок</label>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-gray-500 mb-2 block">Текст условия</label>
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={6}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none resize-y"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-sm font-semibold text-gray-500 mb-2 block">Тип</label>
                        <select
                          value={editType}
                          onChange={(e) => setEditType(e.target.value)}
                          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none bg-white"
                        >
                          {CLAUSE_TYPES.filter(t => t.value).map(t => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-sm font-semibold text-gray-500 mb-2 block">Уровень риска</label>
                        <select
                          value={editRiskLevel}
                          onChange={(e) => setEditRiskLevel(e.target.value)}
                          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none bg-white"
                        >
                          {RISK_LEVELS.filter(r => r.value).map(r => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="flex gap-3 pt-2">
                      <button
                        onClick={handleSaveEdit}
                        disabled={updateMutation.isPending}
                        className="px-5 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition disabled:opacity-50"
                      >
                        {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button
                        onClick={() => setIsEditing(false)}
                        className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 transition"
                      >
                        Отмена
                      </button>
                    </div>
                  </>
                ) : (
                  /* ---- View Mode ---- */
                  <>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-500 mb-2">Заголовок</h3>
                      <p className="text-stone-800 font-medium">{selectedClause.title}</p>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-500 mb-2">Текст условия</h3>
                      <div className="p-4 bg-gray-50 rounded-xl text-sm text-stone-700 whitespace-pre-wrap leading-relaxed">
                        {selectedClause.text}
                      </div>
                    </div>
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
                    {clauseDetail?.analysis && (
                      <div>
                        <h3 className="text-sm font-semibold text-gray-500 mb-2">Анализ LLM</h3>
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
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowCreateModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto"
            >
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-xl font-bold text-stone-800">Новое условие</h2>
              </div>
              <div className="p-6 space-y-5">
                <div>
                  <label className="text-sm font-semibold text-gray-500 mb-2 block">Заголовок *</label>
                  <input
                    type="text"
                    value={createTitle}
                    onChange={(e) => setCreateTitle(e.target.value)}
                    placeholder="Название условия"
                    className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none"
                  />
                </div>
                <div>
                  <label className="text-sm font-semibold text-gray-500 mb-2 block">Текст условия *</label>
                  <textarea
                    value={createText}
                    onChange={(e) => setCreateText(e.target.value)}
                    rows={6}
                    placeholder="Текст условия договора..."
                    className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none resize-y"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-semibold text-gray-500 mb-2 block">Тип</label>
                    <select
                      value={createType}
                      onChange={(e) => setCreateType(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none bg-white"
                    >
                      {CLAUSE_TYPES.filter(t => t.value).map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-gray-500 mb-2 block">Уровень риска</label>
                    <select
                      value={createRiskLevel}
                      onChange={(e) => setCreateRiskLevel(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none bg-white"
                    >
                      {RISK_LEVELS.filter(r => r.value).map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleCreate}
                    disabled={createMutation.isPending}
                    className="px-5 py-2.5 bg-green-600 text-white rounded-xl font-medium hover:bg-green-700 transition disabled:opacity-50"
                  >
                    {createMutation.isPending ? 'Создание...' : 'Создать'}
                  </button>
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 transition"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </AppLayout>
  )
}
