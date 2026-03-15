'use client'

import { usePathname, useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { getUserRole, getRoleLabel, getRoleColor, getRolePermissions, UserRole } from '@/utils/roles'

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
  permission?: keyof ReturnType<typeof getRolePermissions>
}

const navItems: NavItem[] = [
  {
    label: 'Дашборд',
    href: '/dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    label: 'Договоры',
    href: '/contracts',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    label: 'Загрузить',
    href: '/contracts/upload',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
      </svg>
    ),
    permission: 'canAnalyze',
  },
  {
    label: 'Генерировать',
    href: '/contracts/generate',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
    permission: 'canGenerate',
  },
  {
    label: 'Клаузулы',
    href: '/clauses',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
]

interface SidebarProps {
  user: { name?: string; email?: string; role?: string } | null
  onLogout: () => void
}

export default function Sidebar({ user, onLogout }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const role = getUserRole()
  const permissions = getRolePermissions(role)
  const roleLabel = getRoleLabel(role)
  const roleColor = getRoleColor(role)

  const filteredItems = navItems.filter(item => {
    if (!item.permission) return true
    return permissions[item.permission] as boolean
  })

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-white border-r border-gray-200 flex flex-col z-40">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center shadow-sm">
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-stone-800 leading-tight">Contract AI</h1>
            <p className="text-xs text-gray-500">Система</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/dashboard' && pathname.startsWith(item.href) && item.href !== '/contracts' ? true : false) ||
            (item.href === '/contracts' && pathname === '/contracts')

          return (
            <motion.button
              key={item.href}
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => router.push(item.href)}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
                ${isActive
                  ? 'bg-primary-50 text-primary-700 shadow-sm'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
            >
              <span className={isActive ? 'text-primary-600' : 'text-gray-400'}>
                {item.icon}
              </span>
              <span>{item.label}</span>
              {isActive && (
                <motion.div
                  layoutId="activeIndicator"
                  className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-600"
                />
              )}
            </motion.button>
          )
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-gray-100 p-4">
        <div className="flex items-center space-x-3 mb-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${roleColor.gradient} flex items-center justify-center`}>
            <span className="text-white text-sm font-bold">
              {(user?.name || '?')[0].toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-stone-800 truncate">{user?.name}</p>
            <p className={`text-xs font-medium ${roleColor.text}`}>{roleLabel}</p>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center space-x-2 px-4 py-2 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all duration-200"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Выйти</span>
        </button>
      </div>
    </aside>
  )
}
