import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AIPanelState {
  isOpen: boolean
  activeTab: 'chat' | 'plan'
  sessionId: string | null
  runId: string | null
  selectedDocId: string | null

  openPanel: (docId?: string) => void
  closePanel: () => void
  setActiveTab: (tab: 'chat' | 'plan') => void
  setSessionId: (id: string | null) => void
  setRunId: (id: string | null) => void
  setSelectedDocId: (id: string | null) => void
  reset: () => void
}

export const useAIPanelStore = create<AIPanelState>()(
  persist(
    (set) => ({
      isOpen: false,
      activeTab: 'chat',
      sessionId: null,
      runId: null,
      selectedDocId: null,

      openPanel: (docId) =>
        set({ isOpen: true, ...(docId ? { selectedDocId: docId } : {}) }),
      closePanel: () => set({ isOpen: false }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setSessionId: (id) => set({ sessionId: id }),
      setRunId: (id) => set({ runId: id }),
      setSelectedDocId: (id) => set({ selectedDocId: id, sessionId: null, runId: null }),
      reset: () =>
        set({ isOpen: false, activeTab: 'chat', sessionId: null, runId: null, selectedDocId: null }),
    }),
    {
      name: 'ai-panel-store',
      partialize: (state) => ({
        sessionId: state.sessionId,
        selectedDocId: state.selectedDocId,
        activeTab: state.activeTab,
      }),
    }
  )
)
