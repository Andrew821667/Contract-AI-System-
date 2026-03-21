'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useMyOrganizations() {
  return useQuery({
    queryKey: ['my-organizations'],
    queryFn: () => api.listMyOrganizations(),
  })
}

export function useOrganization(orgId: string | null) {
  return useQuery({
    queryKey: ['organization', orgId],
    queryFn: () => api.getOrganization(orgId!),
    enabled: !!orgId,
  })
}

export function useOrgMembers(orgId: string | null) {
  return useQuery({
    queryKey: ['org-members', orgId],
    queryFn: () => api.listOrgMembers(orgId!),
    enabled: !!orgId,
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; slug: string; description?: string }) =>
      api.createOrganization(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-organizations'] })
    },
  })
}

export function useAddOrgMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, ...data }: { orgId: string; user_id: string; functional_role?: string; company_role?: string }) =>
      api.addOrgMember(orgId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['org-members', variables.orgId] })
    },
  })
}

export function usePolicies(level?: string) {
  return useQuery({
    queryKey: ['policies', level],
    queryFn: () => api.listPolicies(level),
  })
}

export function useTools() {
  return useQuery({
    queryKey: ['tools'],
    queryFn: () => api.listTools(),
  })
}

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => api.listAgents(),
  })
}
