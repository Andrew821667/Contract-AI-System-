'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Hook that checks for access_token in localStorage.
 * Redirects to /login if not found.
 * Returns { isReady } — true when auth check is complete.
 */
export function useAuthGuard() {
  const router = useRouter()
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      router.replace('/login')
    } else {
      setIsReady(true)
    }
  }, [router])

  return { isReady }
}
