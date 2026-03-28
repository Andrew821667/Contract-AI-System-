'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useWebhooks(orgId?: string) {
  return useQuery({
    queryKey: ['webhooks', orgId],
    queryFn: () => api.listWebhooks(orgId),
  })
}

export function useCreateWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      name: string
      url: string
      secret?: string
      event_filter?: string[]
      org_id?: string
    }) => api.createWebhook(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
    },
  })
}

export function useDeactivateWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (configId: string) => api.deactivateWebhook(configId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
    },
  })
}

export function useWebhookDeliveries(configId: string | null) {
  return useQuery({
    queryKey: ['webhook-deliveries', configId],
    queryFn: () => api.getWebhookDeliveries(configId!),
    enabled: !!configId,
  })
}

export function useRetryDeliveries() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (limit?: number) => api.retryFailedDeliveries(limit),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhook-deliveries'] })
    },
  })
}

export function useDomainEvents(params?: {
  entity_type?: string
  event_type?: string
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ['domain-events', params],
    queryFn: () => api.listDomainEvents(params),
  })
}

export function useEventTypes() {
  return useQuery({
    queryKey: ['event-types'],
    queryFn: () => api.listEventTypes(),
    staleTime: 5 * 60 * 1000,
  })
}
