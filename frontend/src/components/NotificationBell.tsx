'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { type Notification } from '@/hooks/useNotifications'

interface NotificationBellProps {
  notifications: Notification[]
  unreadCount: number
  isConnected: boolean
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearAll: () => void
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'только что'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} мин. назад`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} ч. назад`
  return `${Math.floor(hours / 24)} дн. назад`
}

const severityStyles: Record<string, { icon: string; bg: string; border: string }> = {
  warning: { icon: '\u26A0\uFE0F', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  error: { icon: '\u274C', bg: 'bg-red-50', border: 'border-red-200' },
  info: { icon: '\u2139\uFE0F', bg: 'bg-blue-50', border: 'border-blue-200' },
}

export default function NotificationBell({
  notifications,
  unreadCount,
  isConnected,
  markAsRead,
  markAllAsRead,
  clearAll,
}: NotificationBellProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition-colors"
        aria-label="Уведомления"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        {/* Unread badge */}
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </motion.span>
        )}
      </motion.button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-xl border border-gray-200 z-50 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-gray-900">Уведомления</h3>
                <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-gray-300'}`} />
              </div>
              <div className="flex items-center gap-2">
                {unreadCount > 0 && (
                  <button
                    onClick={markAllAsRead}
                    className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                  >
                    Прочитать все
                  </button>
                )}
                {notifications.length > 0 && (
                  <button
                    onClick={clearAll}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    Очистить
                  </button>
                )}
              </div>
            </div>

            {/* List */}
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <svg className="w-8 h-8 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  <p className="text-sm">Нет уведомлений</p>
                </div>
              ) : (
                notifications.map((notif) => {
                  const style = severityStyles[notif.severity] || severityStyles.info
                  return (
                    <button
                      key={notif.id}
                      onClick={() => markAsRead(notif.id)}
                      className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                        !notif.read ? 'bg-primary-50/30' : ''
                      }`}
                    >
                      <div className="flex gap-3">
                        <span className="text-base flex-shrink-0 mt-0.5">{style.icon}</span>
                        <div className="flex-1 min-w-0">
                          {notif.title && (
                            <p className={`text-sm font-medium text-gray-900 truncate ${!notif.read ? 'font-semibold' : ''}`}>
                              {notif.title}
                            </p>
                          )}
                          <p className="text-xs text-gray-600 line-clamp-2">{notif.message}</p>
                          <p className="text-[10px] text-gray-400 mt-1">{timeAgo(notif.timestamp)}</p>
                        </div>
                        {!notif.read && (
                          <span className="w-2 h-2 rounded-full bg-primary-500 flex-shrink-0 mt-1.5" />
                        )}
                      </div>
                    </button>
                  )
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
