'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import api, { User } from '@/services/api'
import { useAuthStore } from '../stores/authStore'
import Sidebar from './Sidebar'
import NotificationBell from './NotificationBell'
import { useNotifications } from '@/hooks/useNotifications'

interface AppLayoutProps {
  children: React.ReactNode
  title?: string
}

export default function AppLayout({ children, title }: AppLayoutProps) {
  const router = useRouter()
  const notif = useNotifications()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Check auth
  useEffect(() => {
    const token = useAuthStore.getState().accessToken
    if (!token) {
      router.push('/login')
    }
  }, [router])

  // Fetch current user
  const { data: user, isLoading } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: () => api.getCurrentUser(),
  })

  const handleLogout = async () => {
    await api.logout()
    // Belt-and-suspenders: clear flag cookie & localStorage even if api.logout() missed something
    document.cookie = 'has_token=; path=/; max-age=0'
    localStorage.removeItem('passwordChanged')
    toast.success('Вы вышли из системы')
    router.push('/login')
  }

  if (isLoading) {
    return (
      <div className="brand-surface min-h-screen flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full"
        />
      </div>
    )
  }

  return (
    <div className="brand-surface min-h-screen">
      <div className="brand-grid fixed inset-0 pointer-events-none" aria-hidden="true" />
      {/* Skip to content link */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary-600 focus:text-white focus:rounded-xl">
        Перейти к содержимому
      </a>
      {/* Sidebar */}
      <Sidebar
        user={user || null}
        onLogout={handleLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content area — offset on desktop */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="bg-white/95 dark:bg-slate-950/80 backdrop-blur-xl border-b border-slate-400 dark:border-amber-500/20 shadow-lg shadow-slate-900/10 sticky top-0 z-30">
          <div className="px-4 sm:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {/* Hamburger — mobile only */}
              <button
                onClick={() => setSidebarOpen(true)}
                aria-label="Открыть меню"
                aria-expanded={sidebarOpen}
                className="lg:hidden p-2 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-xl transition"
              >
                <svg className="w-6 h-6 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              {title && (
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">{title}</h1>
              )}
            </div>
            <div className="flex items-center space-x-3">
              <NotificationBell
                notifications={notif.notifications}
                unreadCount={notif.unreadCount}
                isConnected={notif.isConnected}
                markAsRead={notif.markAsRead}
                markAllAsRead={notif.markAllAsRead}
                clearAll={notif.clearAll}
              />
              <div className="hidden sm:flex items-center space-x-3">
                <span className="text-sm text-slate-600 dark:text-slate-300">
                  {user?.name}
                </span>
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all duration-200"
                  title="Выйти из системы"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  <span>Выйти</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main id="main-content" className="relative p-4 sm:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
