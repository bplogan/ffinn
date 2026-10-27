import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import Cookies from 'js-cookie'
import type {
  ChatAttachmentSummary, ChatConversation, ChatMessage, ChatStreamEvent,
  CloudSetupProgress, ExternalSsoProvider, SsoConfiguration, SsoProvider,
} from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const USER_KEY          = 'ffinn_user'
const REFRESH_TOKEN_KEY = 'ffinn_refresh'
const IMPERSONATION_KEY = 'ffinn_impersonation'

export interface ImpersonationBackup {
  adminToken: string
  adminUser: unknown
  impersonationToken: string
}

export const impersonationStore = {
  get: (): ImpersonationBackup | null => {
    try {
      const s = typeof window !== 'undefined' ? sessionStorage.getItem(IMPERSONATION_KEY) : null
      return s ? JSON.parse(s) as ImpersonationBackup : null
    } catch { return null }
  },
  set: (adminToken: string, adminUser: unknown, impersonationToken: string) => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(IMPERSONATION_KEY, JSON.stringify({ adminToken, adminUser, impersonationToken }))
    }
  },
  clear: () => {
    if (typeof window !== 'undefined') sessionStorage.removeItem(IMPERSONATION_KEY)
  },
}

// ── Token stores ───────────────────────────────────────────────
// Access token: memory only — cleared on page reload, never touches localStorage.
// This prevents XSS exfiltration of the JWT via localStorage or accessible cookies.
let _accessToken: string | null = null

export const tokenStore = {
  get:   ()            => _accessToken,
  set:   (t: string)   => { _accessToken = t },
  clear: ()            => { _accessToken = null },
}

// Refresh token: now set as HttpOnly by the server — invisible and inaccessible to
// client JavaScript. The browser sends it automatically on requests to /api/auth/refresh.
// `set` is a no-op; `clear` removes any legacy JS-readable cookie from earlier versions.
export const refreshTokenStore = {
  get:   (): null => null,  // httpOnly — cannot be read from JS
  set:   (_t: string) => { /* no-op: server sets HttpOnly Set-Cookie */ },
  clear: () => Cookies.remove(REFRESH_TOKEN_KEY),  // clean up legacy plaintext cookie
}

export const userStore = {
  get: () => { try { const s = typeof window !== 'undefined' ? localStorage.getItem(USER_KEY) : null; return s ? JSON.parse(s) : null } catch { return null } },
  set: (u: unknown) => { if (typeof window !== 'undefined') localStorage.setItem(USER_KEY, JSON.stringify(u)) },
  clear: () => { if (typeof window !== 'undefined') localStorage.removeItem(USER_KEY) },
}

// ── Axios instance ─────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
  withCredentials: true,   // Send httpOnly cookies (e.g. refresh token) on all requests
})

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const token = tokenStore.get()
  if (token && cfg.headers) cfg.headers['Authorization'] = `Bearer ${token}`
  return cfg
})

// ── Token refresh ───────────────────────────────────────────────
// Single in-flight refresh prevents concurrent 401s from spawning multiple refresh calls.
let _refreshPromise: Promise<string | null> | null = null

export async function attemptTokenRefresh(): Promise<string | null> {
  try {
    // No body needed — the browser automatically sends the httpOnly ffinn_refresh cookie.
    // Use a bare axios instance with withCredentials so the cookie is included.
    const r = await axios.post<{ access_token: string; refresh_token?: string }>(
      `${API_BASE}/api/auth/refresh`,
      {},   // empty body — refresh token comes from the HttpOnly cookie
      { withCredentials: true },
    )
    tokenStore.set(r.data.access_token)
    return r.data.access_token
  } catch {
    tokenStore.clear()
    refreshTokenStore.clear()   // remove legacy JS-visible cookie if present
    userStore.clear()
    return null
  }
}

