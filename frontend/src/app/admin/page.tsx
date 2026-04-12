'use client'

import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'
import {
  useMyOrganizations,
  useOrgMembers,
  useCreateOrganization,
  useAddOrgMember,
  usePolicies,
  useTools,
  useAgents,
} from '@/hooks/useOrganization'
import {
  useClausePolicies,
  useCreateClausePolicy,
  useTemplateVersions,
  useActivateTemplateVersion,
} from '@/hooks/useTemplates'
import {
  useRagStats,
  useRagDocuments,
  useUploadRagDocument,
  useDeleteRagDocument,
} from '@/hooks/useRAGAdmin'
import type { Organization, OrgMembership, Policy, ToolDefinition, AgentDefinition, ClausePolicy, TemplateVersion, RAGDocument } from '@/services/api'
import LLMSettings from '@/components/admin/LLMSettings'
import IntegrationSettings from '@/components/admin/IntegrationSettings'
import GraphRAGPanel from '@/components/admin/GraphRAGPanel'

type Tab = 'orgs' | 'policies' | 'tools' | 'agents' | 'templates' | 'integrations' | 'llm' | 'graph' | 'rag'

const RAG_COLLECTIONS = [
  { value: 'knowledge', label: 'База знаний' },
  { value: 'laws', label: 'Законы и НПА' },
  { value: 'case_law', label: 'Судебная практика' },
  { value: 'templates', label: 'Шаблоны' },
]

const RAG_DOC_TYPES = [
  { value: 'law', label: 'Закон / НПА' },
  { value: 'regulation', label: 'Регламент' },
  { value: 'template', label: 'Шаблон договора' },
  { value: 'court_decision', label: 'Судебное решение' },
  { value: 'guidance', label: 'Методические указания' },
  { value: 'document', label: 'Прочее' },
]

