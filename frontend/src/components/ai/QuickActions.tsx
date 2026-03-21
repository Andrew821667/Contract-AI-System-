'use client'

import { motion } from 'framer-motion'

interface QuickAction {
  label: string
  prompt: string
  icon: string
}

const defaultActions: QuickAction[] = [
  { label: 'Анализ рисков', prompt: 'Проанализируй все риски в этом договоре и оцени их критичность', icon: '⚡' },
  { label: 'Объясни риски', prompt: 'Объясни основные риски этого договора простым языком', icon: '🔍' },
  { label: 'Предложи клаузулу', prompt: 'Предложи дополнительные защитные клаузулы для этого договора', icon: '📝' },
  { label: 'Создай резюме', prompt: 'Создай краткое резюме ключевых условий этого договора', icon: '📋' },
  { label: 'Извлеки клаузулы', prompt: 'Извлеки и классифицируй все клаузулы из этого договора', icon: '📑' },
  { label: 'Найди в базе', prompt: 'Найди похожие клаузулы в базе знаний и сравни с текущим договором', icon: '🗃️' },
  { label: 'Сравни версии', prompt: 'Сравни текущую версию договора с предыдущей и покажи ключевые изменения', icon: '🔄' },
  { label: 'Сгенерируй', prompt: 'Сгенерируй улучшенную версию проблемных разделов этого договора', icon: '✨' },
]

interface QuickActionsProps {
  onSelect: (prompt: string) => void
  compact?: boolean
  actions?: QuickAction[]
}

export default function QuickActions({ onSelect, compact, actions }: QuickActionsProps) {
  const items = actions || defaultActions

  return (
    <div className={`flex flex-wrap gap-2 ${compact ? 'gap-1.5' : ''}`}>
      {items.map((action, i) => (
        <motion.button
          key={action.label}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.03 }}
          onClick={() => onSelect(action.prompt)}
          className={`inline-flex items-center gap-1 rounded-lg border border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:border-primary-300 dark:hover:border-primary-700 text-gray-700 dark:text-gray-300 transition-colors ${
            compact ? 'text-xs px-2 py-1' : 'text-xs px-3 py-1.5'
          }`}
        >
          <span>{action.icon}</span>
          <span>{action.label}</span>
        </motion.button>
      ))}
    </div>
  )
}
