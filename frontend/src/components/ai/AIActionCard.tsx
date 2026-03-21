'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { AIAction } from '@/services/api'

interface AIActionCardProps {
  action: AIAction
  onApprove: (actionId: string, comment?: string) => void
  onReject: (actionId: string, comment?: string) => void
  compact?: boolean
}

const statusColors: Record<string, string> = {
  pending: 'border-amber-300 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/20',
  approved: 'border-green-300 dark:border-green-600 bg-green-50 dark:bg-green-900/20',
  rejected: 'border-red-300 dark:border-red-600 bg-red-50 dark:bg-red-900/20',
  edited: 'border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/20',
}

const statusLabels: Record<string, string> = {
  pending: 'Ожидает',
  approved: 'Одобрено',
  rejected: 'Отклонено',
  edited: 'Изменено',
}

export default function AIActionCard({ action, onApprove, onReject, compact }: AIActionCardProps) {
  const [comment, setComment] = useState('')
  const [showComment, setShowComment] = useState(false)
  const isPending = action.status === 'pending'
  const confidencePercent = Math.round(action.confidence * 100)

  const confidenceColor =
    confidencePercent >= 80 ? 'bg-green-500' :
    confidencePercent >= 50 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`rounded-xl border ${statusColors[action.status] || statusColors.pending} ${compact ? 'p-3' : 'p-4'} mb-3`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              {action.action_type.replace(/_/g, ' ')}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              action.status === 'approved' ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' :
              action.status === 'rejected' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' :
              action.status === 'edited' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' :
              'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
            }`}>
              {statusLabels[action.status]}
            </span>
          </div>
          <p className={`${compact ? 'text-xs' : 'text-sm'} text-gray-700 dark:text-gray-300 mt-1`}>
            {action.description}
          </p>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] text-gray-500 dark:text-gray-400 w-20">Уверенность</span>
        <div className="flex-1 h-1.5 bg-gray-200 dark:bg-dark-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${confidenceColor}`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
        <span className="text-xs font-medium text-gray-600 dark:text-gray-400 w-8 text-right">
          {confidencePercent}%
        </span>
      </div>

      {/* Actions */}
      {isPending && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (showComment && comment.trim()) {
                onApprove(action.id, comment)
              } else {
                onApprove(action.id)
              }
            }}
            className="flex-1 text-xs font-medium py-1.5 px-3 rounded-lg bg-green-600 hover:bg-green-700 text-white transition-colors"
          >
            Одобрить
          </button>
          <button
            onClick={() => {
              if (showComment && comment.trim()) {
                onReject(action.id, comment)
              } else {
                onReject(action.id)
              }
            }}
            className="flex-1 text-xs font-medium py-1.5 px-3 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 dark:bg-red-900/30 dark:hover:bg-red-900/50 dark:text-red-300 transition-colors"
          >
            Отклонить
          </button>
          <button
            onClick={() => setShowComment(!showComment)}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 p-1.5"
            title="Добавить комментарий"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
          </button>
        </div>
      )}

      {/* Comment input */}
      {showComment && isPending && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="mt-2"
        >
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Комментарий (необязательно)..."
            className="w-full text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </motion.div>
      )}
    </motion.div>
  )
}
