/**
 * Tests for AI Agent API surface (aiAgentsApi, aiGenerationsApi, aiProvidersApi, etc.)
 * Verifies that each method calls the correct URL and HTTP method by mocking axios.
 */

// jest.mock is hoisted to the top of the file by ts-jest/babel, which means
// no outer-scope variables can be referenced inside the factory. To work around
// this we embed the mock functions directly in the factory and retrieve them
// afterwards using jest.mocked() on the imported module.
jest.mock('axios', () => {
  const mockInstance = {
    get: jest.fn().mockResolvedValue({ data: {} }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    put: jest.fn().mockResolvedValue({ data: {} }),
    delete: jest.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  }
  return {
    create: jest.fn(() => mockInstance),
    default: {},
    // Expose the mock instance so tests can retrieve it.
    __mockInstance: mockInstance,
  }
})

jest.mock('js-cookie', () => ({
  get: jest.fn(() => null),
  set: jest.fn(),
  remove: jest.fn(),
}))

import axios from 'axios'
import {
  aiAgentsApi,
  aiGenerationsApi,
  aiProvidersApi,
  aiChatApi,
  aiHistoryApi,
  customDomainsApi,
  authApi,
  dashboardApi,
} from '@/lib/api'

// Retrieve the shared mock axios instance embedded in the jest.mock factory.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockInstance = (axios as any).__mockInstance as {
  get: jest.Mock
  post: jest.Mock
  put: jest.Mock
  delete: jest.Mock
}
const mockGet = mockInstance.get
const mockPost = mockInstance.post
const mockPut = mockInstance.put
const mockDelete = mockInstance.delete

// ── Helpers ────────────────────────────────────────────────────────────────

function clearMocks() {
  mockGet.mockClear()
  mockPost.mockClear()
  mockPut.mockClear()
  mockDelete.mockClear()
}

// ═══════════════════════════════════════════════════════════════════════
// aiAgentsApi (configurations)
// ═══════════════════════════════════════════════════════════════════════

describe('aiAgentsApi', () => {
  beforeEach(clearMocks)

  it('list() calls GET /api/aiagent/configurations', async () => {
    await aiAgentsApi.list()
    expect(mockGet).toHaveBeenCalledWith(
      '/api/aiagent/configurations',
      expect.objectContaining({ params: undefined })
    )
  })

  it('get(id) calls GET /api/aiagent/configurations/:id', async () => {
    await aiAgentsApi.get('config-123')
    expect(mockGet).toHaveBeenCalledWith(
      '/api/aiagent/configurations/config-123',
      expect.anything()
    )
  })

  it('create(data) calls POST /api/aiagent/configurations', async () => {
    const payload = { name: 'My Config', ai_provider: 'openai' }
    await aiAgentsApi.create(payload)
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/configurations', payload)
  })

  it('update(id, data) calls PUT /api/aiagent/configurations/:id', async () => {
    const payload = { ai_model: 'gpt-4-turbo' }
    await aiAgentsApi.update('config-123', payload)
    expect(mockPut).toHaveBeenCalledWith('/api/aiagent/configurations/config-123', payload)
  })

  it('delete(id) calls DELETE /api/aiagent/configurations/:id', async () => {
    await aiAgentsApi.delete('config-123')
    expect(mockDelete).toHaveBeenCalledWith('/api/aiagent/configurations/config-123')
  })

  it('verify(id) calls POST /api/aiagent/configurations/:id/verify', async () => {
    await aiAgentsApi.verify('config-123')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/configurations/config-123/verify', {})
  })

  it('setupRepository(id, data) calls POST /api/aiagent/configurations/:id/setup-repository', async () => {
    const payload = { branch: 'main' }
    await aiAgentsApi.setupRepository('config-123', payload)
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/configurations/config-123/setup-repository', payload)
  })

  it('getHistory(id) calls GET /api/aiagent/configurations/:id/history', async () => {
    await aiAgentsApi.getHistory('config-123')
    expect(mockGet).toHaveBeenCalledWith(
      '/api/aiagent/configurations/config-123/history',
      expect.anything()
    )
  })
})

// ═══════════════════════════════════════════════════════════════════════
// aiGenerationsApi
// ═══════════════════════════════════════════════════════════════════════

