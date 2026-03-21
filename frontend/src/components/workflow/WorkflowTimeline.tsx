'use client'

import { motion } from 'framer-motion'
import type { WorkflowTask, WorkflowExecution, WorkflowDefinition } from '@/services/api'

const statusConfig: Record<string, { color: string; bg: string; label: string }> = {
  pending:     { color: 'text-gray-500',   bg: 'bg-gray-200 dark:bg-dark-600',    label: 'Ожидает' },
  in_progress: { color: 'text-blue-500',   bg: 'bg-blue-500',                     label: 'В работе' },
  completed:   { color: 'text-green-500',  bg: 'bg-green-500',                    label: 'Готово' },
  escalated:   { color: 'text-orange-500', bg: 'bg-orange-500',                   label: 'Эскалировано' },
  skipped:     { color: 'text-gray-400',   bg: 'bg-gray-300 dark:bg-dark-600',    label: 'Пропущено' },
}

const decisionLabels: Record<string, { label: string; color: string }> = {
  approve:              { label: 'Согласовано',            color: 'text-green-600 dark:text-green-400' },
  reject:               { label: 'Отклонено',             color: 'text-red-600 dark:text-red-400' },
  return_for_revision:  { label: 'На доработку',          color: 'text-amber-600 dark:text-amber-400' },
}

interface WorkflowTimelineProps {
  execution: WorkflowExecution
  tasks: WorkflowTask[]
  definition?: WorkflowDefinition | null
}

export default function WorkflowTimeline({ execution, tasks, definition }: WorkflowTimelineProps) {
  const steps = definition?.steps || []
  const totalSteps = Math.max(steps.length, tasks.length)

  return (
    <div className="relative">
      {/* Execution header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            execution.status === 'active' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
            execution.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
            execution.status === 'cancelled' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
            'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
          }`}>
            {execution.status === 'active' ? 'Активен' :
             execution.status === 'completed' ? 'Завершён' :
             execution.status === 'cancelled' ? 'Отменён' : 'Ошибка'}
          </span>
          {definition && (
            <span className="text-xs text-gray-500 dark:text-gray-400">{definition.name}</span>
          )}
        </div>
        <span className="text-[10px] text-gray-400">
          Шаг {execution.current_step + 1} из {totalSteps}
        </span>
      </div>

      {/* Timeline */}
      <div className="space-y-0">
        {Array.from({ length: totalSteps }, (_, i) => {
          const task = tasks.find(t => t.step_order === i)
          const stepDef = steps[i]
          const isCurrent = i === execution.current_step && execution.status === 'active'
          const sc = task ? statusConfig[task.status] || statusConfig.pending : statusConfig.pending
          const dc = task?.decision ? decisionLabels[task.decision] : null

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex gap-3"
            >
              {/* Line + dot */}
              <div className="flex flex-col items-center w-6 flex-shrink-0">
                <div className={`w-3 h-3 rounded-full border-2 flex-shrink-0 ${
                  isCurrent ? 'border-primary-500 bg-primary-500 ring-4 ring-primary-100 dark:ring-primary-900/30' :
                  task?.status === 'completed' ? 'border-green-500 bg-green-500' :
                  task?.status === 'escalated' ? 'border-orange-500 bg-orange-500' :
                  'border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-800'
                }`} />
                {i < totalSteps - 1 && (
                  <div className={`w-0.5 flex-1 min-h-[2rem] ${
                    task?.status === 'completed' ? 'bg-green-300 dark:bg-green-700' : 'bg-gray-200 dark:bg-dark-700'
                  }`} />
                )}
              </div>

              {/* Content */}
              <div className={`flex-1 pb-4 ${isCurrent ? '-mt-1' : ''}`}>
                <div className={`p-3 rounded-lg ${
                  isCurrent ? 'bg-primary-50 dark:bg-primary-900/10 border border-primary-200 dark:border-primary-800' :
                  'bg-gray-50 dark:bg-dark-900'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <p className={`text-sm font-medium ${
                      isCurrent ? 'text-primary-700 dark:text-primary-300' : 'text-gray-700 dark:text-gray-300'
                    }`}>
                      {stepDef?.name || task?.step_name || `Шаг ${i + 1}`}
                    </p>
                    <span className={`text-[10px] font-medium ${sc.color}`}>{sc.label}</span>
                  </div>

                  <div className="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500">
                    {stepDef?.assignee_role && <span>Роль: {stepDef.assignee_role}</span>}
                    {task?.task_type && <span>Тип: {task.task_type}</span>}
                    {task?.sla_deadline && (
                      <span className={task.sla_breached ? 'text-red-500 font-medium' : ''}>
                        SLA: {new Date(task.sla_deadline).toLocaleString('ru-RU')}
                        {task.sla_breached && ' (просрочено!)'}
                      </span>
                    )}
                  </div>

                  {dc && (
                    <p className={`text-xs font-medium mt-1 ${dc.color}`}>
                      {dc.label}
                    </p>
                  )}
                  {task?.comment && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">
                      &laquo;{task.comment}&raquo;
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
