'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useOrchestratorRun(runId: string | null) {
  return useQuery({
    queryKey: ['orchestrator-run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'running' || status === 'planning') return 2000
      return false
    },
  })
}

export function useRunSteps(runId: string | null) {
  return useQuery({
    queryKey: ['orchestrator-steps', runId],
    queryFn: () => api.getRunSteps(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      // Poll while run is active
      return runId ? 2000 : false
    },
  })
}

export function useCreateRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ goal, documentId }: { goal: string; documentId?: string }) =>
      api.createRun(goal, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orchestrator-run'] })
    },
  })
}

export function useContinueRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => api.continueRun(runId),
    onSuccess: (_, runId) => {
      queryClient.invalidateQueries({ queryKey: ['orchestrator-run', runId] })
      queryClient.invalidateQueries({ queryKey: ['orchestrator-steps', runId] })
    },
  })
}

export function useCancelRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: (_, runId) => {
      queryClient.invalidateQueries({ queryKey: ['orchestrator-run', runId] })
      queryClient.invalidateQueries({ queryKey: ['orchestrator-steps', runId] })
    },
  })
}