describe('aiGenerationsApi', () => {
  beforeEach(clearMocks)

  it('list() calls GET /api/aiagent/generations', async () => {
    await aiGenerationsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/generations', expect.anything())
  })

  it('list(params) passes query params', async () => {
    await aiGenerationsApi.list({ page: 2, page_size: 10 })
    expect(mockGet).toHaveBeenCalledWith(
      '/api/aiagent/generations',
      expect.objectContaining({ params: { page: 2, page_size: 10 } })
    )
  })

  it('get(id) calls GET /api/aiagent/generations/:id', async () => {
    await aiGenerationsApi.get('gen-456')
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/generations/gen-456', expect.anything())
  })

  it('create(data) calls POST /api/aiagent/generations', async () => {
    const payload = { config_id: 'cfg-1', feature_name: 'Blog', prompt: 'Build a blog' }
    await aiGenerationsApi.create(payload)
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations', payload)
  })

  it('process(id) calls POST /api/aiagent/generations/:id/process', async () => {
    await aiGenerationsApi.process('gen-456')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations/gen-456/process', {})
  })

  it('progress(id) calls GET /api/aiagent/generations/:id/progress', async () => {
    await aiGenerationsApi.progress('gen-456')
    expect(mockGet).toHaveBeenCalledWith(
      '/api/aiagent/generations/gen-456/progress',
      expect.anything()
    )
  })

  it('release(id) calls POST /api/aiagent/generations/:id/release', async () => {
    await aiGenerationsApi.release('gen-456')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations/gen-456/release', {})
  })

  it('revert(id) calls POST /api/aiagent/generations/:id/revert', async () => {
    await aiGenerationsApi.revert('gen-456')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations/gen-456/revert', {})
  })

  it('cancel(id) calls POST /api/aiagent/generations/:id/cancel', async () => {
    await aiGenerationsApi.cancel('gen-456')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations/gen-456/cancel', {})
  })

  it('delete(id) calls DELETE /api/aiagent/generations/:id', async () => {
    await aiGenerationsApi.delete('gen-456')
    expect(mockDelete).toHaveBeenCalledWith('/api/aiagent/generations/gen-456')
  })

  it('deployStaging(id) calls POST /api/aiagent/generations/:id/deploy-staging', async () => {
    await aiGenerationsApi.deployStaging('gen-456')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/generations/gen-456/deploy-staging', {})
  })

  it('requestChanges(id, data) calls POST correct endpoint', async () => {
    await aiGenerationsApi.requestChanges('gen-456', { notes: 'Fix naming' })
    expect(mockPost).toHaveBeenCalledWith(
      '/api/aiagent/generations/gen-456/request-changes',
      { notes: 'Fix naming' }
    )
  })

  it('scheduleRelease(id, data) calls POST correct endpoint', async () => {
    const data = { scheduled_at: '2026-03-01T10:00:00Z' }
    await aiGenerationsApi.scheduleRelease('gen-456', data)
    expect(mockPost).toHaveBeenCalledWith(
      '/api/aiagent/generations/gen-456/schedule-release',
      data
    )
  })
})

// ═══════════════════════════════════════════════════════════════════════
// aiProvidersApi
// ═══════════════════════════════════════════════════════════════════════

