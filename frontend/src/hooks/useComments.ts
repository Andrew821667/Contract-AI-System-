'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useComments(documentId: string | null, anchorType?: string) {
  return useQuery({
    queryKey: ['comments', documentId, anchorType],
    queryFn: () => api.listComments(documentId!, { anchor_type: anchorType }),
    enabled: !!documentId,
  })
}

export function useCreateComment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId, ...data }: { documentId: string; content: string; anchor_type?: string; anchor_id?: string; parent_comment_id?: string }) =>
      api.createComment(documentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments'] })
    },
  })
}

export function useReplyToComment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ commentId, content }: { commentId: string; content: string }) =>
      api.replyToComment(commentId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments'] })
    },
  })
}

export function useResolveComment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (commentId: string) => api.resolveComment(commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments'] })
    },
  })
}
