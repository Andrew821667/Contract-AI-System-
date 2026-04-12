'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useRagStats() {
  return useQuery({
    queryKey: ['rag-stats'],
    queryFn: () => api.getRagStats(),
  })
}

export function useRagDocuments(collection: string) {
  return useQuery({
    queryKey: ['rag-documents', collection],
    queryFn: () => api.listRagDocuments(collection),
  })
}

export function useUploadRagDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, collection, docType }: { file: File; collection: string; docType?: string }) =>
      api.uploadRagDocument(file, collection, docType),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['rag-documents', variables.collection] })
      queryClient.invalidateQueries({ queryKey: ['rag-stats'] })
    },
  })
}

export function useDeleteRagDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, collection }: { docId: string; collection: string }) =>
      api.deleteRagDocument(docId, collection),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['rag-documents', variables.collection] })
      queryClient.invalidateQueries({ queryKey: ['rag-stats'] })
    },
  })
}