describe('aiProvidersApi', () => {
  beforeEach(clearMocks)

  it('list() calls GET /api/aiagent/providers', async () => {
    await aiProvidersApi.list()
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/providers', expect.anything())
  })

  it('listModels() calls POST /api/aiagent/providers/models', async () => {
    await aiProvidersApi.listModels({ provider_name: 'openai', api_key: 'sk-x' })
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/providers/models', { provider_name: 'openai', api_key: 'sk-x' })
  })

  it('testCredentials() calls POST /api/aiagent/providers/test', async () => {
    await aiProvidersApi.testCredentials({ provider_name: 'openai', api_key: 'sk-x', model_name: 'gpt-4o' })
    expect(mockPost).toHaveBeenCalledWith(
      '/api/aiagent/providers/test',
      { provider_name: 'openai', api_key: 'sk-x', model_name: 'gpt-4o' },
    )
  })

  it('get(id) calls GET /api/aiagent/providers/:id', async () => {
    await aiProvidersApi.get('prov-1')
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/providers/prov-1', expect.anything())
  })

  it('create(data) calls POST /api/aiagent/providers', async () => {
    await aiProvidersApi.create({ provider_name: 'openai', api_key: 'sk-...' })
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/providers', expect.anything())
  })

  it('update(id, data) calls PUT /api/aiagent/providers/:id', async () => {
    await aiProvidersApi.update('prov-1', { api_key: 'sk-new' })
    expect(mockPut).toHaveBeenCalledWith('/api/aiagent/providers/prov-1', expect.anything())
  })

  it('delete(id) calls DELETE /api/aiagent/providers/:id', async () => {
    await aiProvidersApi.delete('prov-1')
    expect(mockDelete).toHaveBeenCalledWith('/api/aiagent/providers/prov-1')
  })

  it('testConnection(id) calls POST /api/aiagent/providers/:id/test', async () => {
    await aiProvidersApi.testConnection('prov-1')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/providers/prov-1/test', {})
  })
})

// ═══════════════════════════════════════════════════════════════════════
// aiHistoryApi
// ═══════════════════════════════════════════════════════════════════════

describe('aiChatApi', () => {
  beforeEach(clearMocks)

  it('listConversations(agentId) calls GET /api/aiagent/agents/:id/conversations', async () => {
    await aiChatApi.listConversations('agent-1')
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/agents/agent-1/conversations', expect.anything())
  })

  it('createConversation(agentId) calls POST /api/aiagent/agents/:id/conversations', async () => {
    await aiChatApi.createConversation('agent-1')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/agents/agent-1/conversations', {})
  })

  it('getConversation(id) calls GET /api/aiagent/conversations/:id', async () => {
    await aiChatApi.getConversation('c-1')
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/conversations/c-1', expect.anything())
  })

  it('deleteConversation(id) calls DELETE /api/aiagent/conversations/:id', async () => {
    await aiChatApi.deleteConversation('c-1')
    expect(mockDelete).toHaveBeenCalledWith('/api/aiagent/conversations/c-1')
  })

  it('attachmentUrl(id) points at the authenticated download route', () => {
    expect(aiChatApi.attachmentUrl('a-1')).toMatch(/\/api\/aiagent\/attachments\/a-1$/)
  })

  it('sendMessage() streams SSE frames into onEvent', async () => {
    const frames = [
      'data: {"type":"user_message","message":{"id":"u1","role":"user","content":"hi","attachments":[]},"title":"hi"}\n\n',
      'data: {"type":"assistant_start","message_id":"a1"}\n\ndata: {"type":"token","text":"Hel"}\n\n',
      'data: {"type":"token","text":"lo"}\n\ndata: {"type":"done","message":{"id":"a1","role":"assistant","content":"Hello","attachments":[]}}\n\n',
    ]
    // jsdom has no TextEncoder/TextDecoder; use Node's for the fake stream and the decoder under test.
    const { TextEncoder: NodeTextEncoder, TextDecoder: NodeTextDecoder } = jest.requireActual('util')
    const g = global as unknown as { TextDecoder?: unknown; fetch: jest.Mock }
    const prevDecoder = g.TextDecoder
    g.TextDecoder = NodeTextDecoder
    const encoder = new NodeTextEncoder()
    let i = 0
    const body = {
      getReader: () => ({
        read: async () => (i < frames.length ? { value: encoder.encode(frames[i++]), done: false } : { value: undefined, done: true }),
      }),
    }
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 200, body })
    g.fetch = fetchMock

    const events: unknown[] = []
    await aiChatApi.sendMessage('c-1', { content: 'hi', attachment_ids: [] }, e => events.push(e))

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/aiagent\/conversations\/c-1\/messages$/),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(events.map(e => (e as { type: string }).type)).toEqual(['user_message', 'assistant_start', 'token', 'token', 'done'])
    g.TextDecoder = prevDecoder
  })
})

