import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, resetCsrf, setUnauthorizedHandler } from '../services/api'
import type { User } from '../types'

interface AuthValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string, remember: boolean) => Promise<void>
  register: (b: { full_name: string; email: string; password: string; confirm_password: string }) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    api.auth.me()
      .then((u) => alive && setUser(u))
      .catch((e) => { if (!(e instanceof ApiError && e.status === 401)) console.error(e) })
      .finally(() => alive && setLoading(false))
    // If the server says the session ended mid-use, drop back to the sign-in screen.
    setUnauthorizedHandler(() => setUser(null))
    return () => { alive = false; setUnauthorizedHandler(null) }
  }, [])

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    setUser(await api.auth.login({ email, password, remember }))
  }, [])
  const register = useCallback(async (b: Parameters<typeof api.auth.register>[0]) => {
    setUser(await api.auth.register(b))
  }, [])
  const logout = useCallback(async () => {
    try { await api.auth.logout() } finally { resetCsrf(); setUser(null) }
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
