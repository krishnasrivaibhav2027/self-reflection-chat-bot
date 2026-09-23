import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout } from '../api/authApi'
import { getMe } from '../api/userApi'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('access_token'))
  const [loading, setLoading] = useState(true)

  // On mount, if a token exists try to rehydrate the user object
  useEffect(() => {
    const restore = async () => {
      const stored = localStorage.getItem('access_token')
      if (!stored) {
        setLoading(false)
        return
      }
      try {
        const me = await getMe()
        setUser(me)
        setToken(stored)
      } catch {
        // Token is stale — clear everything
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        setToken(null)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    restore()
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await apiLogin(email, password)
    localStorage.setItem('access_token', data.access_token)
    setToken(data.access_token)
    // Fetch user profile immediately after login
    const me = await getMe()
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // Best-effort — clear locally regardless
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      setToken(null)
      setUser(null)
    }
  }, [])

  const value = { user, token, loading, login, logout, isAuthenticated: !!token && !!user }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