describe('aiHistoryApi', () => {
  beforeEach(clearMocks)

  it('list() calls GET /api/aiagent/generations', async () => {
    await aiHistoryApi.list()
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/generations', expect.anything())
  })

  it('get(id) calls GET /api/aiagent/generations/:id', async () => {
    await aiHistoryApi.get('gen-789')
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/generations/gen-789', expect.anything())
  })
})

// ═══════════════════════════════════════════════════════════════════════
// customDomainsApi
// ═══════════════════════════════════════════════════════════════════════

describe('customDomainsApi', () => {
  beforeEach(clearMocks)

  it('list() calls GET /api/aiagent/domains', async () => {
    await customDomainsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/api/aiagent/domains', expect.anything())
  })

  it('create(data) calls POST /api/aiagent/domains', async () => {
    await customDomainsApi.create({ domain: 'app.example.com' })
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/domains', expect.anything())
  })

  it('add() is an alias for create()', async () => {
    await customDomainsApi.add({ domain: 'api.example.com' })
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/domains', expect.anything())
  })

  it('delete(id) calls DELETE /api/aiagent/domains/:id', async () => {
    await customDomainsApi.delete('domain-1')
    expect(mockDelete).toHaveBeenCalledWith('/api/aiagent/domains/domain-1')
  })

  it('verify(id) calls POST /api/aiagent/domains/:id/verify', async () => {
    await customDomainsApi.verify('domain-1')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/domains/domain-1/verify', {})
  })

  it('activate(id) calls POST /api/aiagent/domains/:id/activate', async () => {
    await customDomainsApi.activate('domain-1')
    expect(mockPost).toHaveBeenCalledWith('/api/aiagent/domains/domain-1/activate', {})
  })
})

// ═══════════════════════════════════════════════════════════════════════
// authApi
// ═══════════════════════════════════════════════════════════════════════

describe('authApi', () => {
  beforeEach(clearMocks)

  it('login(data) calls POST /api/auth/login', async () => {
    await authApi.login({ username_or_email: 'user@test.com', password: 'pass' })
    expect(mockPost).toHaveBeenCalledWith('/api/auth/login', expect.anything())
  })

  it('register(data) calls POST /api/auth/register', async () => {
    await authApi.register({ email: 'user@test.com', password: 'pass' })
    expect(mockPost).toHaveBeenCalledWith('/api/auth/register', expect.anything())
  })

  it('me() calls GET /api/auth/me', async () => {
    await authApi.me()
    expect(mockGet).toHaveBeenCalledWith('/api/auth/me', expect.anything())
  })

  it('logout() calls POST /api/auth/logout', async () => {
    await authApi.logout()
    expect(mockPost).toHaveBeenCalledWith('/api/auth/logout', undefined)
  })

  it('forgotPassword(data) calls POST /api/auth/forgot-password', async () => {
    await authApi.forgotPassword({ email: 'user@test.com' })
    expect(mockPost).toHaveBeenCalledWith('/api/auth/forgot-password', expect.anything())
  })

  it('resetPassword(data) calls POST /api/auth/reset-password', async () => {
    await authApi.resetPassword({ token: 'abc', password: 'new' })
    expect(mockPost).toHaveBeenCalledWith('/api/auth/reset-password', expect.anything())
  })

  it('confirmEmail(data) calls POST /api/auth/confirm-email', async () => {
    await authApi.confirmEmail({ token: 'abc123' })
    expect(mockPost).toHaveBeenCalledWith('/api/auth/confirm-email', expect.anything())
  })
})

// ═══════════════════════════════════════════════════════════════════════
// dashboardApi
// ═══════════════════════════════════════════════════════════════════════

describe('dashboardApi', () => {
  beforeEach(clearMocks)

  it('stats() calls GET /api/dashboard/stats', async () => {
    await dashboardApi.stats()
    expect(mockGet).toHaveBeenCalledWith('/api/dashboard/stats', expect.anything())
  })

  it('activity() calls GET /api/dashboard/activity', async () => {
    await dashboardApi.activity()
    expect(mockGet).toHaveBeenCalledWith('/api/dashboard/activity', expect.anything())
  })

  it('systemInfo() calls GET /api/monitoring/system/info', async () => {
    await dashboardApi.systemInfo()
    expect(mockGet).toHaveBeenCalledWith('/api/monitoring/system/info', expect.anything())
  })
})
