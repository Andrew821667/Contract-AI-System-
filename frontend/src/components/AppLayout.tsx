'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import api, { User } from '@/services/api'
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
    const token = localStorage.getItem('access_token')
    if (!token) {
      router.push('/login')
    }
  }, [router])

  // Fetch current user
  const { data: user, isLoading } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: () => api.getCurrentUser(),
  })

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    localStorage.removeItem('passwordChanged')
    toast.success('Вы вышли из системы')
    router.push('/login')
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-stone-50 to-stone-100">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full"
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
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
        <header className="bg-white/80 backdrop-blur-lg border-b border-gray-100 sticky top-0 z-30">
          <div className="px-4 sm:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {/* Hamburger — mobile only */}
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 hover:bg-gray-100 rounded-xl transition"
              >
                <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              {title && (
                <h1 className="text-xl sm:text-2xl font-bold text-stone-800">{title}</h1>
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
              <div className="hidden sm:block text-sm text-gray-500">
                {user?.name}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
