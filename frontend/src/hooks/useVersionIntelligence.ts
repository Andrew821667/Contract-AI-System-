'use client'

import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/services/api'

export function useVersionHistory(documentId: string | null) {
  return useQuery({
    queryKey: ['version-history', documentId],
    queryFn: () => api.getVersionHistory(documentId!),
    enabled: !!documentId,
  })
}

export function useCompareVersions() {
  return useMutation({
    mutationFn: (data: { document_id: string; from_version_id: string; to_version_id: string; deep_analysis?: boolean }) =>
      api.compareVersionsV2(data),
  })
}

export function useMaterialChanges(comparisonId: string | null) {
  return useQuery({
    queryKey: ['material-changes', comparisonId],
    queryFn: () => api.getMaterialChanges(comparisonId!),
    enabled: !!comparisonId,
  })
}

export function useChangeRecommendations(comparisonId: string | null) {
  return useQuery({
    queryKey: ['change-recommendations', comparisonId],
    queryFn: () => api.getChangeRecommendations(comparisonId!),
    enabled: !!comparisonId,
  })
}