api.interceptors.response.use(
  r => r,
  async (err: AxiosError) => {
    const req = err.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const AUTH_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/refresh', '/api/2fa/verify-login']
    if (AUTH_PATHS.some(p => req.url?.includes(p))) return Promise.reject(err)
    if (err.response?.status === 401 && req && !req._retry) {
      req._retry = true
      // Coalesce concurrent 401s into a single refresh attempt
      if (!_refreshPromise) {
        _refreshPromise = attemptTokenRefresh().finally(() => { _refreshPromise = null })
      }
      const newToken = await _refreshPromise
      if (newToken) {
        if (req.headers) req.headers['Authorization'] = `Bearer ${newToken}`
        return api(req)
      }
      // Refresh failed — notify the app to show login; avoid hard-nav where possible
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:session-expired'))
      }
    }
    return Promise.reject(err)
  },
)

// ── Typed helpers ──────────────────────────────────────────────
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const r = await api.get<T>(url, { params })
  return r.data
}
export async function post<T>(url: string, data?: unknown): Promise<T> {
  const r = await api.post<T>(url, data)
  return r.data
}
export async function put<T>(url: string, data?: unknown): Promise<T> {
  const r = await api.put<T>(url, data)
  return r.data
}
export async function patch<T>(url: string, data?: unknown): Promise<T> {
  const r = await api.patch<T>(url, data)
  return r.data
}
export async function del<T>(url: string): Promise<T> {
  const r = await api.delete<T>(url)
  return r.data
}
export async function postForm<T>(url: string, data: FormData): Promise<T> {
  const r = await api.post<T>(url, data, { headers: { 'Content-Type': 'multipart/form-data' } })
  return r.data
}

// ── API surface ────────────────────────────────────────────────
export const authApi = {
  login:              (d: unknown) => post('/api/auth/login', d),
  register:           (d: unknown) => post('/api/auth/register', d),
  refreshToken:       (d: unknown) => post('/api/auth/refresh', d),
  forgotPassword:     (d: unknown) => post('/api/auth/forgot-password', d),
  resetPassword:      (d: unknown) => post('/api/auth/reset-password', d),
  confirmEmail:       (d: unknown) => post('/api/auth/confirm-email', d),
  me:                 ()           => get('/api/auth/me'),
  logout:             ()           => post('/api/auth/logout'),
  impersonate:        (userId: string, tenantId?: string) =>
    post('/api/auth/impersonate', { user_id: userId, ...(tenantId ? { tenant_id: tenantId } : {}) }),
  endImpersonation:   ()           => post('/api/auth/end-impersonation'),
  changePassword:     (d: unknown) => post('/api/auth/change-password', d),
  profile:            ()           => get('/api/auth/profile'),
  updateProfile:      (d: unknown) => put('/api/auth/profile', d),
  selectTenant:       (d: unknown) => post('/api/auth/select-tenant', d),
  ssoLogin:           (configId: string, returnUrl?: string) =>
    `${API_BASE}/api/sso/login/${configId}${returnUrl ? `?returnUrl=${encodeURIComponent(returnUrl)}` : ''}`,
  getTenantSsoProviders: (tenantName: string) => get<{ tenant_name: string; providers: SsoProvider[] }>(`/api/sso/tenant/${encodeURIComponent(tenantName)}`),
  getExternalProviders: (tenantName: string) => get<ExternalSsoProvider[]>(`/api/auth/external-providers`, { tenant_name: tenantName }),
  getTwoFactorStatus: ()           => get('/api/2fa/status'),
  enableTwoFactor:    (d: unknown) => post('/api/2fa/verify', d),
  disableTwoFactor:   (d: unknown) => post('/api/2fa/disable', d),
  verifyTwoFactor:    (d: unknown) => post('/api/2fa/verify-login', d),
  generateTwoFactor:  ()           => post('/api/2fa/setup'),
  ssoExchange:        (code: string) => post('/api/auth/sso/exchange', { code }),
}

