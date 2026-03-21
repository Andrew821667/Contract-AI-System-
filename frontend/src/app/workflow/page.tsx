'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'
import TaskCard from '@/components/workflow/TaskCard'
import WorkflowTimeline from '@/components/workflow/WorkflowTimeline'
import {
  useMyWorkflowTasks,
  useWorkflowDefinitions,
  useDocumentWorkflows,
  useExecutionTasks,
  useStartWorkflow,
  useCreateWorkflowDefinition,
} from '@/hooks/useWorkflow'
import type { WorkflowExecution, WorkflowDefinition } from '@/services/api'

type Tab = 'tasks' | 'definitions' | 'viewer'

export default function WorkflowPage() {
  const { isReady } = useAuthGuard()
  const [activeTab, setActiveTab] = useState<Tab>('tasks')
  const [taskFilter, setTaskFilter] = useState('pending')
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null)
  const [showCreateDef, setShowCreateDef] = useState(false)

  // New definition form
  const [defName, setDefName] = useState('')
  const [defDesc, setDefDesc] = useState('')
  const [defDocType, setDefDocType] = useState('')
  const [defSteps, setDefSteps] = useState<Array<{ name: string; assignee_role: string; sla_hours: number }>>([
    { name: '', assignee_role: '', sla_hours: 24 },
  ])

  const { data: tasks = [], isLoading: tasksLoading } = useMyWorkflowTasks(taskFilter)
  const { data: definitions = [] } = useWorkflowDefinitions()
  const { data: executionTasks = [] } = useExecutionTasks(selectedExecution?.id || null)
  const createDef = useCreateWorkflowDefinition()
  const startWorkflow = useStartWorkflow()

  if (!isReady) return null

  const handleCreateDefinition = async () => {
    if (!defName.trim() || defSteps.every(s => !s.name.trim())) return
    await createDef.mutateAsync({
      name: defName.trim(),
      description: defDesc.trim() || undefined,
      document_type: defDocType.trim() || undefined,
      steps: defSteps.filter(s => s.name.trim()),
    })
    setShowCreateDef(false)
    setDefName('')
    setDefDesc('')
    setDefDocType('')
    setDefSteps([{ name: '', assignee_role: '', sla_hours: 24 }])
  }

  const addStep = () => {
    setDefSteps([...defSteps, { name: '', assignee_role: '', sla_hours: 24 }])
  }

  const removeStep = (idx: number) => {
    if (defSteps.length > 1) setDefSteps(defSteps.filter((_, i) => i !== idx))
  }

  const updateStep = (idx: number, field: string, value: string | number) => {
    setDefSteps(defSteps.map((s, i) => i === idx ? { ...s, [field]: value } : s))
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'tasks', label: 'Мои задачи' },
    { key: 'definitions', label: 'Маршруты' },
    { key: 'viewer', label: 'Просмотр' },
  ]

  const pendingCount = tasks.length
  const overdueTasks = tasks.filter(t => t.sla_deadline && new Date(t.sla_deadline) < new Date())

  return (
    <AppLayout title="Workflow">
      <div className="max-w-5xl mx-auto">
        {/* Header with stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
            <p className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase">На согласовании</p>
            <p className="text-2xl font-bold text-gray-800 dark:text-gray-200 mt-1">{pendingCount}</p>
          </div>
          <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
            <p className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase">Просрочено</p>
            <p className={`text-2xl font-bold mt-1 ${overdueTasks.length > 0 ? 'text-red-600' : 'text-gray-800 dark:text-gray-200'}`}>
              {overdueTasks.length}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
            <p className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase">Маршрутов</p>
            <p className="text-2xl font-bold text-gray-800 dark:text-gray-200 mt-1">{definitions.length}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-dark-800 rounded-xl p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-white dark:bg-dark-700 text-gray-800 dark:text-gray-200 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
              {tab.key === 'tasks' && pendingCount > 0 && (
                <span className="ml-1.5 text-[10px] bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300 px-1.5 py-0.5 rounded-full">
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tasks tab */}
        {activeTab === 'tasks' && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              {['pending', 'in_progress', 'completed'].map(s => (
                <button
                  key={s}
                  onClick={() => setTaskFilter(s)}
                  className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                    taskFilter === s
                      ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-700'
                  }`}
                >
                  {s === 'pending' ? 'Ожидающие' : s === 'in_progress' ? 'В работе' : 'Завершённые'}
                </button>
              ))}
            </div>

            {tasksLoading ? (
              <p className="text-sm text-gray-400 text-center py-8">Загрузка...</p>
            ) : tasks.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-dark-700 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Нет задач</p>
              </div>
            ) : (
              <div className="space-y-3">
                {tasks.map(task => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Definitions tab */}
        {activeTab === 'definitions' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">
                Маршруты согласования
              </h3>
              <button
                onClick={() => setShowCreateDef(!showCreateDef)}
                className="px-3 py-1.5 text-xs font-medium bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
              >
                {showCreateDef ? 'Отмена' : 'Создать маршрут'}
              </button>
            </div>

            {/* Create definition form */}
            <AnimatePresence>
              {showCreateDef && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5 mb-4 overflow-hidden"
                >
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Название</label>
                      <input
                        type="text"
                        value={defName}
                        onChange={(e) => setDefName(e.target.value)}
                        placeholder="Согласование договора поставки"
                        className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Тип документа</label>
                      <input
                        type="text"
                        value={defDocType}
                        onChange={(e) => setDefDocType(e.target.value)}
                        placeholder="supply, service, nda..."
                        className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                  <div className="mb-4">
                    <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Описание</label>
                    <input
                      type="text"
                      value={defDesc}
                      onChange={(e) => setDefDesc(e.target.value)}
                      placeholder="Описание маршрута..."
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>

                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 block">Шаги маршрута</label>
                  <div className="space-y-2 mb-4">
                    {defSteps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-400 w-5 text-right">{i + 1}</span>
                        <input
                          type="text"
                          value={step.name}
                          onChange={(e) => updateStep(i, 'name', e.target.value)}
                          placeholder="Название шага"
                          className="flex-1 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                        <input
                          type="text"
                          value={step.assignee_role}
                          onChange={(e) => updateStep(i, 'assignee_role', e.target.value)}
                          placeholder="Роль"
                          className="w-28 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                        <input
                          type="number"
                          value={step.sla_hours}
                          onChange={(e) => updateStep(i, 'sla_hours', parseInt(e.target.value) || 0)}
                          className="w-16 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                        <span className="text-[10px] text-gray-400">ч</span>
                        <button
                          onClick={() => removeStep(i)}
                          className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center justify-between">
                    <button onClick={addStep} className="text-xs text-primary-600 hover:text-primary-700 font-medium">
                      + Добавить шаг
                    </button>
                    <button
                      onClick={handleCreateDefinition}
                      disabled={!defName.trim() || createDef.isPending}
                      className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      {createDef.isPending ? 'Создание...' : 'Создать'}
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Definitions list */}
            <div className="space-y-3">
              {definitions.map((def: WorkflowDefinition) => (
                <div
                  key={def.id}
                  className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-gray-800 dark:text-gray-200">{def.name}</h4>
                    <div className="flex items-center gap-2">
                      {def.document_type && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">{def.document_type}</span>
                      )}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        def.active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {def.active ? 'Активен' : 'Неактивен'}
                      </span>
                    </div>
                  </div>
                  {def.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{def.description}</p>
                  )}
                  <div className="flex items-center gap-2">
                    {def.steps.map((step, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400">
                          {step.name}
                        </span>
                        {i < def.steps.length - 1 && (
                          <svg className="w-3 h-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {definitions.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-8">Нет маршрутов. Создайте первый.</p>
              )}
            </div>
          </div>
        )}

        {/* Viewer tab */}
        {activeTab === 'viewer' && (
          <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-6 text-center">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">Просмотр workflow</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Откройте страницу договора, чтобы увидеть его workflow-процесс с таймлайном
            </p>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
