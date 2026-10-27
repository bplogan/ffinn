/** Public site identity used for SEO metadata, sitemaps, structured data and share images. */

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ffinn.ca').replace(/\/$/, '')
export const GITHUB_URL = 'https://github.com/bplogan/ffinn'

export const SITE_NAME = 'ffinn'
export const SITE_TITLE = 'ffinn — Free, open-source AI SaaS framework'
export const SITE_TAGLINE = 'The free, open-source SaaS framework with built-in AI agents'
export const SITE_DESCRIPTION =
  'ffinn is a free, MIT-licensed, multi-tenant SaaS framework built on FastAPI and Next.js. ' +
  'Auth, roles, billing and admin out of the box, plus AI agents that write features, open pull ' +
  'requests and chat with your files — using your own OpenAI, Claude, Gemini or Ollama keys.'

export const SITE_KEYWORDS = [
  'open source SaaS framework',
  'SaaS boilerplate',
  'SaaS starter kit',
  'multi-tenant SaaS',
  'AI agent framework',
  'AI code generation',
  'bring your own AI key',
  'FastAPI Next.js boilerplate',
  'Next.js SaaS template',
  'Python SaaS framework',
  'self-hosted ChatGPT alternative',
  'MIT license',
  'Stripe billing',
  'RBAC',
  'OpenAI',
  'Anthropic Claude',
  'Google Gemini',
  'Ollama',
]
