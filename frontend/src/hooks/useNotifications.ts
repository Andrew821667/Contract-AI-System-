'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { toast } from 'react-hot-toast'

export interface Notification {
  id: string
  type: string
  title: string
  message: string
  severity: 'info' | 'warning' | 'error'
  timestamp: Date
  read: boolean
}

export interface UseNotificationsReturn {
  notifications: Notification[]
  unreadCount: number
  isConnected: boolean
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearAll: () => void
}

const MAX_NOTIFICATIONS = 20
const MAX_RECONNECT_ATTEMPTS = 3
const RECONNECT_DELAY_MS = 3000

let notifCounter = 0

export function useNotifications(): UseNotificationsReturn {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const unmountedRef = useRef(false)

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  )

  const addNotification = useCallback((data: any) => {
    const notif: Notification = {
      id: `notif-${++notifCounter}-${Date.now()}`,
      type: data.type || 'info',
      title: data.title || '',
      message: data.message || '',
      severity: data.severity || 'info',
      timestamp: new Date(),
      read: false,
    }

    setNotifications((prev) => [notif, ...prev].slice(0, MAX_NOTIFICATIONS))

    // Show toast
    const toastMsg = notif.title || notif.message
    if (notif.severity === 'error') {
      toast.error(toastMsg)
    } else if (notif.severity === 'warning') {
      toast(toastMsg, { icon: '\u26A0\uFE0F' })
    } else {
      toast(toastMsg, { icon: '\uD83D\uDD14' })
    }
  }, [])

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    )
  }, [])

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }, [])

  const clearAll = useCallback(() => {
    setNotifications([])
  }, [])

  const closeWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onerror = null
      wsRef.current.onclose = null
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close()
      }
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    const token =
      typeof window !== 'undefined'
        ? localStorage.getItem('access_token')
        : null
    if (!token) return

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl =
      apiUrl.replace(/^http/, 'ws') +
      `/api/v1/ws/notifications?token=${token}`

    closeWs()

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) return
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        if (unmountedRef.current) return
        try {
          const data = JSON.parse(event.data)
          // Skip the initial "connected" message
          if (data.type === 'connected') return
          addNotification(data)
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        if (unmountedRef.current) return
        setIsConnected(false)
      }

      ws.onclose = () => {
        if (unmountedRef.current) return
        setIsConnected(false)

        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++
          setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }
    } catch {
      // WS not available — silent fail
    }
  }, [closeWs, addNotification])

  useEffect(() => {
    unmountedRef.current = false
    connect()

    return () => {
      unmountedRef.current = true
      closeWs()
    }
  }, [connect, closeWs])

  return {
    notifications,
    unreadCount,
    isConnected,
    markAsRead,
    markAllAsRead,
    clearAll,
  }
}
