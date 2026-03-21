'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useWorkflowDefinitions() {
  return useQuery({
    queryKey: ['workflow-definitions'],
    queryFn: () => api.listWorkflowDefinitions(),
  })
}

export function useCreateWorkflowDefinition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createWorkflowDefinition>[0]) =>
      api.createWorkflowDefinition(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-definitions'] })
    },
  })
}

export function useDocumentWorkflows(documentId: string | null) {
  return useQuery({
    queryKey: ['document-workflows', documentId],
    queryFn: () => api.getDocumentWorkflows(documentId!),
    enabled: !!documentId,
  })
}

export function useExecutionTasks(executionId: string | null) {
  return useQuery({
    queryKey: ['execution-tasks', executionId],
    queryFn: () => api.getExecutionTasks(executionId!),
    enabled: !!executionId,
    refetchInterval: 5000,
  })
}

export function useMyWorkflowTasks(status: string = 'pending') {
  return useQuery({
    queryKey: ['my-workflow-tasks', status],
    queryFn: () => api.getMyWorkflowTasks(status),
    refetchInterval: 10000,
  })
}

export function useStartWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ definitionId, documentId }: { definitionId: string; documentId: string }) =>
      api.startWorkflow(definitionId, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document-workflows'] })
      queryClient.invalidateQueries({ queryKey: ['my-workflow-tasks'] })
    },
  })
}

export function useCompleteWorkflowTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, decision, comment }: { taskId: string; decision: string; comment?: string }) =>
      api.completeWorkflowTask(taskId, decision, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-workflow-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['execution-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['document-workflows'] })
    },
  })
}

export function useEscalateWorkflowTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, reason }: { taskId: string; reason?: string }) =>
      api.escalateWorkflowTask(taskId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-workflow-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['execution-tasks'] })
    },
  })
}
