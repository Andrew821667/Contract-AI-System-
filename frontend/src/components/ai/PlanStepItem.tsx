'use client'

import { motion } from 'framer-motion'
import type { OrchestratorStep } from '@/services/api'

const statusIcons: Record<string, { icon: React.ReactNode; color: string }> = {
  pending: {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <circle cx="12" cy="12" r="10" strokeWidth={2} />
      </svg>
    ),
    color: 'text-gray-400 dark:text-gray-500',
  },
  running: {
    icon: (
      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    ),
    color: 'text-primary-500',
  },
  completed: {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'text-green-500',
  },
  failed: {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'text-red-500',
  },
  skipped: {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
      </svg>
    ),
    color: 'text-gray-400',
  },
}

interface PlanStepItemProps {
  step: OrchestratorStep
  compact?: boolean
}

export default function PlanStepItem({ step, compact }: PlanStepItemProps) {
  const s = statusIcons[step.status] || statusIcons.pending

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: step.step_number * 0.05 }}
      className={`flex items-start gap-3 ${compact ? 'py-1.5' : 'py-2'} ${
        step.status === 'running' ? 'bg-primary-50/50 dark:bg-primary-900/10 -mx-2 px-2 rounded-lg' : ''
      }`}
    >
      {/* Step number + icon */}
      <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
        <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500 w-4 text-right">
          {step.step_number}
        </span>
        <span className={s.color}>{s.icon}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className={`${compact ? 'text-xs' : 'text-sm'} font-medium text-gray-700 dark:text-gray-300 truncate`}>
          {step.name}
        </p>
        {step.tool_name && (
          <span className="text-[10px] text-gray-400 dark:text-gray-500 font-mono">
            {step.tool_name}
          </span>
        )}
        {step.error && (
          <p className="text-[10px] text-red-500 mt-0.5 truncate">{step.error}</p>
        )}
        {step.output && !compact && (
          <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 truncate">
            {typeof step.output === 'string' ? step.output : JSON.stringify(step.output).slice(0, 100)}
          </p>
        )}
      </div>
    </motion.div>
  )
}
