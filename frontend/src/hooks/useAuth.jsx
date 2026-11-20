import { useState, useEffect, createContext, useContext } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // On mount, check if user is authenticated via cookie
    authAPI.me()
      .then(r => setUser(r.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const { data } = await authAPI.login({ username, password })
    // Tokens are set in httpOnly cookies by backend
    setUser(data.user)
    return data.user
  }

  const googleLogin = async (credential) => {
    const { data } = await authAPI.googleLogin(credential)
    setUser(data.user)
    return data.user
  }

  const register = async (payload) => {
    const { data } = await authAPI.register(payload)
    // Auto-login after registration (backend sets cookies)
    const { data: loginData } = await authAPI.login({
      username: payload.username,
      password: payload.password,
    })
    setUser(loginData.user)
    return data
  }

  const logout = async () => {
    try {
      await authAPI.logout()
    } catch (e) {
      // Ignore logout errors, still clear user state
      console.warn('Logout API error:', e)
    }
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, googleLogin, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)