'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import api from '@/services/api'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'
import { useOrgStore } from '@/stores/orgStore'

interface Member {
  id: string
  user_id: string
  functional_role: string
  company_role: string | null
  active: boolean
  joined_at: string
}

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Администратор',
  manager: 'Менеджер',
  member: 'Участник',
  viewer: 'Наблюдатель',
}

const ROLE_COLORS: Record<string, string> = {
  org_admin: 'danger',
  manager: 'warning',
  member: 'info',
  viewer: 'default',
}

export default function OrganizationPage() {
  const { isReady } = useAuthGuard()
  const router = useRouter()
  const { selectedOrgId, selectedOrgName } = useOrgStore()

  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [inviting, setInviting] = useState(false)

  // Create org form
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newOrgName, setNewOrgName] = useState('')
  const [newOrgSlug, setNewOrgSlug] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (selectedOrgId) {
      setLoading(true)
      api.getOrgMembers(selectedOrgId)
        .then(setMembers)
        .catch(() => toast.error('Не удалось загрузить участников'))
        .finally(() => setLoading(false))
    } else {
      setMembers([])
      setLoading(false)
    }
  }, [selectedOrgId])

  const handleInvite = async () => {
    if (!selectedOrgId || !inviteEmail) return
    setInviting(true)
    try {
      await api.inviteMember(selectedOrgId, {
        email: inviteEmail,
        functional_role: inviteRole,
      })
      toast.success('Участник добавлен')
      setInviteEmail('')
      // Refresh members
      const updated = await api.getOrgMembers(selectedOrgId)
      setMembers(updated)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка приглашения')
    } finally {
      setInviting(false)
    }
  }

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (!selectedOrgId) return
    try {
      await api.updateMemberRole(selectedOrgId, userId, { functional_role: newRole })
      toast.success('Роль обновлена')
      const updated = await api.getOrgMembers(selectedOrgId)
      setMembers(updated)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка')
    }
  }

  const handleRemove = async (userId: string) => {
    if (!selectedOrgId) return
    if (!confirm('Удалить участника из организации?')) return
    try {
      await api.removeMember(selectedOrgId, userId)
      toast.success('Участник удалён')
      const updated = await api.getOrgMembers(selectedOrgId)
      setMembers(updated)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка')
    }
  }

  const handleCreateOrg = async () => {
    if (!newOrgName || !newOrgSlug) return
    setCreating(true)
    try {
      const org = await api.createOrganization({
        name: newOrgName,
        slug: newOrgSlug,
      })
      toast.success('Организация создана')
      useOrgStore.getState().setSelectedOrg(org.id, org.name)
      setShowCreateForm(false)
      setNewOrgName('')
      setNewOrgSlug('')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка создания')
    } finally {
      setCreating(false)
    }
  }

  if (!isReady) return null

  return (
    <AppLayout title="Организация">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold gradient-text mb-2">Организация</h1>
          <p className="text-gray-600">
            {selectedOrgId
              ? `Управление организацией: ${selectedOrgName}`
              : 'Создайте организацию или выберите существующую в боковой панели'
            }
          </p>
        </motion.div>

        {/* No org selected */}
        {!selectedOrgId && (
          <Card>
            {!showCreateForm ? (
              <div className="text-center py-8">
                <p className="text-gray-500 mb-4">Выберите организацию в боковой панели или создайте новую</p>
                <Button variant="primary" onClick={() => setShowCreateForm(true)}>
                  Создать организацию
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-gray-900">Новая организация</h3>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Название</label>
                  <input
                    type="text"
                    value={newOrgName}
                    onChange={(e) => {
                      setNewOrgName(e.target.value)
                      setNewOrgSlug(e.target.value.toLowerCase().replace(/[^a-zа-я0-9]/gi, '-').replace(/-+/g, '-'))
                    }}
                    placeholder="ООО Юридическая фирма"
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Slug (латиница)</label>
                  <input
                    type="text"
                    value={newOrgSlug}
                    onChange={(e) => setNewOrgSlug(e.target.value)}
                    placeholder="my-law-firm"
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none"
                  />
                </div>
                <div className="flex gap-3">
                  <Button variant="primary" onClick={handleCreateOrg} loading={creating}>
                    Создать
                  </Button>
                  <Button variant="outline" onClick={() => setShowCreateForm(false)}>
                    Отмена
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Org selected — show members */}
        {selectedOrgId && (
          <>
            {/* Invite member */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="mb-6"
            >
              <Card>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Пригласить участника</h3>
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <label className="block text-sm font-semibold text-gray-700 mb-1">Email</label>
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="user@example.com"
                      className="w-full px-4 py-2.5 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none"
                    />
                  </div>
                  <div className="w-40">
                    <label className="block text-sm font-semibold text-gray-700 mb-1">Роль</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none"
                    >
                      <option value="member">Участник</option>
                      <option value="manager">Менеджер</option>
                      <option value="viewer">Наблюдатель</option>
                      <option value="org_admin">Администратор</option>
                    </select>
                  </div>
                  <Button variant="primary" onClick={handleInvite} loading={inviting} disabled={!inviteEmail}>
                    Пригласить
                  </Button>
                </div>
              </Card>
            </motion.div>

            {/* Members list */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card>
                <h3 className="text-lg font-bold text-gray-900 mb-4">
                  Участники ({members.length})
                </h3>

                {loading ? (
                  <p className="text-gray-500 py-4 text-center">Загрузка...</p>
                ) : members.length === 0 ? (
                  <p className="text-gray-500 py-4 text-center">Нет участников</p>
                ) : (
                  <div className="space-y-3">
                    {members.map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between p-4 bg-gray-50 rounded-xl"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
                            <span className="text-primary-700 font-bold text-sm">
                              {m.user_id.substring(0, 2).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{m.user_id}</p>
                            {m.company_role && (
                              <p className="text-xs text-gray-500">{m.company_role}</p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <select
                            value={m.functional_role}
                            onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none"
                          >
                            <option value="org_admin">Администратор</option>
                            <option value="manager">Менеджер</option>
                            <option value="member">Участник</option>
                            <option value="viewer">Наблюдатель</option>
                          </select>
                          <button
                            onClick={() => handleRemove(m.user_id)}
                            className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                            title="Удалить"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </motion.div>
          </>
        )}
      </div>
    </AppLayout>
  )
}