export default function AdminPage() {
  const { isReady } = useAuthGuard()
  const [activeTab, setActiveTab] = useState<Tab>('llm')
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [showCreateOrg, setShowCreateOrg] = useState(false)
  const [orgName, setOrgName] = useState('')
  const [orgSlug, setOrgSlug] = useState('')
  const [orgDesc, setOrgDesc] = useState('')
  const [showAddMember, setShowAddMember] = useState(false)
  const [memberId, setMemberId] = useState('')
  const [memberRole, setMemberRole] = useState('member')
  const [policyLevel, setPolicyLevel] = useState<string | undefined>(undefined)
  const [clausePolicyStatus, setClausePolicyStatus] = useState<string | undefined>(undefined)
  const [showCreateClausePolicy, setShowCreateClausePolicy] = useState(false)
  const [cpClauseType, setCpClauseType] = useState('')
  const [cpStatus, setCpStatus] = useState('approved')
  const [cpRiskExplanation, setCpRiskExplanation] = useState('')
  const [templateIdInput, setTemplateIdInput] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)

  const [ragCollection, setRagCollection] = useState('knowledge')
  const [ragDocType, setRagDocType] = useState('document')
  const [ragUploadError, setRagUploadError] = useState<string | null>(null)
  const [ragUploadSuccess, setRagUploadSuccess] = useState<string | null>(null)
  const [ragDragging, setRagDragging] = useState(false)
  const ragFileInputRef = useRef<HTMLInputElement>(null)

  const { data: orgs = [] } = useMyOrganizations()
  const { data: members = [] } = useOrgMembers(selectedOrgId)
  const { data: policies = [] } = usePolicies(policyLevel)
  const { data: tools = [] } = useTools()
  const { data: agents = [] } = useAgents()
  const { data: clausePolicies = [] } = useClausePolicies(undefined, clausePolicyStatus)
  const createClausePolicy = useCreateClausePolicy()
  const { data: templateVersions = [] } = useTemplateVersions(selectedTemplateId)
  const activateVersion = useActivateTemplateVersion()
  const createOrg = useCreateOrganization()
  const addMember = useAddOrgMember()

  const { data: ragStats } = useRagStats()
  const { data: ragDocsData, isLoading: ragLoading } = useRagDocuments(ragCollection)
  const uploadRagDoc = useUploadRagDocument()
  const deleteRagDoc = useDeleteRagDocument()

  const ragDocuments = ragDocsData?.documents ?? []

  const handleRagUpload = async (file: File) => {
    setRagUploadError(null)
    setRagUploadSuccess(null)
    try {
      const result = await uploadRagDoc.mutateAsync({ file, collection: ragCollection, docType: ragDocType })
      setRagUploadSuccess(`Загружено: "${result.title}" (${result.chunks} чанков)`)
    } catch (e: any) {
      setRagUploadError(e?.response?.data?.detail || 'Ошибка загрузки')
    }
  }

  const handleRagFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setRagDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleRagUpload(file)
  }

  const handleRagFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleRagUpload(file)
    e.target.value = ''
  }

  const handleRagDelete = async (doc: RAGDocument) => {
    if (!confirm(`Удалить "${doc.title}" из базы знаний? Все чанки будут удалены.`)) return
    await deleteRagDoc.mutateAsync({ docId: doc.doc_id, collection: ragCollection })
  }

  if (!isReady) return null

  const handleCreateOrg = async () => {
    if (!orgName.trim() || !orgSlug.trim()) return
    const org = await createOrg.mutateAsync({
      name: orgName.trim(),
      slug: orgSlug.trim(),
      description: orgDesc.trim() || undefined,
    })
    setSelectedOrgId(org.id)
    setShowCreateOrg(false)
    setOrgName('')
    setOrgSlug('')
    setOrgDesc('')
  }

  const handleAddMember = async () => {
    if (!selectedOrgId || !memberId.trim()) return
    await addMember.mutateAsync({
      orgId: selectedOrgId,
      user_id: memberId.trim(),
      functional_role: memberRole,
    })
    setShowAddMember(false)
    setMemberId('')
    setMemberRole('member')
  }

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'llm', label: 'LLM Модели' },
    { key: 'rag', label: 'База знаний' },
    { key: 'orgs', label: 'Организации', count: orgs.length },
    { key: 'policies', label: 'Политики', count: policies.length },
    { key: 'tools', label: 'Инструменты', count: tools.length },
    { key: 'agents', label: 'Агенты', count: agents.length },
    { key: 'integrations', label: 'Интеграции' },
    { key: 'graph', label: 'Graph-RAG' },
    { key: 'templates', label: 'Шаблоны' },
  ]

  const handleCreateClausePolicy = async () => {
    if (!cpClauseType.trim()) return
    await createClausePolicy.mutateAsync({
      clause_type: cpClauseType.trim(),
      status: cpStatus,
      risk_explanation: cpRiskExplanation.trim() || undefined,
    })
    setShowCreateClausePolicy(false)
    setCpClauseType('')
    setCpStatus('approved')
    setCpRiskExplanation('')
  }

  const handleLoadVersions = () => {
    if (templateIdInput.trim()) {
      setSelectedTemplateId(templateIdInput.trim())
    }
  }

  return (
    <AppLayout title="Администрирование">
      <div className="max-w-5xl mx-auto">
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
              {tab.count !== undefined && (
                <span className="ml-1.5 text-[10px] bg-gray-200 dark:bg-dark-600 px-1.5 py-0.5 rounded-full">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* LLM Settings tab */}
        {activeTab === 'llm' && <LLMSettings />}

        {/* RAG База знаний */}
        {activeTab === 'rag' && (
          <div className="space-y-6">
            {/* Stats */}
            {ragStats && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {ragStats.collections.map((c) => (
                  <button
                    key={c.name}
                    onClick={() => setRagCollection(c.name)}
                    className={`p-3 rounded-xl border text-left transition-colors ${
                      ragCollection === c.name
                        ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/10'
                        : 'border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 hover:border-gray-300'
                    }`}
                  >
                    <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{c.label}</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-gray-100">{c.doc_count}</p>
                    <p className="text-[10px] text-gray-400">{c.chunk_count} чанков</p>
                  </button>
                ))}
              </div>
            )}

            {/* Upload */}
            <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5">
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-4">Загрузить документ</h3>

              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <div>
                  <label className="text-[10px] text-gray-500 dark:text-gray-400 mb-1 block">Коллекция</label>
                  <select
                    value={ragCollection}
                    onChange={(e) => setRagCollection(e.target.value)}
                    className="bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs text-gray-800 dark:text-gray-200"
                  >
                    {RAG_COLLECTIONS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 dark:text-gray-400 mb-1 block">Тип документа</label>
                  <select
                    value={ragDocType}
                    onChange={(e) => setRagDocType(e.target.value)}
                    className="bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs text-gray-800 dark:text-gray-200"
                  >
                    {RAG_DOC_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setRagDragging(true) }}
                onDragLeave={() => setRagDragging(false)}
                onDrop={handleRagFileDrop}
                onClick={() => ragFileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  ragDragging
                    ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/10'
                    : 'border-gray-200 dark:border-dark-700 hover:border-primary-300 hover:bg-gray-50 dark:hover:bg-dark-700/50'
                }`}
              >
                <input
                  ref={ragFileInputRef}
                  type="file"
                  accept=".txt,.pdf,.docx"
                  className="hidden"
                  onChange={handleRagFileSelect}
                />
                {uploadRagDoc.isPending ? (
                  <p className="text-sm text-primary-600 dark:text-primary-400 font-medium">Загрузка и индексация...</p>
                ) : (
                  <>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Перетащите файл или нажмите для выбора
                    </p>
                    <p className="text-[10px] text-gray-400 mt-1">Поддерживается: .txt, .pdf, .docx</p>
                  </>
                )}
              </div>

              {ragUploadSuccess && (
                <p className="mt-3 text-xs text-green-600 dark:text-green-400 font-medium">{ragUploadSuccess}</p>
              )}
              {ragUploadError && (
                <p className="mt-3 text-xs text-red-600 dark:text-red-400">{ragUploadError}</p>
              )}
            </div>

            {/* Documents list */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">
                  Документы — {RAG_COLLECTIONS.find((c) => c.value === ragCollection)?.label}
                  <span className="ml-2 text-[10px] font-normal text-gray-400">({ragDocuments.length})</span>
                </h3>
              </div>

              {ragLoading ? (
                <p className="text-xs text-gray-400 text-center py-6">Загрузка...</p>
              ) : ragDocuments.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-6">Нет документов в этой коллекции</p>
              ) : (
                <div className="space-y-2">
                  {ragDocuments.map((doc) => (
                    <div
                      key={doc.doc_id}
                      className="flex items-center justify-between bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{doc.title}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          {doc.doc_type && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">
                              {doc.doc_type}
                            </span>
                          )}
                          <span className="text-[10px] text-gray-400">{doc.chunks} чанков</span>
                          {doc.created_at && (
                            <span className="text-[10px] text-gray-400">
                              {new Date(doc.created_at).toLocaleDateString('ru-RU')}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => handleRagDelete(doc)}
                        disabled={deleteRagDoc.isPending}
                        className="ml-4 text-[10px] px-2 py-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors disabled:opacity-40 shrink-0"
                      >
                        Удалить
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Organizations tab */}
        {activeTab === 'orgs' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Org list */}
            <div className="lg:col-span-1">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">Организации</h3>
                <button
                  onClick={() => setShowCreateOrg(!showCreateOrg)}
                  className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                >
                  {showCreateOrg ? 'Отмена' : '+ Создать'}
                </button>
              </div>

              <AnimatePresence>
                {showCreateOrg && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4 mb-3 overflow-hidden"
                  >
                    <input
                      type="text"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      placeholder="Название"
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <input
                      type="text"
                      value={orgSlug}
                      onChange={(e) => setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                      placeholder="slug (латиница, цифры, дефис)"
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <input
                      type="text"
                      value={orgDesc}
                      onChange={(e) => setOrgDesc(e.target.value)}
                      placeholder="Описание (необязательно)"
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <button
                      onClick={handleCreateOrg}
                      disabled={!orgName.trim() || !orgSlug.trim() || createOrg.isPending}
                      className="w-full px-3 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      {createOrg.isPending ? 'Создание...' : 'Создать'}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="space-y-2">
                {orgs.map((org: Organization) => (
                  <button
                    key={org.id}
                    onClick={() => setSelectedOrgId(org.id)}
                    className={`w-full text-left p-3 rounded-xl border transition-colors ${
                      selectedOrgId === org.id
                        ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/10'
                        : 'border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 hover:border-gray-300'
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{org.name}</p>
                    <p className="text-[10px] text-gray-400 font-mono">{org.slug}</p>
                  </button>
                ))}
                {orgs.length === 0 && !showCreateOrg && (
                  <p className="text-xs text-gray-400 text-center py-4">Нет организаций</p>
                )}
              </div>
            </div>

            {/* Org details + members */}
            <div className="lg:col-span-2">
              {selectedOrgId ? (
                <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">
                      Участники ({members.length})
                    </h3>
                    <button
                      onClick={() => setShowAddMember(!showAddMember)}
                      className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                    >
                      {showAddMember ? 'Отмена' : '+ Добавить'}
                    </button>
                  </div>

                  {showAddMember && (
                    <div className="flex items-center gap-2 mb-4">
                      <input
                        type="text"
                        value={memberId}
                        onChange={(e) => setMemberId(e.target.value)}
                        placeholder="ID пользователя"
                        className="flex-1 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                      <select
                        value={memberRole}
                        onChange={(e) => setMemberRole(e.target.value)}
                        className="bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2 py-1.5 text-xs text-gray-800 dark:text-gray-200"
                      >
                        <option value="member">Участник</option>
                        <option value="lawyer">Юрист</option>
                        <option value="senior_lawyer">Ст. юрист</option>
                        <option value="org_admin">Админ</option>
                      </select>
                      <button
                        onClick={handleAddMember}
                        disabled={!memberId.trim() || addMember.isPending}
                        className="px-3 py-1.5 bg-primary-600 text-white text-xs font-medium rounded-lg disabled:opacity-40"
                      >
                        Добавить
                      </button>
                    </div>
                  )}

                  <div className="space-y-2">
                    {members.map((m: OrgMembership) => (
                      <div key={m.id} className="flex items-center justify-between p-2.5 rounded-lg bg-gray-50 dark:bg-dark-900">
                        <div>
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 font-mono">{m.user_id.slice(0, 12)}...</span>
                          {m.company_role && <span className="text-[10px] text-gray-400 ml-2">{m.company_role}</span>}
                        </div>
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                          m.functional_role === 'org_admin' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' :
                          m.functional_role === 'senior_lawyer' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                          'bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400'
                        }`}>
                          {m.functional_role}
                        </span>
                      </div>
                    ))}
                    {members.length === 0 && (
                      <p className="text-xs text-gray-400 text-center py-4">Нет участников</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <p className="text-sm text-gray-400">Выберите организацию</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Policies tab */}
        {activeTab === 'policies' && (
          <div>
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              {[undefined, 'platform', 'organization', 'document', 'user'].map(lvl => (
                <button
                  key={lvl || 'all'}
                  onClick={() => setPolicyLevel(lvl)}
                  className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                    policyLevel === lvl
                      ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-700'
                  }`}
                >
                  {lvl ? lvl : 'Все'}
                </button>
              ))}
            </div>
            <div className="space-y-2">
              {policies.map((p: Policy) => (
                <div key={p.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="text-sm font-medium text-gray-800 dark:text-gray-200">{p.name}</h4>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        p.effect === 'allow' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        p.effect === 'deny' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                        'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                      }`}>
                        {p.effect}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">{p.level}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-gray-400">
                    <span>Действие: {p.action_type}</span>
                    <span>Приоритет: {p.priority}</span>
                    <span className={p.active ? 'text-green-500' : 'text-gray-400'}>{p.active ? 'Активна' : 'Неактивна'}</span>
                  </div>
                </div>
              ))}
              {policies.length === 0 && <p className="text-xs text-gray-400 text-center py-8">Нет политик</p>}
            </div>
          </div>
        )}

        {/* Tools tab */}
        {activeTab === 'tools' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {tools.map((t: ToolDefinition) => (
              <div key={t.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-sm font-bold text-gray-800 dark:text-gray-200">{t.display_name || t.name}</h4>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    t.active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {t.active ? 'Активен' : 'Неактивен'}
                  </span>
                </div>
                {t.description && <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t.description}</p>}
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                  <span className="font-mono">{t.name}</span>
                  {t.category && <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700">{t.category}</span>}
                </div>
              </div>
            ))}
            {tools.length === 0 && (
              <div className="md:col-span-2 text-center py-8">
                <p className="text-xs text-gray-400">Нет зарегистрированных инструментов</p>
              </div>
            )}
          </div>
        )}

        {/* Templates tab */}
        {activeTab === 'templates' && (
          <div className="space-y-6">
            {/* Clause Policies */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">Политики клауз</h3>
                <button
                  onClick={() => setShowCreateClausePolicy(!showCreateClausePolicy)}
                  className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                >
                  {showCreateClausePolicy ? 'Отмена' : '+ Создать'}
                </button>
              </div>

              {/* Status filter */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                {[undefined, 'approved', 'prohibited', 'risky', 'fallback'].map(s => (
                  <button
                    key={s || 'all'}
                    onClick={() => setClausePolicyStatus(s)}
                    className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                      clausePolicyStatus === s
                        ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                        : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-700'
                    }`}
                  >
                    {s ? s : 'Все'}
                  </button>
                ))}
              </div>

              <AnimatePresence>
                {showCreateClausePolicy && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4 mb-3 overflow-hidden"
                  >
                    <input
                      type="text"
                      value={cpClauseType}
                      onChange={(e) => setCpClauseType(e.target.value)}
                      placeholder="Тип клаузы (financial, liability, termination...)"
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <select
                      value={cpStatus}
                      onChange={(e) => setCpStatus(e.target.value)}
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200"
                    >
                      <option value="approved">Approved</option>
                      <option value="prohibited">Prohibited</option>
                      <option value="risky">Risky</option>
                      <option value="fallback">Fallback</option>
                    </select>
                    <textarea
                      value={cpRiskExplanation}
                      onChange={(e) => setCpRiskExplanation(e.target.value)}
                      placeholder="Пояснение риска (необязательно)"
                      rows={2}
                      className="w-full bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs mb-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                    />
                    <button
                      onClick={handleCreateClausePolicy}
                      disabled={!cpClauseType.trim() || createClausePolicy.isPending}
                      className="w-full px-3 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      {createClausePolicy.isPending ? 'Создание...' : 'Создать'}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="space-y-2">
                {clausePolicies.map((cp: ClausePolicy) => (
                  <div key={cp.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-sm font-medium text-gray-800 dark:text-gray-200">{cp.clause_type}</h4>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        cp.status === 'approved' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        cp.status === 'prohibited' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                        cp.status === 'risky' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
                        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                      }`}>
                        {cp.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-gray-400">
                      {cp.org_id && <span>Орг: {cp.org_id.slice(0, 8)}...</span>}
                      {!cp.org_id && <span>Платформенная</span>}
                      {cp.risk_explanation && <span className="truncate max-w-[200px]">{cp.risk_explanation}</span>}
                    </div>
                  </div>
                ))}
                {clausePolicies.length === 0 && <p className="text-xs text-gray-400 text-center py-4">Нет политик клауз</p>}
              </div>
            </div>

            {/* Template Versions */}
            <div>
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-3">Версии шаблонов</h3>
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="text"
                  value={templateIdInput}
                  onChange={(e) => setTemplateIdInput(e.target.value)}
                  placeholder="ID шаблона"
                  className="flex-1 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-1.5 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
                <button
                  onClick={handleLoadVersions}
                  disabled={!templateIdInput.trim()}
                  className="px-4 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  Загрузить
                </button>
              </div>

              {selectedTemplateId && (
                <div className="space-y-2">
                  {templateVersions.map((v: TemplateVersion) => (
                    <div key={v.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Версия {v.version}
                        </h4>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                            v.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                            v.status === 'draft' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
                            'bg-gray-100 text-gray-500'
                          }`}>
                            {v.status}
                          </span>
                          {v.status === 'draft' && (
                            <button
                              onClick={() => activateVersion.mutate(v.id)}
                              disabled={activateVersion.isPending}
                              className="text-[10px] px-2 py-0.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-medium rounded-lg transition-colors"
                            >
                              Активировать
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-gray-400">
                        <span>{new Date(v.created_at).toLocaleDateString('ru-RU')}</span>
                        {v.created_by && <span>Автор: {v.created_by.slice(0, 8)}...</span>}
                        {v.variables && <span>{v.variables.length} переменных</span>}
                      </div>
                    </div>
                  ))}
                  {templateVersions.length === 0 && <p className="text-xs text-gray-400 text-center py-4">Нет версий</p>}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Integrations tab */}
        {activeTab === 'integrations' && <IntegrationSettings />}

        {/* Graph-RAG tab */}
        {activeTab === 'graph' && <GraphRAGPanel />}

        {/* Agents tab */}
        {activeTab === 'agents' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents.map((a: AgentDefinition) => (
              <div key={a.id} className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-4">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-sm font-bold text-gray-800 dark:text-gray-200">{a.display_name || a.name}</h4>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    a.active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {a.active ? 'Активен' : 'Неактивен'}
                  </span>
                </div>
                {a.description && <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{a.description}</p>}
                <div className="flex items-center gap-2 text-[10px] text-gray-400 mb-2">
                  <span className="font-mono">{a.name}</span>
                  {a.agent_type && <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700">{a.agent_type}</span>}
                </div>
                {a.capabilities && a.capabilities.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {a.capabilities.map((c, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-300">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                {a.tools && a.tools.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {a.tools.map((t, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500 font-mono">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {agents.length === 0 && (
              <div className="md:col-span-2 text-center py-8">
                <p className="text-xs text-gray-400">Нет зарегистрированных агентов</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
