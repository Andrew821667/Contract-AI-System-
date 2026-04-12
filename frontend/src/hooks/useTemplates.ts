'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import api from '@/services/api'

export function useTemplateVersions(templateId: string | null) {
  return useQuery({
    queryKey: ['template-versions', templateId],
    queryFn: () => api.listTemplateVersions(templateId!),
    enabled: !!templateId,
  })
}

export function useCreateTemplateVersion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ templateId, ...data }: { templateId: string; content: Record<string, unknown>; variables?: Record<string, unknown>[] | null; validation_rules?: Record<string, unknown> | null }) =>
      api.createTemplateVersion(templateId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['template-versions', variables.templateId] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка создания версии шаблона')
    },
  })
}

export function useActivateTemplateVersion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (versionId: string) => api.activateTemplateVersion(versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['template-versions'] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка активации версии шаблона')
    },
  })
}

export function useClausePolicies(orgId?: string, statusFilter?: string) {
  return useQuery({
    queryKey: ['clause-policies', orgId, statusFilter],
    queryFn: () => api.listClausePolicies(orgId, statusFilter),
  })
}

export function useCreateClausePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { org_id?: string | null; clause_type: string; status: string; alternative_clause_id?: string | null; risk_explanation?: string | null }) =>
      api.createClausePolicy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clause-policies'] })
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Ошибка создания политики клауз')
    },
  })
}

export function useProhibitedClauses(orgId?: string) {
  return useQuery({
    queryKey: ['prohibited-clauses', orgId],
    queryFn: () => api.listProhibitedClauses(orgId),
  })
}
