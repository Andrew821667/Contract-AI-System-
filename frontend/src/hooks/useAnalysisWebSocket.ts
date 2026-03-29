'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import api from '@/services/api'
import { useAuthStore } from '../stores/authStore'

export interface WSMessage {
  type: string
  contract_id: string
  status: string
  progress: number
  message: string
  data?: Record<string, any>
}

interface UseAnalysisWebSocketOptions {
  onProgress?: (data: WSMessage) => void
  onComplete?: (data: WSMessage) => void
  onError?: (data: WSMessage) => void
  enabled?: boolean
}

interface UseAnalysisWebSocketReturn {
  progress: number
  status: string
  message: string
  isConnected: boolean
}

const POLL_INTERVAL_MS = 2000

/**
 * Hybrid hook: polling is ALWAYS active during analysis, WS is optional bonus.
 * This guarantees progress updates even when WebSocket auth fails.
 */
export function useAnalysisWebSocket(
  contractId: string,
  options: UseAnalysisWebSocketOptions = {}
): UseAnalysisWebSocketReturn {
  const { onProgress, onComplete, onError, enabled = true } = options

  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('connecting')
  const [message, setMessage] = useState('Подключение...')
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const unmountedRef = useRef(false)
  const terminalRef = useRef(false) // true when completed/error — stop everything

  // Stable callback refs
  const onProgressRef = useRef(onProgress)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  onProgressRef.current = onProgress
  onCompleteRef.current = onComplete
  onErrorRef.current = onError

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  const closeWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onerror = null
      wsRef.current.onclose = null
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close()
      }
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  // ── Polling (always active during analysis) ──────────────────────
  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) return // already polling
    pollIntervalRef.current = setInterval(async () => {
      if (unmountedRef.current || terminalRef.current) return
      try {
        const data = await api.getContract(contractId)
        const contract = data?.contract
        if (!contract || unmountedRef.current) return

        // Use granular progress from backend meta_info
        const statusProgress: Record<string, number> = {
          uploaded: 0, parsing: 10, analyzing: 50, completed: 100, error: 0,
        }
        const p = contract.progress ?? statusProgress[contract.status] ?? 0
        setProgress(p)
        setStatus(contract.status)
        setMessage(contract.progress_message || `Статус: ${contract.status}`)

        if (contract.status === 'completed') {
          terminalRef.current = true
          const msg: WSMessage = {
            type: 'analysis_complete', contract_id: contractId,
            status: 'completed', progress: 100,
            message: 'Анализ завершён',
          }
          onCompleteRef.current?.(msg)
          stopPolling()
          closeWs()
        } else if (contract.status === 'error') {
          terminalRef.current = true
          const msg: WSMessage = {
            type: 'error', contract_id: contractId,
            status: 'error', progress: 0,
            message: 'Ошибка анализа',
          }
          onErrorRef.current?.(msg)
          stopPolling()
          closeWs()
        } else if (contract.status === 'uploaded') {
          // Analysis was cancelled or never started
          terminalRef.current = true
          stopPolling()
          closeWs()
        }
      } catch {
        // ignore polling errors — next tick will retry
      }
    }, POLL_INTERVAL_MS)
  }, [contractId, stopPolling, closeWs])

  // ── WebSocket (bonus — realtime updates if auth works) ───────────
  const connectWs = useCallback(() => {
    if (unmountedRef.current || terminalRef.current) return

    const token = useAuthStore.getState().accessToken
    if (!token) return // no token — rely on polling only

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws/analysis/${contractId}`

    closeWs()

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) return
        ws.send(JSON.stringify({ type: 'auth', token }))
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        if (unmountedRef.current) return
        try {
          const data: WSMessage = JSON.parse(event.data)

          // Ignore auth errors from server — polling handles it
          if (data.type === 'error' && data.message === 'Authentication failed') {
            closeWs()
            return
          }

          setProgress(data.progress ?? 0)
          setStatus(data.status ?? '')
          setMessage(data.message ?? '')

          if (data.type === 'analysis_complete') {
            terminalRef.current = true
            onCompleteRef.current?.(data)
            stopPolling()
            closeWs()
          } else if (data.type === 'error') {
            // Don't treat all WS errors as terminal — polling will detect real errors
            closeWs()
          } else {
            onProgressRef.current?.(data)
          }
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
        // Don't reconnect — polling is already running and will handle everything
      }
    } catch {
      // WS failed — polling is already running
    }
  }, [contractId, closeWs, stopPolling])

  // ── Lifecycle ────────────────────────────────────────────────────
  useEffect(() => {
    unmountedRef.current = false
    terminalRef.current = false

    if (!enabled) {
      closeWs()
      stopPolling()
      return
    }

    // Always start polling first — it's the reliable backbone
    startPolling()
    // Then try WS as a bonus
    connectWs()

    return () => {
      unmountedRef.current = true
      closeWs()
      stopPolling()
    }
  }, [enabled, connectWs, startPolling, closeWs, stopPolling])

  return { progress, status, message, isConnected }
}
