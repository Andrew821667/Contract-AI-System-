'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import type { GraphAskRequest, GraphSearchRequest, GraphIngestRequest } from '@/services/api'

export function useGraphDocuments(layer?: string, limit?: number) {
  return useQuery({
    queryKey: ['graph-documents', layer, limit],
    queryFn: () => api.graphListDocuments(layer, limit),
  })
}

export function useGraphDocument(documentId: string | null, maxDepth?: number) {
  return useQuery({
    queryKey: ['graph-document', documentId, maxDepth],
    queryFn: () => api.graphGetDocument(documentId!, maxDepth),
    enabled: !!documentId,
  })
}

export function useGraphNode(nodeId: string | null, includeContext?: boolean) {
  return useQuery({
    queryKey: ['graph-node', nodeId, includeContext],
    queryFn: () => api.graphGetNode(nodeId!, includeContext),
    enabled: !!nodeId,
  })
}

export function useGraphStats(documentId?: string) {
  return useQuery({
    queryKey: ['graph-stats', documentId],
    queryFn: () => api.graphStats(documentId),
  })
}

export function useGraphEntitySummary(documentId: string | null) {
  return useQuery({
    queryKey: ['graph-entities', documentId],
    queryFn: () => api.graphEntitySummary(documentId!),
    enabled: !!documentId,
  })
}

export function useGraphPendingCandidates(limit?: number) {
  return useQuery({
    queryKey: ['graph-candidates-pending', limit],
    queryFn: () => api.graphPendingCandidates(limit),
  })
}

export function useGraphAsk() {
  return useMutation({
    mutationFn: (body: GraphAskRequest) => api.graphAsk(body),
  })
}

export function useGraphSearch() {
  return useMutation({
    mutationFn: (body: GraphSearchRequest) => api.graphSearch(body),
  })
}

export function useGraphIngest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: GraphIngestRequest) => api.graphIngest(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['graph-documents'] })
      queryClient.invalidateQueries({ queryKey: ['graph-stats'] })
    },
  })
}

export function useGraphProposeEdge() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof api.graphProposeEdge>[0]) => api.graphProposeEdge(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['graph-candidates-pending'] })
    },
  })
}

export function useGraphReviewCandidate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ candidateId, result, comment }: { candidateId: string; result: 'accepted' | 'rejected' | 'modified'; comment?: string }) =>
      api.graphReviewCandidate(candidateId, result, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['graph-candidates-pending'] })
    },
  })
}
