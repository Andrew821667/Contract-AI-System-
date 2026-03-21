'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { useAuthGuard } from '@/hooks/useAuthGuard'
import AppLayout from '@/components/AppLayout'
import DocumentSidebar from '@/components/ai/DocumentSidebar'
import ChatMessage from '@/components/ai/ChatMessage'
import AIActionCard from '@/components/ai/AIActionCard'
import ChatInput from '@/components/ai/ChatInput'
import QuickActions from '@/components/ai/QuickActions'
import ExecutionPlan from '@/components/ai/ExecutionPlan'
import { useAIPanelStore } from '@/stores/aiPanelStore'
import { useAIMessages, useAIActions, useAIContext, useSendAIMessage, useApproveAction, useRejectAction, useCreateAISession } from '@/hooks/useAISession'

export default function AIWorkspacePageWrapper() {
  return (
    <Suspense fallback={null}>
      <AIWorkspacePage />
    </Suspense>
  )
}

function AIWorkspacePage() {
  const { isReady } = useAuthGuard()
  const searchParams = useSearchParams()
  const { sessionId, selectedDocId, setSelectedDocId, setSessionId } = useAIPanelStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [showRightPanel, setShowRightPanel] = useState(false)

  // Pick up doc from URL
  useEffect(() => {
    const docParam = searchParams.get('doc')
    if (docParam && docParam !== selectedDocId) {
      setSelectedDocId(docParam)
    }
  }, [searchParams, selectedDocId, setSelectedDocId])

  // Data hooks
  const { data: messagesData } = useAIMessages(sessionId)
  const { data: actionsData } = useAIActions(sessionId)
  const { data: context } = useAIContext(sessionId)
  const sendMessage = useSendAIMessage()
  const approveAction = useApproveAction()
  const rejectAction = useRejectAction()
  const createSession = useCreateAISession()

  const messages = messagesData?.messages || []
  const actions = actionsData?.actions || []
  const pendingActions = actions.filter((a) => a.status === 'pending')

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = (content: string) => {
    if (!sessionId) {
      // Auto-create session if none exists
      if (selectedDocId) {
        createSession.mutateAsync({ documentId: selectedDocId }).then((session) => {
          setSessionId(session.id)
          sendMessage.mutate({ sessionId: session.id, content })
        })
      }
      return
    }
    sendMessage.mutate({ sessionId, content })
  }

  if (!isReady) return null

  return (
    <AppLayout title="AI Workspace">
      <div className="h-[calc(100vh-130px)] flex gap-0 -mx-4 sm:-mx-8 -my-4 sm:-my-8">
        {/* Left column — Documents & Sessions */}
        <div className="hidden lg:flex w-[260px] flex-shrink-0 border-r border-gray-200 dark:border-dark-700 bg-white/50 dark:bg-dark-900/50">
          <div className="w-full">
            <DocumentSidebar />
          </div>
        </div>

        {/* Center column — Chat */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Context bar */}
          {context?.document && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="px-4 py-2 border-b border-gray-200 dark:border-dark-700 bg-white/80 dark:bg-dark-800/80 backdrop-blur-sm flex items-center gap-3 flex-shrink-0"
            >
              <svg className="w-4 h-4 text-primary-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                {context.document.file_name}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-dark-700 text-gray-500 dark:text-gray-400">
                {context.document.contract_type || '—'}
              </span>
              {context.document.risk_level && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                  context.document.risk_level === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                  context.document.risk_level === 'high' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' :
                  context.document.risk_level === 'medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
                  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                }`}>
                  Риск: {context.document.risk_level}
                </span>
              )}

              {/* Mobile: toggle right panel */}
              <button
                onClick={() => setShowRightPanel(!showRightPanel)}
                className="lg:hidden ml-auto p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-700 text-gray-500"
                title="План выполнения"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              </button>
            </motion.div>
          )}

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {!sessionId && !selectedDocId ? (
              /* Empty state — no doc selected */
              <div className="h-full flex flex-col items-center justify-center text-center px-8">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center mb-4 shadow-lg">
                  <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2">AI Workspace</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">
                  Выберите документ в левой панели или используйте оркестратор для запуска AI-задач
                </p>
              </div>
            ) : !sessionId && selectedDocId ? (
              /* Doc selected, no session */
              <div className="h-full flex flex-col items-center justify-center text-center px-8">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center mb-4">
                  <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">Начните диалог</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  Выберите быстрое действие или введите вопрос
                </p>
                <QuickActions onSelect={handleSend} />
              </div>
            ) : (
              /* Chat messages */
              <>
                {messages.length === 0 && (
                  <div className="mb-4">
                    <p className="text-xs text-gray-400 dark:text-gray-500 mb-3 text-center">Быстрые действия:</p>
                    <QuickActions onSelect={handleSend} />
                  </div>
                )}
                {messages.map((msg) => (
                  <ChatMessage key={msg.id} message={msg} />
                ))}
                {/* Pending actions inline */}
                {pendingActions.length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 font-medium">
                      AI предлагает действия ({pendingActions.length}):
                    </p>
                    {pendingActions.map((action) => (
                      <AIActionCard
                        key={action.id}
                        action={action}
                        onApprove={(id, comment) => approveAction.mutate({ actionId: id, comment })}
                        onReject={(id, comment) => rejectAction.mutate({ actionId: id, comment })}
                      />
                    ))}
                  </div>
                )}
                {/* Typing indicator */}
                {sendMessage.isPending && (
                  <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500 mb-4">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span>AI думает...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input area */}
          <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-gray-100 dark:border-dark-800">
            <ChatInput
              onSend={handleSend}
              disabled={sendMessage.isPending || (!sessionId && !selectedDocId)}
              placeholder={!selectedDocId ? 'Сначала выберите документ...' : undefined}
            />
          </div>
        </div>

        {/* Right column — Execution Plan */}
        <div className={`${showRightPanel ? 'fixed inset-0 z-50 bg-white dark:bg-dark-900 p-4' : 'hidden'} lg:relative lg:flex lg:z-auto lg:inset-auto lg:bg-transparent lg:p-0 w-full lg:w-[320px] flex-shrink-0 border-l border-gray-200 dark:border-dark-700 bg-white/50 dark:bg-dark-900/50`}>
          <div className="w-full flex flex-col h-full">
            {/* Mobile close button */}
            <div className="lg:hidden flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800 dark:text-gray-200">План выполнения</h2>
              <button
                onClick={() => setShowRightPanel(false)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-xl"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="px-4 py-3 border-b border-gray-200 dark:border-dark-700 hidden lg:block">
              <h2 className="text-sm font-bold text-gray-800 dark:text-gray-200">План выполнения</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <ExecutionPlan />
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
