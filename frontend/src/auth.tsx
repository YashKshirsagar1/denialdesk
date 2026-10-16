import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { LoginResponse, SessionUser } from './types'

// sessionStorage, not localStorage: the session ends when the tab closes, which
// limits how long a token sits around in a browser that may hold PHI.
const TOKEN_KEY = 'dd_token'
const USER_KEY = 'dd_user'
const IDLE_LIMIT_MS = 30 * 60 * 1000

export function getToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function authHeaders(): Record<string, string> {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

function loadUser(): SessionUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw && getToken() ? (JSON.parse(raw) as SessionUser) : null
  } catch { return null }
}

function save(resp: LoginResponse) {
  try {
    sessionStorage.setItem(TOKEN_KEY, resp.access_token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(resp.user))
  } catch { /* storage blocked: session just won't survive a refresh */ }
}

function clear() {
  try { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY) } catch { /* ignore */ }
}

interface AuthCtx {
  user: SessionUser | null
  signIn: (resp: LoginResponse) => void
  signOut: (reason?: string) => void
  updateUser: (patch: Partial<SessionUser>) => void
  notice: string | null
  isOps: boolean
  isClinic: boolean
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(loadUser)
  const [notice, setNotice] = useState<string | null>(null)
  const timer = useRef<number>()

  const signOut = useCallback((reason?: string) => {
    clear()
    setUser(null)
    setNotice(reason ?? null)
  }, [])

  const signIn = useCallback((resp: LoginResponse) => {
    save(resp)
    setNotice(null)
    setUser(resp.user)
  }, [])

  const updateUser = useCallback((patch: Partial<SessionUser>) => {
    setUser((u) => {
      if (!u) return u
      const next = { ...u, ...patch }
      try { sessionStorage.setItem(USER_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])

  // API layer fires this on any 401 (expired / revoked token).
  useEffect(() => {
    const h = () => signOut('Your session expired. Please sign in again.')
    window.addEventListener('dd:unauthorized', h)
    return () => window.removeEventListener('dd:unauthorized', h)
  }, [signOut])

  // Auto sign-out after 30 min idle (standard for apps that show PHI).
  useEffect(() => {
    if (!user) return
    const reset = () => {
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => signOut('You were signed out after 30 minutes of inactivity.'), IDLE_LIMIT_MS)
    }
    const evts = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart']
    evts.forEach((e) => window.addEventListener(e, reset, { passive: true }))
    reset()
    return () => {
      evts.forEach((e) => window.removeEventListener(e, reset))
      window.clearTimeout(timer.current)
    }
  }, [user, signOut])

  const value = useMemo<AuthCtx>(
    () => ({
      user, signIn, signOut, updateUser, notice,
      isOps: user?.role === 'ops_admin' || user?.role === 'reviewer',
      isClinic: user?.role === 'clinic_admin' || user?.role === 'clinic_staff',
    }),
    [user, signIn, signOut, updateUser, notice],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}
