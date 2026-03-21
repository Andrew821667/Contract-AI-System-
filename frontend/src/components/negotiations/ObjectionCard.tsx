'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Objection } from '@/services/api'

const priorityColors: Record<string, { bg: string; text: string }> = {
  critical: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-300' },
  high: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-300' },
  medium: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-300' },
  low: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300' },
}

interface ObjectionCardProps {
  objection: Objection
  selected: boolean
  onToggle: () => void
}

export default function ObjectionCard({ objection, selected, onToggle }: ObjectionCardProps) {
  const [expanded, setExpanded] = useState(false)
  const pc = priorityColors[objection.priority] || priorityColors.medium

  return (
    <motion.div
      layout
      className={`rounded-xl border-2 transition-colors ${
        selected
          ? 'border-primary-400 bg-white dark:bg-dark-800'
          : 'border-gray-200 dark:border-dark-700 bg-gray-50 dark:bg-dark-900 opacity-70'
      }`}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Checkbox */}
          <button
            onClick={onToggle}
            className={`mt-0.5 w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
              selected
                ? 'bg-primary-600 border-primary-600 text-white'
                : 'border-gray-300 dark:border-dark-600'
            }`}
          >
            {selected && (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </button>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${pc.bg} ${pc.text}`}>
                {objection.priority.toUpperCase()}
              </span>
              <div className="flex items-center gap-1">
                <div className="h-1 w-12 rounded-full bg-gray-200 dark:bg-dark-700 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary-500"
                    style={{ width: `${objection.confidence * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-gray-400">{Math.round(objection.confidence * 100)}%</span>
              </div>
            </div>
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
              {objection.issue_description}
            </p>

            {/* Expandable details */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-primary-600 dark:text-primary-400 hover:underline mt-2"
            >
              {expanded ? 'Скрыть детали' : 'Показать детали'}
            </button>

            {expanded && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-3"
              >
                <div>
                  <p className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase mb-1">Правовое основание</p>
                  <p className="text-xs text-gray-700 dark:text-gray-300">{objection.legal_basis}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase mb-1">Объяснение риска</p>
                  <p className="text-xs text-gray-700 dark:text-gray-300">{objection.risk_explanation}</p>
                </div>
                <div className="p-3 bg-green-50 dark:bg-green-900/10 rounded-lg">
                  <p className="text-[10px] font-bold text-green-700 dark:text-green-400 uppercase mb-1">Альтернативная формулировка</p>
                  <p className="text-xs text-green-800 dark:text-green-300">{objection.alternative_formulation}</p>
                  <p className="text-[10px] text-green-600 dark:text-green-400 mt-1 italic">{objection.alternative_reasoning}</p>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}
