'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import api, { CompanyCondition, CompanyConditionCreate, CompanyConditionUpdate, ConditionCategory } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import AppLayout from '@/components/AppLayout'

const PRIORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'Низкий', color: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' },
  2: { label: 'Средний', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  3: { label: 'Высокий', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
}

function getCategoryLabel(categories: ConditionCategory[], value: string): string {
  return categories.find(c => c.value === value)?.label || value
}

export default function ConditionsPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [filterCategory, setFilterCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingCondition, setEditingCondition] = useState<CompanyCondition | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState<CompanyConditionCreate>({
    category: 'other',
    title: '',
    description: '',
    condition_text: '',
    priority: 2,
    is_active: true,
  })

  useEffect(() => {
    const token = useAuthStore.getState().accessToken
    if (!token) router.push('/login')
  }, [router])

  // Fetch categories
  const { data: categories = [] } = useQuery<ConditionCategory[]>({
    queryKey: ['conditionCategories'],
    queryFn: () => api.getConditionCategories(),
    staleTime: 300000,
  })

  // Fetch conditions
  const { data: conditionsData, isLoading } = useQuery({
    queryKey: ['conditions', filterCategory],
    queryFn: () => api.getConditions({
      page_size: 100,
      category: filterCategory || undefined,
    }),
    staleTime: 30000,
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CompanyConditionCreate) => api.createCondition(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions'] })
      resetForm()
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CompanyConditionUpdate }) =>
      api.updateCondition(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions'] })
      resetForm()
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteCondition(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions'] })
      setDeleteConfirm(null)
    },
  })

  const resetForm = useCallback(() => {
    setShowForm(false)
    setEditingCondition(null)
    setFormData({
      category: 'other',
      title: '',
      description: '',
      condition_text: '',
      priority: 2,
      is_active: true,
    })
  }, [])

  const handleEdit = (condition: CompanyCondition) => {
    setEditingCondition(condition)
    setFormData({
      category: condition.category,
      title: condition.title,
      description: condition.description || '',
      condition_text: condition.condition_text,
      priority: condition.priority,
      is_active: condition.is_active,
    })
    setShowForm(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingCondition) {
      updateMutation.mutate({ id: editingCondition.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const conditions = conditionsData?.conditions || []
  const activeCount = conditions.filter(c => c.is_active).length
  const totalCount = conditionsData?.total || 0

  // Group by category
  const grouped: Record<string, CompanyCondition[]> = {}
  conditions.forEach(c => {
    if (!grouped[c.category]) grouped[c.category] = []
    grouped[c.category].push(c)
  })

  return (
    <AppLayout title="Условия компании">
      <div>
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
          <div>
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
              Стандартные условия вашей компании. При анализе договора система сравнивает пункты с этими стандартами.
            </p>
            <div className="flex gap-4 mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Всего: <strong className="text-stone-800 dark:text-gray-100">{totalCount}</strong>
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Активных: <strong className="text-green-600">{activeCount}</strong>
              </span>
            </div>
          </div>
          <button
            onClick={() => { resetForm(); setShowForm(true) }}
            className="px-5 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition flex items-center gap-2 shadow-sm"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Добавить условие
          </button>
        </div>

        {/* Category filter */}
        <div className="flex gap-2 mb-6 flex-wrap">
          <button
            onClick={() => setFilterCategory('')}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
              !filterCategory
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-dark-700 dark:text-gray-300 dark:hover:bg-dark-600'
            }`}
          >
            Все
          </button>
          {categories.map(cat => (
            <button
              key={cat.value}
              onClick={() => setFilterCategory(cat.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
                filterCategory === cat.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-dark-700 dark:text-gray-300 dark:hover:bg-dark-600'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Conditions List */}
        {isLoading ? (
          <div className="flex justify-center py-16">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full"
            />
          </div>
        ) : conditions.length === 0 ? (
          <div className="text-center py-16 bg-white dark:bg-dark-800 rounded-2xl shadow-sm border border-gray-100 dark:border-dark-700">
            <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 dark:bg-dark-700 rounded-2xl flex items-center justify-center">
              <svg className="h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-2">Нет условий</h3>
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              Добавьте стандартные условия вашей компании для улучшения анализа договоров
            </p>
            <button
              onClick={() => { resetForm(); setShowForm(true) }}
              className="px-5 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition"
            >
              Добавить первое условие
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 px-1">
                  {getCategoryLabel(categories, category)} ({items.length})
                </h3>
                <div className="space-y-3">
                  {items.map((condition, idx) => (
                    <motion.div
                      key={condition.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      className={`bg-white dark:bg-dark-800 rounded-2xl p-5 shadow-sm border transition-all ${
                        condition.is_active
                          ? 'border-gray-100 dark:border-dark-700'
                          : 'border-gray-100 dark:border-dark-700 opacity-60'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-semibold text-stone-800 dark:text-gray-100 truncate">
                              {condition.title}
                            </h4>
                            <span className={`px-2 py-0.5 rounded-lg text-xs font-medium ${PRIORITY_LABELS[condition.priority]?.color || ''}`}>
                              {PRIORITY_LABELS[condition.priority]?.label || ''}
                            </span>
                            {!condition.is_active && (
                              <span className="px-2 py-0.5 rounded-lg text-xs font-medium bg-gray-200 text-gray-500 dark:bg-gray-600 dark:text-gray-400">
                                Неактивно
                              </span>
                            )}
                          </div>
                          {condition.description && (
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">{condition.description}</p>
                          )}
                          <div className="p-3 bg-gray-50 dark:bg-dark-700 rounded-xl text-sm text-stone-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
                            {condition.condition_text}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex flex-col gap-2 shrink-0">
                          <button
                            onClick={() => handleEdit(condition)}
                            className="p-2 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-xl transition"
                            title="Редактировать"
                          >
                            <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(condition.id)}
                            className="p-2 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition"
                            title="Удалить"
                          >
                            <svg className="w-4 h-4 text-gray-500 hover:text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create/Edit Form Modal */}
        <AnimatePresence>
          {showForm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
              onClick={() => resetForm()}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto"
              >
                <div className="p-6 border-b border-gray-100 dark:border-dark-700 flex justify-between items-center">
                  <h2 className="text-xl font-bold text-stone-800 dark:text-gray-100">
                    {editingCondition ? 'Редактировать условие' : 'Новое условие'}
                  </h2>
                  <button onClick={() => resetForm()} className="p-2 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-xl transition">
                    <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                  {/* Title */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Название условия *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.title}
                      onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                      placeholder="Например: Срок оплаты не более 30 дней"
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 dark:bg-dark-700 dark:text-gray-100 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none transition"
                    />
                  </div>

                  {/* Category + Priority row */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                        Категория
                      </label>
                      <select
                        value={formData.category}
                        onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 dark:bg-dark-700 dark:text-gray-100 focus:border-primary-400 outline-none bg-white transition"
                      >
                        {categories.map(cat => (
                          <option key={cat.value} value={cat.value}>{cat.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                        Приоритет
                      </label>
                      <select
                        value={formData.priority}
                        onChange={(e) => setFormData(prev => ({ ...prev, priority: Number(e.target.value) }))}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 dark:bg-dark-700 dark:text-gray-100 focus:border-primary-400 outline-none bg-white transition"
                      >
                        <option value={1}>Низкий</option>
                        <option value={2}>Средний</option>
                        <option value={3}>Высокий</option>
                      </select>
                    </div>
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Описание (необязательно)
                    </label>
                    <input
                      type="text"
                      value={formData.description || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Краткое пояснение, зачем нужно это условие"
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 dark:bg-dark-700 dark:text-gray-100 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none transition"
                    />
                  </div>

                  {/* Condition text */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Текст условия *
                    </label>
                    <textarea
                      required
                      rows={5}
                      value={formData.condition_text}
                      onChange={(e) => setFormData(prev => ({ ...prev, condition_text: e.target.value }))}
                      placeholder="Опишите стандартное условие, которому должны соответствовать договоры. Например: «Оплата производится в течение 30 календарных дней с даты подписания акта выполненных работ. Авансовые платежи не допускаются.»"
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 dark:bg-dark-700 dark:text-gray-100 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none transition resize-none"
                    />
                  </div>

                  {/* Active toggle */}
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, is_active: !prev.is_active }))}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        formData.is_active ? 'bg-primary-600' : 'bg-gray-300 dark:bg-dark-600'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          formData.is_active ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {formData.is_active ? 'Активно — учитывается при анализе' : 'Неактивно — не учитывается'}
                    </span>
                  </div>

                  {/* Submit */}
                  <div className="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => resetForm()}
                      className="px-5 py-2.5 rounded-xl border border-gray-200 dark:border-dark-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-700 font-medium transition"
                    >
                      Отмена
                    </button>
                    <button
                      type="submit"
                      disabled={createMutation.isPending || updateMutation.isPending}
                      className="px-5 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition disabled:opacity-50"
                    >
                      {createMutation.isPending || updateMutation.isPending
                        ? 'Сохранение...'
                        : editingCondition ? 'Сохранить' : 'Создать'
                      }
                    </button>
                  </div>
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Delete Confirmation Modal */}
        <AnimatePresence>
          {deleteConfirm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
              onClick={() => setDeleteConfirm(null)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-md w-full p-6"
              >
                <h3 className="text-lg font-bold text-stone-800 dark:text-gray-100 mb-2">Удалить условие?</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  Это действие нельзя отменить. Условие будет удалено навсегда.
                </p>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={() => setDeleteConfirm(null)}
                    className="px-4 py-2 rounded-xl border border-gray-200 dark:border-dark-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-700 font-medium transition"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={() => deleteConfirm && deleteMutation.mutate(deleteConfirm)}
                    disabled={deleteMutation.isPending}
                    className="px-4 py-2 bg-red-600 text-white rounded-xl font-medium hover:bg-red-700 transition disabled:opacity-50"
                  >
                    {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}
