/**
 * Tests for AI Agent TypeScript types to ensure shape correctness.
 * These tests serve as compile-time + runtime guarantees that our types
 * match what the Python backend API returns.
 */

import type {
  AIAgent,
  AIProvider,
  AIGeneration,
  PagedResult,
} from '@/types'

// ═══════════════════════════════════════════════════════════════════════
// Type shape validation helpers
// ═══════════════════════════════════════════════════════════════════════

/**
 * Creates a minimal object that satisfies the AIAgent interface.
 * If the type changes incompatibly, this will cause a compile error.
 */
function makeAIAgent(overrides: Partial<AIAgent> = {}): AIAgent {
  return {
    id: 'agent-123',
    name: 'Test Agent',
    ...overrides,
  }
}

function makeAIProvider(overrides: Partial<AIProvider> = {}): AIProvider {
  return {
    id: 'provider-1',
    name: 'OpenAI',
    provider_name: 'openai',
    isActive: true,
    ...overrides,
  }
}

function makeAIGeneration(overrides: Partial<AIGeneration> = {}): AIGeneration {
  return {
    id: 'gen-123',
    user_prompt: 'Build a blog page',
    status: 'Queued',
    ...overrides,
  }
}

function makePagedResult<T>(items: T[]): PagedResult<T> {
  return {
    items,
    totalCount: items.length,
    pageIndex: 1,
    pageSize: 20,
  }
}

// ═══════════════════════════════════════════════════════════════════════
// AIAgent type tests
// ═══════════════════════════════════════════════════════════════════════

describe('AIAgent type', () => {
  it('has required id field', () => {
    const agent = makeAIAgent()
    expect(agent.id).toBe('agent-123')
  })

  it('has required name field', () => {
    const agent = makeAIAgent({ name: 'My Agent' })
    expect(agent.name).toBe('My Agent')
  })

  it('isActive defaults to true when set', () => {
    const agent = makeAIAgent({ isActive: true })
    expect(agent.isActive).toBe(true)
  })

  it('can be inactive', () => {
    const agent = makeAIAgent({ isActive: false })
    expect(agent.isActive).toBe(false)
  })

  it('accepts optional description', () => {
    const agent = makeAIAgent({ description: 'My agent description' })
    expect(agent.description).toBe('My agent description')
  })

  it('accepts undefined description', () => {
    const agent = makeAIAgent({ description: undefined })
    expect(agent.description).toBeUndefined()
  })

  it('accepts optional instructions', () => {
    const agent = makeAIAgent({ instructions: 'Always use TypeScript' })
    expect(agent.instructions).toBe('Always use TypeScript')
  })

  it('accepts optional providerId', () => {
    const agent = makeAIAgent({ providerId: 'prov-xyz' })
    expect(agent.providerId).toBe('prov-xyz')
  })
})

// ═══════════════════════════════════════════════════════════════════════
// AIProvider type tests
// ═══════════════════════════════════════════════════════════════════════

describe('AIProvider type', () => {
  it('has required id and name', () => {
    const p = makeAIProvider()
    expect(p.id).toBeDefined()
    expect(p.name).toBe('OpenAI')
  })

  it('has optional provider_name', () => {
    const p = makeAIProvider({ provider_name: 'anthropic' })
    expect(p.provider_name).toBe('anthropic')
  })

  it('isActive field is boolean', () => {
    const active = makeAIProvider({ isActive: true })
    const inactive = makeAIProvider({ isActive: false })
    expect(typeof active.isActive).toBe('boolean')
    expect(typeof inactive.isActive).toBe('boolean')
  })

  // The backend sometimes returns snake_case is_active
  it('supports is_active snake_case field', () => {
    const p = makeAIProvider({ is_active: true })
    expect(p.is_active).toBe(true)
  })

  it('supports model_name', () => {
    const p = makeAIProvider({ model_name: 'gpt-4o' })
    expect(p.model_name).toBe('gpt-4o')
  })

  it('supports models array', () => {
    const p = makeAIProvider({ models: ['gpt-4o', 'gpt-4o-mini', 'o1'] })
    expect(p.models).toHaveLength(3)
    expect(p.models![0]).toBe('gpt-4o')
  })

  it('supports apiKeyConfigured flag', () => {
    const configured = makeAIProvider({ apiKeyConfigured: true })
    const notConfigured = makeAIProvider({ apiKeyConfigured: false })
    expect(configured.apiKeyConfigured).toBe(true)
    expect(notConfigured.apiKeyConfigured).toBe(false)
  })

  it('supports display_name', () => {
    const p = makeAIProvider({ display_name: 'OpenAI GPT-4' })
    expect(p.display_name).toBe('OpenAI GPT-4')
  })

  // Test the camelCase alias pattern used in AI agent dashboard page
  it('coalesces is_active || isActive for backward compat', () => {
    const p = makeAIProvider({ isActive: true })
    // The page does: p.is_active ?? p.isActive
    const isActive = p.is_active ?? p.isActive
    expect(isActive).toBe(true)
  })
})

