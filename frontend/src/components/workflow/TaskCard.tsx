'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { WorkflowTask } from '@/services/api'
import { useCompleteWorkflowTask, useEscalateWorkflowTask } from '@/hooks/useWorkflow'

interface TaskCardProps {
  task: WorkflowTask
}

export default function TaskCard({ task }: TaskCardProps) {
  const [comment, setComment] = useState('')
  const [showActions, setShowActions] = useState(false)
  const completeTask = useCompleteWorkflowTask()
  const escalateTask = useEscalateWorkflowTask()

  const isPending = task.status === 'pending' || task.status === 'in_progress'
  const isOverdue = task.sla_deadline && new Date(task.sla_deadline) < new Date() && isPending

  const handleDecision = (decision: string) => {
    completeTask.mutate({
      taskId: task.id,
      decision,
      comment: comment.trim() || undefined,
    })
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-white dark:bg-dark-800 rounded-xl border p-4 ${
        isOverdue ? 'border-red-300 dark:border-red-800' :
        isPending ? 'border-gray-200 dark:border-dark-700' :
        'border-gray-100 dark:border-dark-800 opacity-70'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-bold text-gray-800 dark:text-gray-200">
              {task.step_name}
            </span>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
              task.status === 'pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
              task.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
              task.status === 'escalated' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' :
              'bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400'
            }`}>
              {task.status === 'pending' ? 'Ожидает' :
               task.status === 'in_progress' ? 'В работе' :
               task.status === 'completed' ? 'Готово' :
               task.status === 'escalated' ? 'Эскалировано' : 'Пропущено'}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span>Тип: {task.task_type}</span>
            {task.sla_deadline && (
              <span className={isOverdue ? 'text-red-500 font-medium' : ''}>
                SLA: {new Date(task.sla_deadline).toLocaleString('ru-RU')}
                {isOverdue && ' (просрочено!)'}
              </span>
            )}
          </div>

          {task.decision && (
            <p className={`text-xs font-medium mt-2 ${
              task.decision === 'approve' ? 'text-green-600' :
              task.decision === 'reject' ? 'text-red-600' : 'text-amber-600'
            }`}>
              {task.decision === 'approve' ? 'Согласовано' :
               task.decision === 'reject' ? 'Отклонено' : 'На доработку'}
            </p>
          )}
          {task.comment && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">&laquo;{task.comment}&raquo;</p>
          )}
        </div>

        {isPending && (
          <button
            onClick={() => setShowActions(!showActions)}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-lg transition-colors text-gray-500"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
            </svg>
          </button>
        )}
      </div>

      {/* Action area */}
      {showActions && isPending && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-3 pt-3 border-t border-gray-100 dark:border-dark-700"
        >
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Комментарий (необязательно)..."
            rows={2}
            className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none mb-3"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleDecision('approve')}
              disabled={completeTask.isPending}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
            >
              Согласовать
            </button>
            <button
              onClick={() => handleDecision('return_for_revision')}
              disabled={completeTask.isPending}
              className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
            >
              На доработку
            </button>
            <button
              onClick={() => handleDecision('reject')}
              disabled={completeTask.isPending}
              className="px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
            >
              Отклонить
            </button>
            <button
              onClick={() => escalateTask.mutate({ taskId: task.id })}
              disabled={escalateTask.isPending}
              className="ml-auto px-3 py-1.5 text-xs text-gray-500 hover:text-orange-600 dark:hover:text-orange-400 font-medium transition-colors"
            >
              Эскалировать
            </button>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
