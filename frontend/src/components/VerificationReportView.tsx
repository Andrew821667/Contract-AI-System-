'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import { VerificationReport } from '@/services/api'

interface Props {
  report: VerificationReport
}

const ASSESSMENT_LABELS: Record<VerificationReport['overall_assessment'], { label: string; variant: 'success' | 'warning' | 'danger' | 'default' }> = {
  ok: { label: 'Соответствует', variant: 'success' },
  warnings: { label: 'Есть замечания', variant: 'warning' },
  critical: { label: 'Критические расхождения', variant: 'danger' },
  error: { label: 'Ошибка сверки', variant: 'default' },
}

const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'default'> = {
  critical: 'danger',
  warning: 'warning',
  info: 'info',
}

export default function VerificationReportView({ report }: Props) {
  const [expandReqs, setExpandReqs] = useState(true)
  const [expandContr, setExpandContr] = useState(true)
  const [expandDiff, setExpandDiff] = useState(false)

  const overall = ASSESSMENT_LABELS[report.overall_assessment]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      <Card>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 className="text-xl font-bold text-gray-900 mb-1">Отчёт о сверке</h3>
            <p className="text-xs text-gray-500">
              {report.created_at ? new Date(report.created_at).toLocaleString('ru-RU') : ''}
              {report.duration_ms ? ` · ${(report.duration_ms / 1000).toFixed(1)} с` : ''}
              {report.llm_model ? ` · LLM: ${report.llm_model}` : ''}
            </p>
          </div>
          <Badge variant={overall.variant} size="md">{overall.label}</Badge>
        </div>
        {report.error && (
          <p className="text-red-600 text-sm mt-2">Ошибка: {report.error}</p>
        )}
      </Card>

      {/* Requisites */}
      <Card>
        <button
          onClick={() => setExpandReqs((s) => !s)}
          className="w-full flex items-center justify-between text-left"
        >
          <div>
            <h4 className="text-lg font-semibold text-gray-900">1. Реквизиты</h4>
            <p className="text-xs text-gray-500">
              {report.requisites?.ok
                ? 'Все реквизиты соответствуют'
                : `Несовпадений: ${report.requisites?.mismatches.length || 0}`}
            </p>
          </div>
          <span className="text-gray-400">{expandReqs ? '▾' : '▸'}</span>
        </button>

        {expandReqs && report.requisites && (
          <div className="mt-3 space-y-2">
            {report.requisites.ok && (
              <p className="text-sm text-green-700">
                ✓ Номер, дата, контрагенты и валюта согласованы с основным документом.
              </p>
            )}
            {report.requisites.mismatches.map((m, i) => (
              <div
                key={i}
                className="border-l-4 pl-3 py-2"
                style={{
                  borderColor:
                    m.severity === 'critical' ? '#dc2626' :
                    m.severity === 'warning' ? '#d97706' : '#6b7280',
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-gray-900">
                    {fieldLabel(m.field)}
                  </p>
                  <Badge variant={SEVERITY_VARIANT[m.severity] || 'default'} size="sm">
                    {severityLabel(m.severity)}
                  </Badge>
                </div>
                <p className="text-sm text-gray-700 mt-1">{m.message}</p>
                {(m.parent_value !== undefined || m.child_value !== undefined) && (
                  <div className="mt-2 text-xs text-gray-500 grid grid-cols-1 md:grid-cols-2 gap-2">
                    <div>
                      <span className="font-semibold">Основной: </span>
                      <code className="bg-gray-50 px-1 rounded">{formatValue(m.parent_value)}</code>
                    </div>
                    <div>
                      <span className="font-semibold">Производный: </span>
                      <code className="bg-gray-50 px-1 rounded">{formatValue(m.child_value)}</code>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Contradictions */}
      <Card>
        <button
          onClick={() => setExpandContr((s) => !s)}
          className="w-full flex items-center justify-between text-left"
        >
          <div>
            <h4 className="text-lg font-semibold text-gray-900">2. Противоречия условий</h4>
            <p className="text-xs text-gray-500">
              {report.contradictions?.skipped
                ? `Пропущено${report.contradictions.reason ? ': ' + report.contradictions.reason : ''}`
                : `Найдено: ${report.contradictions?.count || 0}`}
            </p>
          </div>
          <span className="text-gray-400">{expandContr ? '▾' : '▸'}</span>
        </button>

        {expandContr && report.contradictions && !report.contradictions.skipped && (
          <div className="mt-3 space-y-3">
            {report.contradictions.count === 0 && (
              <p className="text-sm text-green-700">
                ✓ Противоречий не обнаружено.
              </p>
            )}
            {report.contradictions.items.map((it, i) => (
              <div
                key={i}
                className="border-l-4 pl-3 py-2"
                style={{
                  borderColor:
                    it.severity === 'critical' ? '#dc2626' :
                    it.severity === 'warning' ? '#d97706' : '#6b7280',
                }}
              >
                <div className="flex items-center justify-between gap-3 mb-1">
                  <Badge variant={SEVERITY_VARIANT[it.severity] || 'default'} size="sm">
                    {severityLabel(it.severity)}
                  </Badge>
                </div>
                <p className="text-sm text-gray-900 italic mb-1">«{it.clause}»</p>
                <p className="text-sm text-gray-700">{it.rationale}</p>
                {it.parent_reference && (
                  <p className="text-xs text-gray-500 mt-1">
                    <span className="font-semibold">Условие основного: </span>
                    {it.parent_reference}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Diff */}
      <Card>
        <button
          onClick={() => setExpandDiff((s) => !s)}
          className="w-full flex items-center justify-between text-left"
        >
          <div>
            <h4 className="text-lg font-semibold text-gray-900">3. Сравнение текстов</h4>
            <p className="text-xs text-gray-500">
              {report.diff?.skipped
                ? `Пропущено${report.diff.reason ? ': ' + report.diff.reason : ''}`
                : `Изменений: ${report.diff?.total_changes || 0}`}
            </p>
          </div>
          <span className="text-gray-400">{expandDiff ? '▾' : '▸'}</span>
        </button>

        {expandDiff && report.diff && !report.diff.skipped && (
          <div className="mt-3">
            {report.diff.total_changes === 0 && (
              <p className="text-sm text-green-700">✓ Тексты идентичны.</p>
            )}
            {report.diff.total_changes > 0 && (
              <>
                <div className="flex gap-2 flex-wrap mb-3">
                  {Object.entries(report.diff.by_category).map(([cat, n]) => (
                    <Badge key={cat} variant="info" size="sm">
                      {cat}: {n}
                    </Badge>
                  ))}
                </div>
                <div className="space-y-1 max-h-96 overflow-auto">
                  {report.diff.items.map((it, i) => (
                    <div
                      key={i}
                      className={`text-xs px-3 py-1 rounded font-mono ${
                        it.change_type === 'addition'
                          ? 'bg-green-50 text-green-900'
                          : it.change_type === 'deletion'
                          ? 'bg-red-50 text-red-900'
                          : 'bg-gray-50 text-gray-700'
                      }`}
                    >
                      <span className="opacity-60 mr-1">
                        {it.change_type === 'addition' ? '+' : it.change_type === 'deletion' ? '−' : '·'}
                      </span>
                      {it.change_type === 'addition' ? it.new_content : it.old_content || it.new_content}
                    </div>
                  ))}
                </div>
                {report.diff.truncated && (
                  <p className="text-xs text-gray-500 mt-2">
                    Показано первых {report.diff.items.length} из {report.diff.total_changes}.
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </Card>
    </motion.div>
  )
}

function fieldLabel(field: string): string {
  const map: Record<string, string> = {
    contract_number: 'Номер договора',
    contract_date: 'Дата договора',
    counterparties: 'Контрагенты',
    currency: 'Валюта',
    effective_period: 'Период действия',
  }
  return map[field] || field
}

function severityLabel(s: string): string {
  return s === 'critical' ? 'Критично' : s === 'warning' ? 'Предупреждение' : 'Инфо'
}

function formatValue(v: any): string {
  if (v === null || v === undefined) return '—'
  if (Array.isArray(v)) return v.length ? v.join(', ') : '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
