'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '../stores/authStore'

/**
 * Decode the payload of a JWT (base64url) without verifying the signature.
 * Returns null if the token is malformed.
 */
function decodeJwtPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    // base64url -> base64
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(base64)
    return JSON.parse(json)
  } catch {
    return null
  }
}

/**
 * Check whether a JWT token has expired based on its `exp` claim.
 * Returns true if the token is expired or malformed.
 */
function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return true
  // exp is in seconds; Date.now() is in milliseconds
  return payload.exp * 1000 < Date.now()
}

/**
 * Hook that checks for a valid auth session.
 *
 * Priority:
 * 1. Zustand store (in-memory access_token)
 * 2. localStorage (legacy fallback)
 * 3. Refresh via httpOnly cookie (page reload scenario)
 *
 * Redirects to /login if no valid session can be established.
 * Returns { isReady } — true when auth check is complete.
 */
export function useAuthGuard() {
  const router = useRouter()
  const [isReady, setIsReady] = useState(false)
  const { accessToken, isAuthenticated, isLoading, initAuth } = useAuthStore()

  useEffect(() => {
    const check = async () => {
      // If store already has a valid token, we're good
      if (accessToken && !isTokenExpired(accessToken)) {
        setIsReady(true)
        return
      }

      // Fallback: check localStorage (legacy)
      const legacyToken = localStorage.getItem('access_token')
      if (legacyToken && !isTokenExpired(legacyToken)) {
        setIsReady(true)
        return
      }

      // No valid in-memory or legacy token — try refresh via httpOnly cookie
      await initAuth()

      // After initAuth, check store state
      const state = useAuthStore.getState()
      if (state.isAuthenticated && state.accessToken) {
        setIsReady(true)
      } else {
        // Clean up stale data
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        document.cookie = 'has_token=; path=/; max-age=0'
        router.replace('/login')
      }
    }

    check()
  }, [router]) // eslint-disable-line react-hooks/exhaustive-deps

  return { isReady }
}
