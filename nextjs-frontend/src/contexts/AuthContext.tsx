'use client'
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { authApi, tokenStore, refreshTokenStore, userStore, impersonationStore, attemptTokenRefresh } from '@/lib/api'
import type { User } from '@/types'

/** An organization the sign-in exists in, offered when there is more than one. */
export interface TenantChoice { name: string }

interface AuthContextValue {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  isHost: boolean
  isImpersonating: boolean
  login:  (usernameOrEmail: string, password: string, tenantId?: string) => Promise<{ requiresTwoFactor?: boolean; userId?: string; tenants?: TenantChoice[] }>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  impersonate: (userId: string, tenantId?: string) => Promise<void>
  endImpersonation: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser]       = useState<User | null>(null)
  const [token, setToken]     = useState<string | null>(null)
  const [isLoading, setLoading] = useState(true)
  const router = useRouter()

  const refreshUser = useCallback(async () => {
    try {
      const me = await authApi.me() as User
      setUser(me)
      userStore.set(me)
    } catch {
      tokenStore.clear()
      userStore.clear()
      setUser(null)
      setToken(null)
    }
  }, [])

  useEffect(() => {
    // Single session-expired handler — uses SPA navigation to /auth/login so we
    // don't lose React state via a hard reload.
    const handleExpired = () => {
      impersonationStore.clear()
      tokenStore.clear()
      refreshTokenStore.clear()
      userStore.clear()
      setUser(null)
      setToken(null)
      router.replace('/auth/login')
    }
    window.addEventListener('auth:session-expired', handleExpired)

    // Skip session restore entirely on public pages — no cookie or token
    // will exist there, and attempting a refresh just generates a noisy 401.
    const path = window.location.pathname
    const PUBLIC_EXACT = new Set(['/', '/home', '/docs', '/how-it-works'])
    const PUBLIC_PREFIX = ['/auth/', '/docs/', '/how-it-works/']
    const isPublic = PUBLIC_EXACT.has(path) || PUBLIC_PREFIX.some(p => path.startsWith(p))
    if (isPublic) {
      setLoading(false)
      return () => window.removeEventListener('auth:session-expired', handleExpired)
    }

    const restoreSession = async () => {
      const impersonation = impersonationStore.get()
      if (impersonation?.impersonationToken) {
        tokenStore.set(impersonation.impersonationToken)
        setToken(impersonation.impersonationToken)
        const cached = userStore.get() as User | null
        if (cached) { setUser(cached); setLoading(false); refreshUser() }
        else { refreshUser().finally(() => setLoading(false)) }
        return
      }

      const t = tokenStore.get()
      if (t) {
        setToken(t)
        const cached = userStore.get() as User | null
        if (cached) { setUser(cached); setLoading(false); refreshUser() }
        else { refreshUser().finally(() => setLoading(false)) }
        return
      }

      const newToken = await attemptTokenRefresh()
      if (newToken) {
        setToken(newToken)
        const cached = userStore.get() as User | null
        if (cached) { setUser(cached); setLoading(false); refreshUser() }
        else { refreshUser().finally(() => setLoading(false)) }
      } else {
        setLoading(false)
      }
    }

    restoreSession()

    return () => window.removeEventListener('auth:session-expired', handleExpired)
  }, [refreshUser, router])

  const login = useCallback(async (usernameOrEmail: string, password: string, tenantId?: string) => {
    const res = await authApi.login({ username_or_email: usernameOrEmail, password, tenant_name: tenantId }) as {
      access_token?: string
      user_id?: string
      requires_two_factor?: boolean
      requiresTwoFactor?: boolean
      tenants?: TenantChoice[]
    }
    if (res.requires_two_factor || res.requiresTwoFactor) {
      return { requiresTwoFactor: true, userId: res.user_id }
    }
    // The same sign-in exists in several organizations: the caller asks which one, then calls again with it
    if (res.tenants && res.tenants.length > 0) return { tenants: res.tenants }
    if (!res.access_token) throw new Error('Login failed')
    tokenStore.set(res.access_token)
    // Note: refresh token is set as HttpOnly cookie by the server — no client-side management needed
    setToken(res.access_token)
    await refreshUser()
    return {}
  }, [])

  const logout = useCallback(async () => {
    try { await authApi.logout() } catch { /* ignore */ }
    impersonationStore.clear()
    tokenStore.clear()
    refreshTokenStore.clear()
    userStore.clear()
    setToken(null)
    setUser(null)
  }, [])

  const impersonate = useCallback(async (userId: string, tenantId?: string) => {
    const currentToken = tokenStore.get()
    if (!currentToken || !user) throw new Error('Not authenticated')
    const res = await authApi.impersonate(userId, tenantId) as { access_token: string }
    impersonationStore.set(currentToken, user, res.access_token)
    tokenStore.set(res.access_token)
    setToken(res.access_token)
    await refreshUser()
    router.push('/app/dashboard')
  }, [user, refreshUser, router])

  const endImpersonation = useCallback(async () => {
    const backup = impersonationStore.get()
    if (!backup?.adminToken) return
    try { await authApi.endImpersonation() } catch { /* ignore */ }
    impersonationStore.clear()
    tokenStore.set(backup.adminToken)
    setToken(backup.adminToken)
    const adminUser = backup.adminUser as User
    setUser(adminUser)
    userStore.set(adminUser)
    await refreshUser()
    router.push(adminUser.tenantId ? '/app/admin/users' : '/app/admin/tenants')
  }, [refreshUser, router])

  const hasPermission = useCallback((p: string) => user?.permissions?.includes(p) ?? false, [user])
  const hasRole       = useCallback((r: string) => user?.roles?.includes(r) ?? false, [user])
  const isImpersonating = !!(user?.isImpersonating || impersonationStore.get())
  const isHost        = !!user && !user?.tenantId && !isImpersonating

  return (
    <AuthContext.Provider value={{
      user, token, isLoading, isAuthenticated: !!user && !!token, isHost, isImpersonating,
      login, logout, refreshUser, impersonate, endImpersonation, hasPermission, hasRole,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
