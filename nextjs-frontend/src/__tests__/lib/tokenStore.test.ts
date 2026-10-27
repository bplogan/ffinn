/**
 * Tests for tokenStore — the JWT token management utility.
 *
 * Note: tokenStore is intentionally MEMORY-ONLY for security (XSS resistance).
 * The access token never touches localStorage or a JS-readable cookie.
 * The refresh token lives in an HttpOnly cookie set by the server.
 */

// Mock js-cookie before importing tokenStore
const cookieStore: Record<string, string> = {}
jest.mock('js-cookie', () => ({
  get: (key: string) => cookieStore[key],
  set: (key: string, value: string) => { cookieStore[key] = value },
  remove: (key: string) => { delete cookieStore[key] },
}))

// Mock next/headers and related next stuff
jest.mock('next/navigation', () => ({ useRouter: jest.fn() }))

import { tokenStore, userStore } from '@/lib/api'

// ── Helpers ────────────────────────────────────────────────────────────────

const USER_KEY = 'ffinn_user'

function clearAll() {
  Object.keys(cookieStore).forEach(k => delete cookieStore[k])
  localStorage.clear()
  tokenStore.clear()
}

// ═══════════════════════════════════════════════════════════════════════
// tokenStore — memory-only access token
// ═══════════════════════════════════════════════════════════════════════

describe('tokenStore (memory-only)', () => {
  beforeEach(() => {
    clearAll()
  })

  describe('set', () => {
    it('does NOT write to localStorage (XSS hardening)', () => {
      tokenStore.set('test-jwt-token')
      // Scan all localStorage keys to make sure the token does not leak.
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)!
        expect(localStorage.getItem(k)).not.toBe('test-jwt-token')
      }
    })

    it('does NOT write to a JS-readable cookie', () => {
      tokenStore.set('test-jwt-token')
      expect(Object.values(cookieStore)).not.toContain('test-jwt-token')
    })

    it('overwrites previous token in memory', () => {
      tokenStore.set('old-token')
      tokenStore.set('new-token')
      expect(tokenStore.get()).toBe('new-token')
    })
  })

  describe('get', () => {
    it('returns null when nothing is stored', () => {
      expect(tokenStore.get()).toBeNull()
    })

    it('returns the in-memory token after set', () => {
      tokenStore.set('round-trip-token')
      expect(tokenStore.get()).toBe('round-trip-token')
    })
  })

  describe('clear', () => {
    it('clears the in-memory token', () => {
      tokenStore.set('to-be-cleared')
      tokenStore.clear()
      expect(tokenStore.get()).toBeNull()
    })

    it('does not touch user data in localStorage (separate concern)', () => {
      localStorage.setItem(USER_KEY, JSON.stringify({ id: '1' }))
      tokenStore.clear()
      // tokenStore.clear is responsible for the access token only;
      // userStore.clear is what removes the cached user.
      expect(localStorage.getItem(USER_KEY)).not.toBeNull()
    })
  })
})

// ═══════════════════════════════════════════════════════════════════════
// userStore
// ═══════════════════════════════════════════════════════════════════════

describe('userStore', () => {
  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
    userName: 'testuser',
    roles: ['Admin'],
  }

  beforeEach(() => {
    clearAll()
  })

  describe('set', () => {
    it('stores user as JSON in localStorage', () => {
      userStore.set(mockUser)
      const raw = localStorage.getItem(USER_KEY)
      expect(raw).not.toBeNull()
      expect(JSON.parse(raw!)).toEqual(mockUser)
    })
  })

  describe('get', () => {
    it('returns null when nothing is stored', () => {
      expect(userStore.get()).toBeNull()
    })

    it('returns the stored user object', () => {
      userStore.set(mockUser)
      const retrieved = userStore.get()
      expect(retrieved).toEqual(mockUser)
    })

    it('returns null for malformed JSON', () => {
      localStorage.setItem(USER_KEY, 'not-valid-json{{{')
      expect(userStore.get()).toBeNull()
    })

    it('returns nested objects correctly', () => {
      const user = { ...mockUser, profile: { avatar: 'https://example.com/a.png' } }
      userStore.set(user)
      const retrieved = userStore.get()
      expect((retrieved as typeof user)?.profile?.avatar).toBe('https://example.com/a.png')
    })
  })

  describe('clear', () => {
    it('removes user from localStorage', () => {
      userStore.set(mockUser)
      userStore.clear()
      expect(localStorage.getItem(USER_KEY)).toBeNull()
    })

    it('get returns null after clear', () => {
      userStore.set(mockUser)
      userStore.clear()
      expect(userStore.get()).toBeNull()
    })
  })
})
