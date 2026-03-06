'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import api from '@/services/api'

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

const MAX_RECONNECT_ATTEMPTS = 3
const RECONNECT_DELAY_MS = 2000
const POLL_INTERVAL_MS = 5000

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
  const reconnectAttemptsRef = useRef(0)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const unmountedRef = useRef(false)

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

  const startPolling = useCallback(() => {
    stopPolling()
    pollIntervalRef.current = setInterval(async () => {
      try {
        const data = await api.getContract(contractId)
        const contract = data?.contract
        if (!contract || unmountedRef.current) return

        const progressMap: Record<string, number> = {
          uploaded: 0,
          parsing: 10,
          analyzing: 50,
          completed: 100,
          error: 0,
        }
        const p = progressMap[contract.status] ?? 0
        setProgress(p)
        setStatus(contract.status)
        setMessage(`Status: ${contract.status}`)

        if (contract.status === 'completed') {
          const msg: WSMessage = {
            type: 'analysis_complete',
            contract_id: contractId,
            status: 'completed',
            progress: 100,
            message: 'Analysis completed successfully',
          }
          onCompleteRef.current?.(msg)
          stopPolling()
        } else if (contract.status === 'error') {
          const msg: WSMessage = {
            type: 'error',
            contract_id: contractId,
            status: 'error',
            progress: 0,
            message: 'Analysis failed',
          }
          onErrorRef.current?.(msg)
          stopPolling()
        }
      } catch {
        // ignore polling errors
      }
    }, POLL_INTERVAL_MS)
  }, [contractId, stopPolling])

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

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    if (!token) {
      startPolling()
      return
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl = apiUrl.replace(/^http/, 'ws') + `/api/v1/ws/analysis/${contractId}?token=${token}`

    closeWs()

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) return
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        setMessage('Подключено к серверу')
        stopPolling()
      }

      ws.onmessage = (event) => {
        if (unmountedRef.current) return
        try {
          const data: WSMessage = JSON.parse(event.data)
          setProgress(data.progress ?? 0)
          setStatus(data.status ?? '')
          setMessage(data.message ?? '')

          if (data.type === 'analysis_complete') {
            onCompleteRef.current?.(data)
            closeWs()
          } else if (data.type === 'error') {
            onErrorRef.current?.(data)
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

        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++
          setMessage(`Переподключение (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})...`)
          setTimeout(connect, RECONNECT_DELAY_MS)
        } else {
          setMessage('WebSocket недоступен, используется polling...')
          startPolling()
        }
      }
    } catch {
      startPolling()
    }
  }, [contractId, closeWs, startPolling, stopPolling])

  useEffect(() => {
    unmountedRef.current = false

    if (!enabled) {
      closeWs()
      stopPolling()
      return
    }

    connect()

    return () => {
      unmountedRef.current = true
      closeWs()
      stopPolling()
    }
  }, [enabled, connect, closeWs, stopPolling])

  return { progress, status, message, isConnected }
}
