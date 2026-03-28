'use client'

import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { getUserRole, getRoleLabel, getRoleColor, getRolePermissions } from '@/utils/roles'
import { useTheme } from '@/hooks/useTheme'

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
    label: 'AI Ассистент',
    href: '/ai',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-2.47 2.47a3.375 3.375 0 01-4.06.54M5 14.5l2.47 2.47a3.375 3.375 0 004.06.54m0 0v3.24m0-3.24a3.375 3.375 0 00-4.06-.54" />
      </svg>
    ),
  },
  {
    label: 'Переговоры',
    href: '/negotiations',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
      </svg>
    ),
  },
  {
    label: 'Workflow',
    href: '/workflow',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
      </svg>
    ),
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
  {
    label: 'Управление',
    href: '/admin',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    permission: 'canManageUsers',
  },
]

interface SidebarProps {
  user: { name?: string; email?: string; role?: string } | null
  onLogout: () => void
  isOpen: boolean
  onClose: () => void
}

function SidebarContent({ user, onLogout, onNavigate }: {
  user: SidebarProps['user']
  onLogout: () => void
  onNavigate: () => void
}) {
  const pathname = usePathname()
  const router = useRouter()
  const role = getUserRole()
  const permissions = getRolePermissions(role)
  const roleLabel = getRoleLabel(role)
  const roleColor = getRoleColor(role)
  const { resolvedTheme, toggleTheme, mounted } = useTheme()

  const filteredItems = navItems.filter(item => {
    if (!item.permission) return true
    return permissions[item.permission] as boolean
  })

  const handleNav = (href: string) => {
    router.push(href)
    onNavigate()
  }

  return (
    <>
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100 dark:border-dark-700">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center shadow-sm">
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-stone-800 dark:text-gray-100 leading-tight">Contract AI</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Система</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Основная навигация">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/dashboard' && item.href !== '/contracts' && pathname.startsWith(item.href)) ||
            (item.href === '/contracts' && pathname === '/contracts')

          return (
            <motion.button
              key={item.href}
              whileTap={{ scale: 0.98 }}
              onClick={() => handleNav(item.href)}
              aria-current={isActive ? 'page' : undefined}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
                ${isActive
                  ? 'bg-primary-50 text-primary-700 shadow-sm dark:bg-primary-900/30 dark:text-primary-300'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-dark-700 dark:hover:text-gray-200'
                }`}
            >
              <span className={isActive ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400 dark:text-gray-500'}>
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

      {/* Theme toggle */}
      <div className="px-4 py-2 border-t border-gray-100 dark:border-dark-700">
        {mounted && (
          <button
            onClick={toggleTheme}
            className="w-full flex items-center space-x-3 px-4 py-2.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-700 rounded-xl transition-all duration-200"
          >
            {resolvedTheme === 'dark' ? (
              <svg className="w-5 h-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : resolvedTheme === 'steel' ? (
              <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            )}
            <span>
              {resolvedTheme === 'dark' ? 'Светлая тема' : resolvedTheme === 'steel' ? 'Тёмная тема' : 'Стальная тема'}
            </span>
          </button>
        )}
      </div>

      {/* User section */}
      <div className="border-t border-gray-100 dark:border-dark-700 p-4">
        <div className="flex items-center space-x-3 mb-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${roleColor.gradient} flex items-center justify-center`}>
            <span className="text-white text-sm font-bold">
              {(user?.name || '?')[0].toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-stone-800 dark:text-gray-100 truncate">{user?.name}</p>
            <p className={`text-xs font-medium ${roleColor.text}`}>{roleLabel}</p>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center space-x-2 px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all duration-200"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Выйти</span>
        </button>
      </div>
    </>
  )
}

export default function Sidebar({ user, onLogout, isOpen, onClose }: SidebarProps) {
  return (
    <>
      {/* Desktop sidebar — always visible on lg+ */}
      <aside className="hidden lg:flex fixed left-0 top-0 h-screen w-64 bg-white dark:bg-dark-900 border-r border-gray-200 dark:border-dark-700 flex-col z-40">
        <SidebarContent user={user} onLogout={onLogout} onNavigate={() => {}} />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
              className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            />
            {/* Drawer */}
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="lg:hidden fixed left-0 top-0 h-screen w-72 bg-white dark:bg-dark-900 shadow-2xl flex flex-col z-50"
            >
              {/* Close button */}
              <button
                onClick={onClose}
                aria-label="Закрыть меню"
                className="absolute top-4 right-4 p-2 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-xl transition z-10"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <SidebarContent user={user} onLogout={onLogout} onNavigate={onClose} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
