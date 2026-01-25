import React, { createContext, useContext, useState } from 'react'
import { loginUser as apiLogin, logoutUser as apiLogout } from '../lib/api'

type AuthContextType = {
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAdmin] = useState(false)

  const login = async (username: string, password: string) => {
    try {
      const result = await apiLogin(username, password)
      if (result && result.token) {
        // Token is already in cookie, just redirect
        window.location.href = '/ui/'
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
      window.location.href = '/ui/login'
    } catch (err) {
      // Even if logout request fails, clear local state
      window.location.href = '/ui/login'
    }
  }

  return (
    <AuthContext.Provider value={{ login, logout, isAdmin }}>
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
