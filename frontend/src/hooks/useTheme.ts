'use client'

import { useEffect, useState, useCallback } from 'react'

type Theme = 'light' | 'dark' | 'steel' | 'system'
type ResolvedTheme = 'light' | 'dark' | 'steel'

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme
  const root = document.documentElement
  root.classList.remove('dark', 'steel')
  if (resolved === 'dark') {
    root.classList.add('dark')
  } else if (resolved === 'steel') {
    root.classList.add('steel')
  }
}

const THEME_CYCLE: ResolvedTheme[] = ['light', 'steel', 'dark']

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>('light')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem('theme') as Theme | null
    const initial = stored || 'system'
    setThemeState(initial)
    applyTheme(initial)
    setMounted(true)

    // Listen for system theme changes
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      const current = localStorage.getItem('theme') as Theme | null
      if (!current || current === 'system') {
        applyTheme('system')
      }
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    localStorage.setItem('theme', t)
    applyTheme(t)
  }, [])

  const toggleTheme = useCallback(() => {
    const resolved: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme as ResolvedTheme
    const currentIdx = THEME_CYCLE.indexOf(resolved)
    const nextIdx = (currentIdx + 1) % THEME_CYCLE.length
    setTheme(THEME_CYCLE[nextIdx])
  }, [theme, setTheme])

  const resolvedTheme: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme as ResolvedTheme

  return { theme, setTheme, toggleTheme, resolvedTheme, mounted }
}