export const usersApi = {
  list:              (p?: unknown) => get('/api/users', p as Record<string, unknown>),
  get:               (id: string)  => get(`/api/users/${id}`),
  create:            (d: unknown)  => post('/api/users', d),
  update:            (id: string, d: unknown) => put(`/api/users/${id}`, d),  // admin only
  updateMe:          (d: unknown)  => put('/api/users/me', d),                // self-service
  delete:            (id: string)  => del(`/api/users/${id}`),
  getRoles:          (id: string)  => get(`/api/users/${id}/roles`),
  setRoles:          (id: string, d: unknown) => put(`/api/users/${id}/roles`, d),
  getPermissions:    (id: string)  => get(`/api/permissions/user/${id}`),
  setPermissions:    (id: string, d: unknown) => put(`/api/permissions/user/${id}`, d),
  activate:          (id: string)  => post(`/api/users/${id}/activate`),
  deactivate:        (id: string)  => post(`/api/users/${id}/lock`),
  unlock:            (id: string)  => post(`/api/users/${id}/unlock`),
  impersonate:       (id: string, tenantId?: string) => authApi.impersonate(id, tenantId),
  uploadMyAvatar:    (fd: FormData) => postForm('/api/users/me/avatar', fd),
  uploadAvatar:      (id: string, fd: FormData) => postForm(`/api/users/${id}/avatar`, fd),  // kept for compatibility
}

export const rolesApi = {
  list:           ()              => get('/api/roles'),
  get:            (id: string)    => get(`/api/roles/${id}`),
  create:         (d: unknown)    => post('/api/roles', d),
  update:         (id: string, d: unknown) => put(`/api/roles/${id}`, d),
  delete:         (id: string)    => del(`/api/roles/${id}`),
  getPermissions: (id: string)    => get<string[]>(`/api/roles/${id}/permissions`),
  setPermissions: (id: string, names: string[]) => put(`/api/permissions/role/${id}`, { permissions: names }),
}

export const tenantsApi = {
  list:       (p?: unknown) => get('/api/tenants', p as Record<string, unknown>),
  get:        (id: string)  => get(`/api/tenants/${id}`),
  create:     (d: unknown)  => post('/api/tenants', d),
  update:     (id: string, d: unknown) => put(`/api/tenants/${id}`, d),
  delete:     (id: string)  => del(`/api/tenants/${id}`),
  activate:   (id: string)  => put(`/api/tenants/${id}/status?is_active=true`),
  deactivate: (id: string)  => put(`/api/tenants/${id}/status?is_active=false`),
  features:   (id: string)  => get(`/api/tenants/${id}/features`),
  setFeatures: (id: string, d: unknown) => put(`/api/tenants/${id}/features`, d),
  users:      (id: string, p?: Record<string, unknown>) => get(`/api/tenants/${id}/users`, p),
}

export const settingsApi = {
  getAll:      ()                       => get('/api/settings'),
  getPublic:   ()                       => get<{ key: string; value: string | null }[]>('/api/settings/public'),
  get:         (key: string)            => get(`/api/settings/${key}`),
  update:      (d: unknown)             => put('/api/settings', d),
  updateBatch: (d: unknown)             => put('/api/settings', d),
  testEmail:   (to: string)             => post('/api/settings/test-email', { to }),
}

export const auditLogsApi = {
  list: (p?: unknown) => get('/api/audit-logs', p as Record<string, unknown>),
  get:  (id: string)  => get(`/api/audit-logs/${id}`),
}

export const subscriptionPlansApi = {
  list:    ()                       => get('/api/subscription-plans'),
  listAll: ()                       => get('/api/subscription-plans/all'),
  get:     (id: string)             => get(`/api/subscription-plans/${id}`),
  create:  (d: unknown)             => post('/api/subscription-plans', d),
  update:  (id: string, d: unknown) => put(`/api/subscription-plans/${id}`, d),
  delete:  (id: string)             => del(`/api/subscription-plans/${id}`),
}

export const subscriptionApi = {
  getCurrent:     ()           => get('/api/subscriptions/current'),
  subscribe:      (d: unknown) => post('/api/subscriptions/checkout', d),
  cancel:         ()           => post('/api/subscriptions/cancel'),
  confirmPaypal:  (subscriptionId: string) => post(`/api/subscriptions/paypal/confirm?subscription_id=${encodeURIComponent(subscriptionId)}`),
  getBillingInfo: ()           => get('/api/subscriptions/billing-history'),
  getInvoices:    ()           => get('/api/subscriptions/invoices'),
  getPaymentMethods: ()        => get('/api/subscriptions/payment-methods'),
  createCheckout: (d: unknown) => post('/api/subscriptions/checkout', d),
  createPortal:   (returnUrl: string) => post(`/api/subscriptions/portal?return_url=${encodeURIComponent(returnUrl)}`),
}

