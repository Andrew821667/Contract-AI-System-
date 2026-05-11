'use client'

import { useEffect, useState } from 'react'
import api, { QuotaResponse } from '@/services/api'

export default function QuotaCounter() {
  const [quota, setQuota] = useState<QuotaResponse | null>(null)

  useEffect(() => {
    api.getQuota()
      .then(setQuota)
      .catch(() => {})
  }, [])

  if (!quota) return null

  const contractsLeft = Math.max(0, quota.contracts_limit - quota.contracts_used)
  const llmLeft = Math.max(0, quota.llm_limit - quota.llm_used)
  const contractsPeriodLabel = quota.contracts_period === 'month' ? 'за месяц' : 'сегодня'
  const contractsPct = quota.contracts_limit > 0
    ? (quota.contracts_used / quota.contracts_limit) * 100
    : 0
  const llmPct = quota.llm_limit > 0
    ? (quota.llm_used / quota.llm_limit) * 100
    : 0

  const getBarColor = (pct: number) => {
    if (pct >= 90) return 'bg-red-500'
    if (pct >= 70) return 'bg-amber-500'
    return 'bg-primary-500'
  }

  // Hide for enterprise users with unlimited quotas
  if (quota.contracts_limit >= 999999) return null

  return (
    <div className="px-4 py-3 border-t border-gray-100 dark:border-dark-700">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
        Лимиты
      </p>

      {/* Contracts */}
      <div className="mb-2">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-600 dark:text-gray-400">Договоры {contractsPeriodLabel}</span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {contractsLeft}/{quota.contracts_limit}
          </span>
        </div>
        <div className="h-1.5 bg-gray-200 dark:bg-dark-600 rounded-full overflow-hidden">
          <div
            className={`h-full ${getBarColor(contractsPct)} rounded-full transition-all duration-300`}
            style={{ width: `${Math.min(contractsPct, 100)}%` }}
          />
        </div>
      </div>

      {/* AI Requests */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-600 dark:text-gray-400">AI-запросы</span>
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {llmLeft}/{quota.llm_limit}
          </span>
        </div>
        <div className="h-1.5 bg-gray-200 dark:bg-dark-600 rounded-full overflow-hidden">
          <div
            className={`h-full ${getBarColor(llmPct)} rounded-full transition-all duration-300`}
            style={{ width: `${Math.min(llmPct, 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
