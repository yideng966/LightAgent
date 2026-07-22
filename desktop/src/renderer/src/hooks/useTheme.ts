import { useState, useEffect, useCallback } from 'react'

export type ThemePref = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'lightagent_theme'
const LEGACY_STORAGE_KEY = 'cow_theme'

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStored(): ThemePref {
  let saved = localStorage.getItem(STORAGE_KEY)
  if (!saved) {
    saved = localStorage.getItem(LEGACY_STORAGE_KEY)
    if (saved) {
      localStorage.setItem(STORAGE_KEY, saved)
      localStorage.removeItem(LEGACY_STORAGE_KEY)
    }
  }
  if (saved === 'dark' || saved === 'light' || saved === 'system') return saved
  // First run: follow the OS appearance rather than forcing a fixed theme.
  return 'system'
}

function applyTheme(resolved: ResolvedTheme) {
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(readStored)
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    readStored() === 'system' ? getSystemTheme() : (readStored() as ResolvedTheme)
  )

  useEffect(() => {
    const next: ResolvedTheme = pref === 'system' ? getSystemTheme() : pref
    setResolved(next)
    applyTheme(next)
    localStorage.setItem(STORAGE_KEY, pref)
  }, [pref])

  // Follow system changes only when preference is "system"
  useEffect(() => {
    if (pref !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      const next = getSystemTheme()
      setResolved(next)
      applyTheme(next)
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [pref])

  const toggleTheme = useCallback(() => {
    setPref(resolved === 'dark' ? 'light' : 'dark')
  }, [resolved])

  const setTheme = useCallback((next: ThemePref) => setPref(next), [])

  return { theme: resolved, pref, toggleTheme, setTheme }
}
