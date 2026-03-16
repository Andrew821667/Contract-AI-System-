'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

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
 * Hook that checks for a valid (non-expired) access_token in localStorage.
 * Redirects to /login if not found or expired.
 * Returns { isReady } — true when auth check is complete.
 */
export function useAuthGuard() {
  const router = useRouter()
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('access_token')

    if (!token || isTokenExpired(token)) {
      // Clean up stale data
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      document.cookie = 'has_token=; path=/; max-age=0'
      router.replace('/login')
    } else {
      setIsReady(true)
    }
  }, [router])

  return { isReady }
}
