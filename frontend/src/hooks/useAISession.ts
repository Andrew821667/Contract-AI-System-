'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import api from '@/services/api'

export function useAISessions(documentId: string | null) {
  return useQuery({
    queryKey: ['ai-sessions', documentId],
    queryFn: () => api.listAISessions(documentId!),
    enabled: !!documentId,
  })
}

export function useAIMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ['ai-messages', sessionId],
    queryFn: () => api.getAIMessages(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      // Poll every 3s while the last message is from the user (waiting for AI response)
      const messages = query.state.data?.messages
      if (messages && messages.length > 0) {
        const last = messages[messages.length - 1]
        if (last.role === 'user') return 3000
      }
      return false
    },
  })
}

export function useAIActions(sessionId: string | null) {
  return useQuery({
    queryKey: ['ai-actions', sessionId],
    queryFn: () => api.listAIActions(sessionId!),
    enabled: !!sessionId,
    refetchInterval: 5000,
  })
}

export function useAIContext(sessionId: string | null) {
  return useQuery({
    queryKey: ['ai-context', sessionId],
    queryFn: () => api.getAIContext(sessionId!),
    enabled: !!sessionId,
  })
}

export function useCreateAISession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId, stage }: { documentId: string | null; stage?: string }) =>
      api.createAISession(documentId, stage),
    onSuccess: (_, variables) => {
      if (variables.documentId) {
        queryClient.invalidateQueries({ queryKey: ['ai-sessions', variables.documentId] })
      }
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка создания AI сессии')
    },
  })
}

export function useSendAIMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, content }: { sessionId: string; content: string }) =>
      api.sendAIMessage(sessionId, content),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['ai-messages', variables.sessionId] })
      queryClient.invalidateQueries({ queryKey: ['ai-actions', variables.sessionId] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка отправки сообщения')
    },
  })
}

export function useApproveAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId, comment }: { actionId: string; comment?: string }) =>
      api.approveAIAction(actionId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-actions'] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка подтверждения действия')
    },
  })
}

export function useRejectAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId, comment }: { actionId: string; comment?: string }) =>
      api.rejectAIAction(actionId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-actions'] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка отклонения действия')
    },
  })
}
