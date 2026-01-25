import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { loginUser as apiLogin, logoutUser as apiLogout, getProfile, UnauthorizedError } from '../lib/api'

type Profile = { username?: string; is_admin?: boolean; [k: string]: any } | null
type AuthContextType = {
  loading: boolean
  profile: Profile
  isAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [profile, setProfile] = useState<Profile>(null)

  const login = async (username: string, password: string) => {
    try {
      const result = await apiLogin(username, password)
      if (result && result.token) {
        // Persist token client-side to ensure Authorization on all API calls
        try { window.localStorage.setItem('jarvis_token', result.token) } catch {}
        // Clear any previous redirect guard
        try { window.sessionStorage.removeItem('jarvis_auth_redirected') } catch {}
        // Redirect to app
        window.location.href = '/'
      } else {
        throw new Error('No token received')
      }
    } catch (err: any) {
      throw err
    }
  }

  const logout = async () => {
    try {
      await apiLogout()
      // clear local profile state and redirect
      setProfile(null)
      window.location.href = '/ui/login'
    } catch (err) {
      // Even if logout request fails, clear local state
      setProfile(null)
      window.location.href = '/ui/login'
    }
  }

  // Boot: load profile once
  useEffect(() => {
    let mounted = true
    async function init() {
      try {
        const p = await getProfile()
        if (!mounted) return
        setProfile(p || null)
      } catch (e) {
        // On any error, treat as unauthenticated and let RequireAuth redirect
        setProfile(null)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    init()
    return () => { mounted = false }
  }, [])

  const isAdmin = useMemo(() => !!profile?.is_admin, [profile])

  return (
    <AuthContext.Provider value={{ loading, profile, isAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return ctx
}

// Guard wrappers
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { loading, profile } = useAuth()
  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-neutral-400">Indlæser…</div>
  }
  if (!profile) {
    try { window.location.href = '/ui/login' } catch {}
    return null
  }
  return <>{children}</>
}

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { loading, profile, isAdmin } = useAuth()
  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-neutral-400">Indlæser…</div>
  }
  if (!profile) {
    try { window.location.href = '/ui/login' } catch {}
    return null
  }
  if (!isAdmin) {
    try { window.location.href = '/ui/' } catch {}
    return null
  }
  return <>{children}</>
}
