'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { useAIPanelStore } from '@/stores/aiPanelStore'
import { useAIMessages, useAIActions, useSendAIMessage, useApproveAction, useRejectAction, useCreateAISession } from '@/hooks/useAISession'
import ChatMessage from './ChatMessage'
import AIActionCard from './AIActionCard'
import ChatInput from './ChatInput'
import QuickActions from './QuickActions'
import ExecutionPlan from './ExecutionPlan'

interface AIPanelProps {
  contractId: string
}

export default function AIPanel({ contractId }: AIPanelProps) {
  const router = useRouter()
  const {
    isOpen, activeTab, sessionId, setSessionId, setActiveTab,
    closePanel, setSelectedDocId,
  } = useAIPanelStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Set doc context when panel opens
  useEffect(() => {
    if (isOpen) {
      setSelectedDocId(contractId)
    }
  }, [isOpen, contractId, setSelectedDocId])

  // Data
  const { data: messagesData } = useAIMessages(sessionId)
  const { data: actionsData } = useAIActions(sessionId)
  const sendMessage = useSendAIMessage()
  const approveAction = useApproveAction()
  const rejectAction = useRejectAction()
  const createSession = useCreateAISession()

  const messages = messagesData?.messages || []
  const actions = actionsData?.actions || []
  const pendingActions = actions.filter((a) => a.status === 'pending')

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = (content: string) => {
    if (!sessionId) {
      createSession.mutateAsync({ documentId: contractId }).then((session) => {
        setSessionId(session.id)
        sendMessage.mutate({ sessionId: session.id, content })
      })
      return
    }
    sendMessage.mutate({ sessionId, content })
  }

  const handleOpenFull = () => {
    closePanel()
    router.push(`/ai?doc=${contractId}`)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closePanel}
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
          />

          {/* Panel */}
          <motion.div
            initial={{ x: 420 }}
            animate={{ x: 0 }}
            exit={{ x: 420 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed right-0 top-0 h-screen w-full sm:w-[400px] bg-white dark:bg-dark-900 shadow-2xl flex flex-col z-50 border-l border-gray-200 dark:border-dark-700"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-700">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h2 className="text-sm font-bold text-gray-800 dark:text-gray-200">AI Помощник</h2>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleOpenFull}
                  className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-lg text-gray-500 dark:text-gray-400 transition"
                  title="Открыть полностью"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                  </svg>
                </button>
                <button
                  onClick={closePanel}
                  className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-lg text-gray-500 dark:text-gray-400 transition"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-200 dark:border-dark-700">
              <button
                onClick={() => setActiveTab('chat')}
                className={`flex-1 text-xs font-medium py-2.5 transition-colors relative ${
                  activeTab === 'chat'
                    ? 'text-primary-600 dark:text-primary-400'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                Чат
                {activeTab === 'chat' && (
                  <motion.div layoutId="panelTab" className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary-500 rounded-full" />
                )}
              </button>
              <button
                onClick={() => setActiveTab('plan')}
                className={`flex-1 text-xs font-medium py-2.5 transition-colors relative ${
                  activeTab === 'plan'
                    ? 'text-primary-600 dark:text-primary-400'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                План
                {activeTab === 'plan' && (
                  <motion.div layoutId="panelTab" className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary-500 rounded-full" />
                )}
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-hidden flex flex-col">
              {activeTab === 'chat' ? (
                <>
                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto px-3 py-3">
                    {messages.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full text-center">
                        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">Быстрые действия:</p>
                        <QuickActions onSelect={handleSend} compact />
                      </div>
                    ) : (
                      <>
                        {messages.map((msg) => (
                          <ChatMessage key={msg.id} message={msg} compact />
                        ))}
                        {pendingActions.map((action) => (
                          <AIActionCard
                            key={action.id}
                            action={action}
                            onApprove={(id, c) => approveAction.mutate({ actionId: id, comment: c })}
                            onReject={(id, c) => rejectAction.mutate({ actionId: id, comment: c })}
                            compact
                          />
                        ))}
                        {sendMessage.isPending && (
                          <div className="flex items-center gap-2 text-xs text-gray-400 mb-2">
                            <div className="flex gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                            AI думает...
                          </div>
                        )}
                        <div ref={messagesEndRef} />
                      </>
                    )}
                  </div>

                  {/* Input */}
                  <div className="flex-shrink-0 px-3 pb-3 pt-2 border-t border-gray-100 dark:border-dark-800">
                    <ChatInput onSend={handleSend} disabled={sendMessage.isPending} compact />
                  </div>
                </>
              ) : (
                /* Plan tab */
                <div className="flex-1 overflow-y-auto p-4">
                  <ExecutionPlan compact />
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
