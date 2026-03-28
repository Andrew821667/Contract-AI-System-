/**
 * Zustand Auth Store
 *
 * Central auth state management. Keeps access_token in memory only (NOT localStorage).
 * Refresh token is handled via httpOnly cookie (set by backend).
 *
 * On page reload, call initAuth() which hits /api/v1/auth/refresh (cookie sent automatically)
 * to obtain a fresh access_token.
 */

import { create } from 'zustand';
import type { User } from '../services/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  /** Called by api.ts after successful login / demo-activate */
  setAuth: (user: User, accessToken: string) => void;

  /** Update only the access token (after refresh) */
  setAccessToken: (token: string) => void;

  /** Update user data (e.g., after /me call) */
  setUser: (user: User) => void;

  /** Full login flow — delegates to api.ts, updates store */
  login: (username: string, password: string) => Promise<void>;

  /** Logout — clears store, calls backend, clears cookie flag */
  logout: () => Promise<void>;

  /** Refresh user profile from /me endpoint */
  refreshUser: () => Promise<void>;

  /** Bootstrap auth on page reload using httpOnly refresh cookie */
  initAuth: () => Promise<void>;

  /** Clear store state (no API call) */
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true, // starts true until initAuth completes

  setAuth: (user, accessToken) => {
    set({ user, accessToken, isAuthenticated: true, isLoading: false });
  },

  setAccessToken: (token) => {
    set({ accessToken: token });
  },

  setUser: (user) => {
    set({ user });
  },

  login: async (username, password) => {
    // Import lazily to avoid circular dependency
    const { default: api } = await import('../services/api');
    set({ isLoading: true });
    try {
      const response = await api.login({ username, password });
      set({
        user: response.user,
        accessToken: response.access_token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    const { default: api } = await import('../services/api');
    try {
      await api.logout();
    } catch {
      // ignore logout errors
    }
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    if (typeof window !== 'undefined') {
      localStorage.removeItem('user');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      document.cookie = 'has_token=; path=/; max-age=0';
    }
  },

  refreshUser: async () => {
    const { default: api } = await import('../services/api');
    try {
      const user = await api.getCurrentUser();
      set({ user });
    } catch {
      // If /me fails, user might be logged out
    }
  },

  initAuth: async () => {
    set({ isLoading: true });

    // First check: is there an in-memory token already?
    if (get().accessToken) {
      set({ isLoading: false });
      return;
    }

    // Security: do NOT recover tokens from localStorage (XSS risk).
    // Clean up any legacy localStorage tokens.
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }

    // No in-memory token — try refresh via httpOnly cookie
    try {
      const { default: api } = await import('../services/api');
      const refreshed = await api.refreshToken();
      if (refreshed) {
        await get().refreshUser();
        set({ isAuthenticated: true, isLoading: false });
      } else {
        set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
      }
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearAuth: () => {
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    if (typeof window !== 'undefined') {
      localStorage.removeItem('user');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      document.cookie = 'has_token=; path=/; max-age=0';
    }
  },
}));
