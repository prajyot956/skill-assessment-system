import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
interface ThemeValue { mode: ThemeMode; isDark: boolean; setMode: (m: ThemeMode) => void; toggle: () => void }

const ThemeContext = createContext<ThemeValue | null>(null)
const KEY = 'sas-theme'

const systemDark = () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches

function readStored(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch { return 'system' }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readStored)
  const [sysDark, setSysDark] = useState(systemDark)

  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const on = () => setSysDark(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])

  const isDark = mode === 'dark' || (mode === 'system' && sysDark)
  useEffect(() => { document.documentElement.classList.toggle('dark', isDark) }, [isDark])

  const setMode = useCallback((m: ThemeMode) => {
    setModeState(m)
    try { localStorage.setItem(KEY, m) } catch { /* storage unavailable */ }
  }, [])
  const toggle = useCallback(() => setMode(isDark ? 'light' : 'dark'), [isDark, setMode])

  const value = useMemo(() => ({ mode, isDark, setMode, toggle }), [mode, isDark, setMode, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
