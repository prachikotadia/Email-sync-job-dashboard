import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authService } from '../services/authService'
import { FEATURES } from '../config/features'

const AuthContext = createContext(null)

const GUEST_STORAGE_KEY = 'jobpulse_guest'

const GUEST_USER = {
  id: 'guest',
  email: 'guest@local',
  role: 'guest',
}

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  // 🚨 TEMPORARY GUEST MODE – REMOVE AFTER BACKEND STABILIZES
  const [isGuest, setIsGuest] = useState(false)

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      // 🚨 TEMPORARY GUEST MODE – check guest first (sync, no backend). Only when flag is on.
      if (FEATURES.GUEST_MODE_ENABLED && sessionStorage.getItem(GUEST_STORAGE_KEY) === 'true') {
        setUser(GUEST_USER)
        setIsAuthenticated(true)
        setIsGuest(true)
        setLoading(false)
        return
      }

      // Google auth – unchanged
      if (authService.isAuthenticated()) {
        try {
          const userData = await authService.getCurrentUser()
          setUser(userData)
          setIsAuthenticated(true)
          setIsGuest(false)
        } catch (error) {
          // Token invalid, clear it
          localStorage.removeItem('token')
          setIsAuthenticated(false)
          setIsGuest(false)
        }
      }
      setLoading(false)
    }

    checkAuth()
  }, [])

  const login = useCallback(async (code) => {
    try {
      const { token, user: userData } = await authService.handleCallback(code)
      setUser(userData)
      setIsAuthenticated(true)
      setIsGuest(false)
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }, [])

  // 🚨 TEMPORARY GUEST MODE – REMOVE AFTER BACKEND STABILIZES
  const loginAsGuest = useCallback(() => {
    if (!FEATURES.GUEST_MODE_ENABLED) return
    sessionStorage.setItem(GUEST_STORAGE_KEY, 'true')
    setUser(GUEST_USER)
    setIsAuthenticated(true)
    setIsGuest(true)
  }, [])

  // 🚨 TEMPORARY GUEST MODE – REMOVE AFTER BACKEND STABILIZES
  const logoutGuest = useCallback(() => {
    sessionStorage.removeItem(GUEST_STORAGE_KEY)
    setUser(null)
    setIsAuthenticated(false)
    setIsGuest(false)
  }, [])

  const logout = useCallback(async () => {
    // Clear all frontend state
    await authService.logout()
    setUser(null)
    setIsAuthenticated(false)
    setIsGuest(false)
    
    // Force backend to delete all cached email data
    // This is handled by the logout endpoint
  }, [])

  const value = {
    isAuthenticated,
    user,
    loading,
    login,
    logout,
    // 🚨 TEMPORARY GUEST MODE
    isGuest: isGuest,
    loginAsGuest,
    logoutGuest,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