// ═══════════════════════════════════════════════════════════════════════
// AIGeneration type tests — uses snake_case fields matching backend API
// ═══════════════════════════════════════════════════════════════════════

describe('AIGeneration type', () => {
  it('has required id, user_prompt and status fields', () => {
    const gen = makeAIGeneration()
    expect(gen.id).toBeDefined()
    expect(gen.status).toBeDefined()
    expect(gen.user_prompt).toBeDefined()
  })

  it('user_prompt is a string', () => {
    const gen = makeAIGeneration({ user_prompt: 'Create a landing page with hero section' })
    expect(gen.user_prompt).toBe('Create a landing page with hero section')
  })

  it('status can be any generation status string', () => {
    const statuses = [
      'Draft', 'Queued', 'Analyzing', 'Generating', 'Validating',
      'AutoFixing', 'Committing', 'CreatingPr', 'Building', 'Staging',
      'Ready', 'Released', 'Failed', 'Cancelled', 'Reverted',
    ]

    statuses.forEach(status => {
      const gen = makeAIGeneration({ status })
      expect(gen.status).toBe(status)
    })
  })

  it('accepts optional pr_url (snake_case)', () => {
    const gen = makeAIGeneration({ pr_url: 'https://github.com/owner/repo/pull/5' })
    expect(gen.pr_url).toContain('pull/5')
  })

  it('accepts optional pull_request_url alias', () => {
    const gen = makeAIGeneration({ pull_request_url: 'https://github.com/owner/repo/pull/5' })
    expect(gen.pull_request_url).toContain('pull/5')
  })

  it('accepts optional branch_name (snake_case)', () => {
    const gen = makeAIGeneration({ branch_name: 'ai-feature/blog-abc123' })
    expect(gen.branch_name).toContain('ai-feature')
  })

  it('accepts optional error_message (snake_case)', () => {
    const gen = makeAIGeneration({ error_message: 'AI provider rate limited' })
    expect(gen.error_message).toBe('AI provider rate limited')
  })

  it('accepts optional tokens_used (snake_case)', () => {
    const gen = makeAIGeneration({ tokens_used: 4500 })
    expect(gen.tokens_used).toBe(4500)
  })

  it('accepts optional estimated_cost (snake_case)', () => {
    const gen = makeAIGeneration({ estimated_cost: 0.0225 })
    expect(gen.estimated_cost).toBeCloseTo(0.0225, 4)
  })

  it('accepts optional config_id (snake_case)', () => {
    const gen = makeAIGeneration({ config_id: 'config-abc-123' })
    expect(gen.config_id).toBe('config-abc-123')
  })

  it('accepts optional feature_name (snake_case)', () => {
    const gen = makeAIGeneration({ feature_name: 'Blog Feature' })
    expect(gen.feature_name).toBe('Blog Feature')
  })

  it('accepts optional staging_url', () => {
    const gen = makeAIGeneration({ staging_url: 'https://staging.example.com' })
    expect(gen.staging_url).toContain('staging')
  })

  it('accepts optional generated_files record', () => {
    const files = {
      'src/pages/blog.tsx': 'export default function Blog() {}',
      'src/components/BlogCard.tsx': 'export default function BlogCard() {}',
    }
    const gen = makeAIGeneration({ generated_files: files })
    expect(Object.keys(gen.generated_files!)).toHaveLength(2)
    expect(gen.generated_files!['src/pages/blog.tsx']).toContain('Blog')
  })

  it('accepts optional validation_errors array', () => {
    const gen = makeAIGeneration({ validation_errors: ['Missing semicolon', 'Unused import'] })
    expect(gen.validation_errors).toHaveLength(2)
  })

  it('accepts optional ai_model field', () => {
    const gen = makeAIGeneration({ ai_model: 'gpt-4o' })
    expect(gen.ai_model).toBe('gpt-4o')
  })
})

// ═══════════════════════════════════════════════════════════════════════
// PagedResult type tests
// ═══════════════════════════════════════════════════════════════════════

describe('PagedResult', () => {
  it('wraps items array correctly', () => {
    const agents = [makeAIAgent({ id: '1' }), makeAIAgent({ id: '2' })]
    const paged = makePagedResult(agents)
    expect(paged.items).toHaveLength(2)
    expect(paged.totalCount).toBe(2)
  })

  it('totalCount can differ from items.length (server-side pagination)', () => {
    const gens = Array.from({ length: 20 }, (_, i) => makeAIGeneration({ id: `gen-${i}` }))
    const paged: PagedResult<AIGeneration> = { items: gens, totalCount: 50, pageIndex: 1, pageSize: 20 }
    expect(paged.totalCount).toBe(50)
    expect(paged.items).toHaveLength(20)
  })

  it('can be empty', () => {
    const paged = makePagedResult<AIAgent>([])
    expect(paged.items).toHaveLength(0)
    expect(paged.totalCount).toBe(0)
  })

  it('pageIndex and pageSize are optional', () => {
    const paged: PagedResult<AIAgent> = {
      items: [makeAIAgent()],
      totalCount: 1,
    }
    expect(paged.pageIndex).toBeUndefined()
    expect(paged.pageSize).toBeUndefined()
  })
})

