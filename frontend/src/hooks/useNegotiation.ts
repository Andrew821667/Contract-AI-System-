'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useNegotiation(negotiationId: string | null) {
  return useQuery({
    queryKey: ['negotiation', negotiationId],
    queryFn: () => api.getNegotiation(negotiationId!),
    enabled: !!negotiationId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'in_progress' || status === 'generating') return 3000
      return false
    },
  })
}

export function useStartNegotiation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { document_id: string; goal: string; analysis_id?: string }) =>
      api.startNegotiation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['negotiation'] })
    },
  })
}

export function useGenerateObjections() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { negotiation_id: string; risk_ids?: string[]; custom_instructions?: string }) =>
      api.generateObjections(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['negotiation', variables.negotiation_id] })
    },
  })
}

export function useSelectObjections() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { negotiation_id: string; selected_objection_ids: string[]; priority_order?: string[] }) =>
      api.selectObjections(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['negotiation', variables.negotiation_id] })
    },
  })
}

export function usePreparePosition() {
  return useMutation({
    mutationFn: (data: { negotiation_id: string; strategy?: string; focus_areas?: string[] }) =>
      api.preparePosition(data),
  })
}
