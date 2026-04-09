/**
 * Zustand Organization Store
 *
 * Tracks the currently selected organization context.
 * When selectedOrgId is set, API calls include X-Organization-Id header.
 * When null, user operates in personal mode.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface OrgState {
  selectedOrgId: string | null;
  selectedOrgName: string | null;
  setSelectedOrg: (orgId: string | null, orgName?: string | null) => void;
  clearOrg: () => void;
}

export const useOrgStore = create<OrgState>()(
  persist(
    (set) => ({
      selectedOrgId: null,
      selectedOrgName: null,

      setSelectedOrg: (orgId, orgName = null) => {
        set({ selectedOrgId: orgId, selectedOrgName: orgName });
      },

      clearOrg: () => {
        set({ selectedOrgId: null, selectedOrgName: null });
      },
    }),
    {
      name: 'org-storage',
    }
  )
);
