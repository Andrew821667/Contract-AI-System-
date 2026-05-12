'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import api, {
  ContractRelation,
  ContractRelationType,
  ContractParty,
  RelationTypeOption,
  PartyRoleOption,
  Counterparty,
  VerificationReport,
} from '@/services/api'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import CounterpartyAutocomplete from '@/components/CounterpartyAutocomplete'
import ContractAutocomplete from '@/components/ContractAutocomplete'
import VerificationReportView from '@/components/VerificationReportView'

interface Props {
  contractId: string
}

export default function RelatedDocumentsSection({ contractId }: Props) {
  const router = useRouter()
  const queryClient = useQueryClient()

  const [showAddParent, setShowAddParent] = useState(false)
  const [parentRel, setParentRel] = useState<ContractRelationType>('supplementary_agreement')
  const [parentContract, setParentContract] = useState<{ id: string; file_name: string } | null>(null)
  const [parentCustomLabel, setParentCustomLabel] = useState('')
  const [parentCustomPrompt, setParentCustomPrompt] = useState('')

  const [showAddParty, setShowAddParty] = useState(false)
  const [partyCp, setPartyCp] = useState<Counterparty | null>(null)
  const [partyRole, setPartyRole] = useState<string>('counterparty')

  const { data: bundle, isLoading } = useQuery({
    queryKey: ['contract-related', contractId],
    queryFn: () => api.getContractRelated(contractId),
    enabled: !!contractId,
  })

  const { data: relationTypes = [] } = useQuery<RelationTypeOption[]>({
    queryKey: ['relation-types'],
    queryFn: () => api.getRelationTypes(),
    staleTime: 5 * 60_000,
  })

  const { data: partyRoles = [] } = useQuery<PartyRoleOption[]>({
    queryKey: ['party-roles'],
    queryFn: () => api.getPartyRoles(),
    staleTime: 5 * 60_000,
  })

  const linkParent = useMutation({
    mutationFn: (data: {
      parent_contract_id: string
      relation_type: ContractRelationType
      custom_label?: string
      custom_prompt?: string
    }) => api.linkContractParent(contractId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-related', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
      setShowAddParent(false)
      setParentContract(null)
      setParentCustomLabel('')
      setParentCustomPrompt('')
      toast.success('Основной договор привязан')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка привязки'),
  })

  const unlinkRel = useMutation({
    mutationFn: (relationId: string) => api.unlinkContractRelation(contractId, relationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-related', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
      toast.success('Связь удалена')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка'),
  })

  const addParty = useMutation({
    mutationFn: (data: { counterparty_id: string; role: any }) =>
      api.addContractParty(contractId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-related', contractId] })
      setShowAddParty(false)
      setPartyCp(null)
      setPartyRole('counterparty')
      toast.success('Сторона добавлена')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка'),
  })

  const removeParty = useMutation({
    mutationFn: (partyId: string) => api.removeContractParty(contractId, partyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-related', contractId] })
      toast.success('Сторона удалена')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка'),
  })

  const findParent = useMutation({
    mutationFn: () => api.findContractParent(contractId),
    onSuccess: (resp) => {
      if (resp.candidates.length === 0) {
        toast(
          resp.message ||
            'Кандидатов не найдено. Можно привязать вручную через «Указать основной договор».',
        )
        return
      }
      toast.success(`Найдено кандидатов: ${resp.candidates.length}`)
      // Авто-открыть форму с первым кандидатом
      const top = resp.candidates[0]
      setParentContract({
        id: top.contract_id,
        file_name: top.file_name,
      })
      setShowAddParent(true)
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка поиска'),
  })

  // ── Verification ──────────────────────────────────────────────────────────
  const [showReport, setShowReport] = useState(false)
  const [reportRelationId, setReportRelationId] = useState<string | undefined>(undefined)

  const verificationsQuery = useQuery({
    queryKey: ['verifications', contractId, reportRelationId],
    queryFn: () => api.listVerifications(contractId, reportRelationId, 5),
    enabled: !!contractId,
  })

  const verifyMutation = useMutation({
    mutationFn: (relationId?: string) => api.verifyAgainstParent(contractId, relationId),
    onSuccess: (report: VerificationReport) => {
      const overall = report.overall_assessment
      const msg =
        overall === 'ok'
          ? 'Сверка пройдена'
          : overall === 'critical'
          ? 'Найдены критические расхождения'
          : overall === 'warnings'
          ? 'Есть замечания'
          : 'Сверка не выполнена'
      if (overall === 'ok') toast.success(msg)
      else if (overall === 'critical') toast.error(msg)
      else toast(msg)
      setShowReport(true)
      queryClient.invalidateQueries({ queryKey: ['verifications', contractId] })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка сверки'),
  })

  const latestReport = verificationsQuery.data?.verifications?.[0]

  const grouped = useMemo(() => {
    const map = new Map<ContractRelationType, ContractRelation[]>()
    for (const r of bundle?.derivatives || []) {
      const list = map.get(r.relation_type) || []
      list.push(r)
      map.set(r.relation_type, list)
    }
    return map
  }, [bundle?.derivatives])

  if (isLoading) {
    return (
      <Card className="mb-8">
        <p className="text-gray-500">Загрузка связанных документов…</p>
      </Card>
    )
  }

  const hasParents = (bundle?.parents?.length || 0) > 0
  const hasDerivatives = (bundle?.derivatives?.length || 0) > 0
  const hasParties = (bundle?.parties?.length || 0) > 0

  const isCustom = parentRel === 'custom'

  return (
    <Card className="mb-8">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-gray-900">Связанные документы и стороны</h2>
        <div className="flex gap-2">
          {!hasParents && (
            <>
              <Button size="sm" variant="outline" onClick={() => findParent.mutate()} disabled={findParent.isPending}>
                {findParent.isPending ? 'Поиск…' : 'Найти основной автоматически'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowAddParent(true)}>
                Указать основной договор
              </Button>
            </>
          )}
          <Button size="sm" variant="outline" onClick={() => setShowAddParty(true)}>
            + Добавить сторону
          </Button>
        </div>
      </div>

      {/* Parents */}
      {hasParents && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide">
              Основной договор
            </h3>
            <div className="flex gap-2 items-center">
              {latestReport && (
                <Badge
                  variant={
                    latestReport.overall_assessment === 'ok'
                      ? 'success'
                      : latestReport.overall_assessment === 'critical'
                      ? 'danger'
                      : latestReport.overall_assessment === 'warnings'
                      ? 'warning'
                      : 'default'
                  }
                  size="sm"
                >
                  {latestReport.overall_assessment === 'ok'
                    ? 'Сверка: OK'
                    : latestReport.overall_assessment === 'critical'
                    ? 'Сверка: критично'
                    : latestReport.overall_assessment === 'warnings'
                    ? 'Сверка: замечания'
                    : 'Сверка: ошибка'}
                </Badge>
              )}
              <Button
                size="sm"
                variant="primary"
                onClick={() =>
                  verifyMutation.mutate(
                    bundle!.parents.length === 1 ? undefined : bundle!.parents[0].id,
                  )
                }
                disabled={verifyMutation.isPending}
              >
                {verifyMutation.isPending ? 'Сверяем…' : 'Запустить сверку'}
              </Button>
              {latestReport && (
                <Button size="sm" variant="outline" onClick={() => setShowReport((s) => !s)}>
                  {showReport ? 'Скрыть отчёт' : 'Показать отчёт'}
                </Button>
              )}
            </div>
          </div>
          {bundle!.parents.map((rel) => (
            <RelationRow
              key={rel.id}
              rel={rel}
              side="parent"
              relationTypes={relationTypes}
              onOpen={() => router.push(`/contracts/${rel.parent_contract_id}`)}
              onUnlink={() => {
                if (confirm('Отвязать этот документ от основного договора?')) {
                  unlinkRel.mutate(rel.id)
                }
              }}
            />
          ))}

          {showReport && latestReport && (
            <div className="mt-4">
              <VerificationReportView report={latestReport} />
            </div>
          )}
        </div>
      )}

      {/* Parties */}
      {hasParties && (
        <div className="mb-6">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-2">
            Стороны
          </h3>
          <div className="space-y-2">
            {bundle!.parties.map((p) => (
              <PartyRow
                key={p.id}
                party={p}
                partyRoles={partyRoles}
                onRemove={() => {
                  if (confirm('Удалить эту сторону?')) removeParty.mutate(p.id)
                }}
                onClick={() => router.push(`/counterparties/${p.counterparty_id}`)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Derivatives by type */}
      {hasDerivatives && (
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-2">
            Производные документы
          </h3>
          {Array.from(grouped.entries()).map(([type, rels]) => (
            <div key={type} className="mb-4">
              <p className="text-sm font-semibold text-gray-700 mb-2">
                {relationTypes.find((rt) => rt.value === type)?.label || type}{' '}
                <span className="text-gray-400">· {rels.length}</span>
              </p>
              <div className="space-y-2">
                {rels.map((rel) => (
                  <RelationRow
                    key={rel.id}
                    rel={rel}
                    side="child"
                    relationTypes={relationTypes}
                    onOpen={() => router.push(`/contracts/${rel.child_contract_id}`)}
                    onUnlink={() => {
                      if (confirm('Удалить связь?')) unlinkRel.mutate(rel.id)
                    }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!hasParents && !hasDerivatives && !hasParties && (
        <p className="text-gray-500 text-sm">
          У этого документа пока нет связей. Вы можете указать основной договор, добавить контрагентов
          или загрузить производные документы (доп.соглашения, спецификации, акты и т. п.).
        </p>
      )}

      {/* Add parent modal */}
      <AnimatePresence>
        {showAddParent && (
          <Modal onClose={() => setShowAddParent(false)} title="Привязать основной договор">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Тип связи</label>
                <select
                  value={parentRel}
                  onChange={(e) => setParentRel(e.target.value as ContractRelationType)}
                  className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                >
                  {relationTypes.map((rt) => (
                    <option key={rt.value} value={rt.value}>{rt.label}</option>
                  ))}
                </select>
              </div>

              {isCustom && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">Название кастомного типа</label>
                    <input
                      value={parentCustomLabel}
                      onChange={(e) => setParentCustomLabel(e.target.value)}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Промпт (опционально)</label>
                    <textarea
                      value={parentCustomPrompt}
                      onChange={(e) => setParentCustomPrompt(e.target.value)}
                      rows={2}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium mb-1">Основной договор</label>
                <ContractAutocomplete
                  value={parentContract}
                  onChange={setParentContract}
                  excludeContractId={contractId}
                />
              </div>

              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setShowAddParent(false)}>
                  Отмена
                </Button>
                <Button
                  variant="primary"
                  disabled={!parentContract || (isCustom && !parentCustomLabel.trim() && !parentCustomPrompt.trim())}
                  onClick={() =>
                    parentContract &&
                    linkParent.mutate({
                      parent_contract_id: parentContract.id,
                      relation_type: parentRel,
                      custom_label: parentCustomLabel || undefined,
                      custom_prompt: parentCustomPrompt || undefined,
                    })
                  }
                  loading={linkParent.isPending}
                >
                  Привязать
                </Button>
              </div>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Add party modal */}
      <AnimatePresence>
        {showAddParty && (
          <Modal onClose={() => setShowAddParty(false)} title="Добавить сторону">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Контрагент</label>
                <CounterpartyAutocomplete value={partyCp} onChange={setPartyCp} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Роль</label>
                <select
                  value={partyRole}
                  onChange={(e) => setPartyRole(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
                >
                  {partyRoles.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setShowAddParty(false)}>Отмена</Button>
                <Button
                  variant="primary"
                  disabled={!partyCp}
                  onClick={() =>
                    partyCp &&
                    addParty.mutate({ counterparty_id: partyCp.id, role: partyRole })
                  }
                  loading={addParty.isPending}
                >
                  Добавить
                </Button>
              </div>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </Card>
  )
}

// ── Modal ───────────────────────────────────────────────────────────────────

function Modal({
  title,
  children,
  onClose,
}: {
  title: string
  children: React.ReactNode
  onClose: () => void
}) {
  return (
    <motion.div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-visible"
      >
        <h2 className="text-2xl font-bold mb-4">{title}</h2>
        {children}
      </motion.div>
    </motion.div>
  )
}

// ── Rows ────────────────────────────────────────────────────────────────────

function RelationRow({
  rel,
  side,
  relationTypes,
  onOpen,
  onUnlink,
}: {
  rel: ContractRelation
  side: 'parent' | 'child'
  relationTypes: RelationTypeOption[]
  onOpen: () => void
  onUnlink: () => void
}) {
  const target = side === 'parent' ? rel.parent : rel.child
  const typeLabel =
    relationTypes.find((rt) => rt.value === rel.relation_type)?.label || rel.relation_type
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 rounded-xl border border-gray-200 hover:border-primary-300 transition-colors">
      <button onClick={onOpen} className="flex-1 min-w-0 text-left">
        <p className="font-medium truncate">{target?.file_name || rel.relation_type}</p>
        <p className="text-xs text-gray-500">
          {typeLabel}
          {rel.custom_label ? ` · ${rel.custom_label}` : ''}
          {target?.contract_number ? ` · № ${target.contract_number}` : ''}
          {target?.contract_date
            ? ` · от ${new Date(target.contract_date).toLocaleDateString('ru-RU')}`
            : ''}
        </p>
        {rel.auto_detected && rel.confidence !== null && rel.confidence !== undefined && (
          <p className="text-xs text-primary-600 mt-1">
            Автодетект · уверенность {Math.round((rel.confidence || 0) * 100)}%
          </p>
        )}
      </button>
      <div className="flex items-center gap-2">
        {target?.status && <Badge variant={target.status === 'completed' ? 'success' : 'default'} size="sm">{target.status}</Badge>}
        <button onClick={onUnlink} className="text-gray-400 hover:text-red-600 text-sm px-2">
          ✕
        </button>
      </div>
    </div>
  )
}

function PartyRow({
  party,
  partyRoles,
  onRemove,
  onClick,
}: {
  party: ContractParty
  partyRoles: PartyRoleOption[]
  onRemove: () => void
  onClick: () => void
}) {
  const roleLabel =
    partyRoles.find((r) => r.value === party.role)?.label || party.role
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 rounded-xl border border-gray-200 hover:border-primary-300 transition-colors">
      <button onClick={onClick} className="flex-1 min-w-0 text-left">
        <p className="font-medium truncate">{party.counterparty_name || '—'}</p>
        <p className="text-xs text-gray-500">
          {roleLabel}
          {party.counterparty_inn ? ` · ИНН ${party.counterparty_inn}` : ''}
        </p>
      </button>
      <button onClick={onRemove} className="text-gray-400 hover:text-red-600 text-sm px-2">
        ✕
      </button>
    </div>
  )
}
