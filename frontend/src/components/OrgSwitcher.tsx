'use client'

import { useEffect, useState } from 'react'
import api from '@/services/api'
import { useOrgStore } from '@/stores/orgStore'

interface Org {
  id: string
  name: string
  slug: string
}

export default function OrgSwitcher() {
  const [orgs, setOrgs] = useState<Org[]>([])
  const { selectedOrgId, setSelectedOrg } = useOrgStore()

  useEffect(() => {
    api.getMyOrganizations()
      .then(setOrgs)
      .catch(() => {})
  }, [])

  if (orgs.length === 0) return null

  return (
    <div className="px-4 py-3 border-t border-gray-100 dark:border-dark-700">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
        Контекст
      </p>
      <select
        value={selectedOrgId || ''}
        onChange={(e) => {
          const orgId = e.target.value || null
          const org = orgs.find(o => o.id === orgId)
          setSelectedOrg(orgId, org?.name || null)
        }}
        className="w-full px-3 py-2 text-sm bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 rounded-lg focus:border-primary-400 focus:outline-none transition-colors"
      >
        <option value="">Личное пространство</option>
        {orgs.map(org => (
          <option key={org.id} value={org.id}>{org.name}</option>
        ))}
      </select>
    </div>
  )
}