export const aiAgentsApi = {
  list:       (p?: unknown) => get('/api/aiagent/configurations', p as Record<string, unknown>),
  get:        (id: string)  => get(`/api/aiagent/configurations/${id}`),
  create:     (d: unknown)  => post('/api/aiagent/configurations', d),
  update:     (id: string, d: unknown) => put(`/api/aiagent/configurations/${id}`, d),
  delete:     (id: string)  => del(`/api/aiagent/configurations/${id}`),
  verify:     (id: string)  => post(`/api/aiagent/configurations/${id}/verify`, {}),
  getHistory: (id: string)  => get(`/api/aiagent/configurations/${id}/history`),
  setupRepository: (id: string, d?: { api_base_url?: string; branch?: string }) =>
    post<{ success: boolean; steps?: { name: string; success: boolean; detail: string }[] }>(
      `/api/aiagent/configurations/${id}/setup-repository`,
      d ?? {},
    ),
  repositorySetupStatus: (id: string) =>
    get(`/api/aiagent/configurations/${id}/repository-setup-status`),
  wsTicket: () => post<{ ticket: string; expires_in: number }>('/api/aiagent/ws-ticket', {}),
}

/** Chat with assistant agents. Replies stream over server-sent events. */
export const aiChatApi = {
  listConversations: (agentId: string) =>
    get<ChatConversation[]>(`/api/aiagent/agents/${agentId}/conversations`),
  createConversation: (agentId: string) =>
    post<ChatConversation>(`/api/aiagent/agents/${agentId}/conversations`, {}),
  getConversation: (id: string) =>
    get<ChatConversation & { messages: ChatMessage[] }>(`/api/aiagent/conversations/${id}`),
  renameConversation: (id: string, title: string) =>
    patch<ChatConversation>(`/api/aiagent/conversations/${id}`, { title }),
  deleteConversation: (id: string) => del(`/api/aiagent/conversations/${id}`),
  uploadAttachment: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return postForm<ChatAttachmentSummary>('/api/aiagent/attachments', fd)
  },
  attachmentUrl: (id: string) => `${API_BASE}/api/aiagent/attachments/${id}`,
  /**
   * Send a message and consume the streamed reply. Uses fetch (axios cannot stream)
   * with the same bearer token the axios instance uses.
   */
  sendMessage: async (
    conversationId: string,
    body: { content: string; attachment_ids: string[] },
    onEvent: (e: ChatStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    let token = tokenStore.get()
    const doFetch = (t: string | null) => fetch(`${API_BASE}/api/aiagent/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(t ? { Authorization: `Bearer ${t}` } : {}) },
      body: JSON.stringify(body),
      credentials: 'include',
      signal,
    })
    let res = await doFetch(token)
    if (res.status === 401) {
      token = await attemptTokenRefresh()
      if (token) res = await doFetch(token)
    }
    if (!res.ok || !res.body) {
      let detail = `Request failed (${res.status})`
      try { detail = (await res.json()).detail || detail } catch { /* not json */ }
      throw new Error(detail)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (line.startsWith('data: ')) {
            try { onEvent(JSON.parse(line.slice(6)) as ChatStreamEvent) } catch { /* skip bad frame */ }
          }
        }
      }
    }
  },
}

export const aiPromptApi = {
  optimize: (prompt: string) => post('/api/aiagent/optimize-prompt', { prompt }),
}

export interface ProviderProbe {
  provider_name: string
  api_key?: string
  provider_id?: string
  endpoint?: string
  model_name?: string
}

export const aiProvidersApi = {
  list:           ()                       => get('/api/aiagent/providers'),
  get:            (id: string)             => get(`/api/aiagent/providers/${id}`),
  create:         (d: unknown)             => post('/api/aiagent/providers', d),
  update:         (id: string, d: unknown) => put(`/api/aiagent/providers/${id}`, d),
  delete:         (id: string)             => del(`/api/aiagent/providers/${id}`),
  testConnection: (id: string)             => post(`/api/aiagent/providers/${id}/test`, {}),
  /** Live model list for a key that may not be saved yet. Blank key + provider_id reuses the stored key. */
  listModels: (d: ProviderProbe) =>
    post<{ models: string[]; deployments: Array<{ deployment_name: string; model: string }>; error: string | null }>(
      '/api/aiagent/providers/models',
      d,
    ),
  /** Send a tiny real request with unsaved credentials. */
  testCredentials: (d: ProviderProbe) =>
    post<{ success: boolean; message: string }>('/api/aiagent/providers/test', d),
  listAzureDeployments: (d: { endpoint: string; api_key?: string; provider_id?: string }) =>
    post<{ deployments: Array<{ deployment_name: string; model: string }> }>(
      '/api/aiagent/providers/azure/deployments',
      d,
    ),
}

export const aiSourceControlApi = {
  get:  ()           => get('/api/aiagent/source-control-config'),
  save: (d: unknown) => put('/api/aiagent/source-control-config', d),
}

export const aiHistoryApi = {
  list: (p?: unknown) => get('/api/aiagent/generations', p as Record<string, unknown>),
  get:  (id: string)  => get(`/api/aiagent/generations/${id}`),
}

export const aiGenerationsApi = {
  list:          (p?: unknown)              => get('/api/aiagent/generations', p as Record<string, unknown>),
  get:           (id: string)               => get(`/api/aiagent/generations/${id}`),
  create:        (d: unknown)               => post('/api/aiagent/generations', d),
  process:       (id: string)               => post(`/api/aiagent/generations/${id}/process`, {}),
  progress:      (id: string)               => get(`/api/aiagent/generations/${id}/progress`),
  release:       (id: string)               => post(`/api/aiagent/generations/${id}/release`, {}),
  revert:        (id: string)               => post(`/api/aiagent/generations/${id}/revert`, {}),
  cancel:        (id: string)               => post(`/api/aiagent/generations/${id}/cancel`, {}),
  delete:        (id: string)               => del(`/api/aiagent/generations/${id}`),
  deployStaging: (id: string)               => post(`/api/aiagent/generations/${id}/deploy-staging`, {}),
  requestChanges:(id: string, d: unknown)   => post(`/api/aiagent/generations/${id}/request-changes`, d),
  scheduleRelease:(id: string, d: unknown)  => post(`/api/aiagent/generations/${id}/schedule-release`, d),
}

export const customDomainsApi = {
  list:   ()                       => get('/api/aiagent/domains'),
  create: (d: unknown)             => post('/api/aiagent/domains', d),
  /** alias for create */
  add:    (d: unknown)             => post('/api/aiagent/domains', d),
  delete: (id: string)             => del(`/api/aiagent/domains/${id}`),
  verify: (id: string)             => post(`/api/aiagent/domains/${id}/verify`, {}),
  activate: (id: string)           => post(`/api/aiagent/domains/${id}/activate`, {}),
}

export const teamInvitationsApi = {
  list:   ()           => get('/api/team-invitations'),
  invite: (d: unknown) => post('/api/team-invitations', d),
  resend: (id: string) => post(`/api/team-invitations/${id}/resend`, {}),
  revoke: (id: string) => del(`/api/team-invitations/${id}`),
  accept: (token: string) => post('/api/team-invitations/accept', { token }),
}

export const ssoApi = {
  list:   ()                       => get<SsoConfiguration[]>('/api/sso'),
  get:    (id: string)             => get<SsoConfiguration>(`/api/sso/${id}`),
  create: (d: unknown)             => post('/api/sso', d),
  update: (id: string, d: unknown) => put(`/api/sso/${id}`, d),
  delete: (id: string)             => del(`/api/sso/${id}`),
  test:   (id: string)             => get<{ test_url: string }>(`/api/sso/${id}/test`),
  getSpMetadataUrl: (id: string)   => `${API_BASE}/api/sso/sp/${id}`,
  getTenantProviders: (tenantName: string) => get<{ tenant_name: string; providers: SsoProvider[] }>(`/api/sso/tenant/${encodeURIComponent(tenantName)}`),
}

export const notificationsApi = {
  getConfig:    ()                  => get('/api/notifications/config'),
  updateConfig: (d: unknown)        => put('/api/notifications/config', d),
  testSms:      (d: unknown)        => post('/api/notifications/test-sms', d),
  testPush:     (d: unknown)        => post('/api/notifications/test-push', d),
}

export const dashboardApi = {
  stats:        () => get('/api/dashboard/stats'),
  activity:     () => get('/api/dashboard/activity'),
  systemInfo:   () => get('/api/monitoring/system/info'),
}

export const featureFlagsApi = {
  list:   ()                       => get('/api/feature-flags'),
  create: (d: unknown)             => post('/api/feature-flags', d),
  update: (name: string, d: unknown) => put(`/api/feature-flags/${name}`, d),
}

export const permissionsApi = {
  getAll: () => get('/api/permissions'),
}

export const onboardingApi = {
  getSteps:     ()           => get('/api/onboarding/steps'),
  completeStep: (key: string) => post(`/api/onboarding/steps/${key}/complete`),
}

export const editionsApi = {
  list:            ()                       => get('/api/editions'),
  listPublic:      ()                       => get('/api/editions/public'),
  forSelect:       ()                       => get('/api/editions/for-select'),
  get:             (id: string)             => get(`/api/editions/${id}`),
  create:          (d: unknown)             => post('/api/editions', d),
  update:          (id: string, d: unknown) => put(`/api/editions/${id}`, d),
  delete:          (id: string)             => del(`/api/editions/${id}`),
  tenantCount:     (id: string)             => get(`/api/editions/${id}/tenant-count`),
  moveTenants:     (d: unknown)             => post('/api/editions/move-tenants', d),
  // Feature management
  listFeatures:    (id: string)             => get(`/api/editions/${id}/features`),
  addFeature:      (id: string, d: unknown) => post(`/api/editions/${id}/features`, d),
  updateFeature:   (id: string, fid: string, d: unknown) => put(`/api/editions/${id}/features/${fid}`, d),
  deleteFeature:   (id: string, fid: string) => del(`/api/editions/${id}/features/${fid}`),
  replaceFeatures: (id: string, d: unknown) => put(`/api/editions/${id}/features/replace`, d),
}

export const paywallApi = {
  getConfiguration: ()           => get('/api/paywall/configuration'),
  updateConfiguration: (d: unknown) => put('/api/paywall/configuration', d),
  getEditions:      ()           => get('/api/paywall/editions'),
}

export const cloudSetupApi = {
  start:              () => post<CloudSetupProgress>('/api/cloudsetup/start'),
  progress:           () => get<CloudSetupProgress>('/api/cloudsetup/progress'),
  updateStep:         (step: number, data: Record<string, unknown>) => put<CloudSetupProgress>(`/api/cloudsetup/step/${step}`, { data }),
  cloudAuthenticate:  (d: { provider: string; credentials: Record<string, unknown> }) => post<CloudSetupProgress>('/api/cloudsetup/cloud/authenticate', d),
  cloudProvision:     (d: { region: string; resource_group?: string; environment_name?: string; extra?: Record<string, string> }) => post<CloudSetupProgress>('/api/cloudsetup/cloud/provision', d),
  cloudProvisionStatus: () => get<{ job_id?: string; status: string; provisioned: boolean }>('/api/cloudsetup/cloud/provision/status'),
  saveAppSettings:    (settings: Record<string, string>) => post<CloudSetupProgress>('/api/cloudsetup/cloud/appsettings', { settings }),
  githubAuthenticate: (d: { token: string; installation_id?: number }) => post<CloudSetupProgress>('/api/cloudsetup/github/authenticate', d),
  githubSetup:        (d: { owner: string; repository: string; branch?: string; create_workflows?: boolean }) => post<CloudSetupProgress>('/api/cloudsetup/github/setup', d),
  githubStatus:       () => get<{ authenticated: boolean; configured: boolean; owner?: string; repository?: string }>('/api/cloudsetup/github/status'),
  complete:           () => post<CloudSetupProgress>('/api/cloudsetup/complete'),
  reset:              () => del('/api/cloudsetup/reset'),
}

export const fileApi = {
  upload: (f: File) => { const fd = new FormData(); fd.append('file', f); return postForm('/api/files/upload', fd) },
  delete: (id: string) => del(`/api/files/${id}`),
}

export default api
