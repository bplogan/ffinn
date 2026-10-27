/** Visual identity for agents: a small palette the user picks from when creating one. */

export interface AgentAvatarStyle {
  key: string
  label: string
  /** Tailwind gradient classes for the badge background. */
  gradient: string
  /** Soft tint used behind cards and headers. */
  tint: string
}

export const AGENT_AVATARS: AgentAvatarStyle[] = [
  { key: 'violet',  label: 'Violet',  gradient: 'from-violet-500 to-fuchsia-500',  tint: 'bg-violet-500/10' },
  { key: 'ocean',   label: 'Ocean',   gradient: 'from-sky-500 to-indigo-500',      tint: 'bg-sky-500/10' },
  { key: 'mint',    label: 'Mint',    gradient: 'from-emerald-500 to-teal-500',    tint: 'bg-emerald-500/10' },
  { key: 'sunset',  label: 'Sunset',  gradient: 'from-orange-500 to-rose-500',     tint: 'bg-orange-500/10' },
  { key: 'gold',    label: 'Gold',    gradient: 'from-amber-400 to-orange-500',    tint: 'bg-amber-500/10' },
  { key: 'rose',    label: 'Rose',    gradient: 'from-pink-500 to-rose-500',       tint: 'bg-pink-500/10' },
  { key: 'slate',   label: 'Slate',   gradient: 'from-slate-500 to-gray-700',      tint: 'bg-slate-500/10' },
  { key: 'build',   label: 'Build',   gradient: 'from-brand-500 to-violet-600',    tint: 'bg-brand-500/10' },
]

export function avatarStyle(key?: string | null): AgentAvatarStyle {
  return AGENT_AVATARS.find(a => a.key === key) ?? AGENT_AVATARS[0]
}

/** Two-letter monogram for an agent name, e.g. "Support Helper" → "SH". */
export function monogram(name?: string | null): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (!words.length) return 'AI'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

/** Starting points for an agent's instructions. */
export const AGENT_TEMPLATES: Array<{ key: string; label: string; description: string; prompt: string }> = [
  {
    key: 'general', label: 'General assistant',
    description: 'A capable all-rounder for questions, writing and analysis.',
    prompt: 'You are a helpful, precise assistant. Give direct answers, show your reasoning when it matters, and ask a clarifying question when the request is ambiguous.',
  },
  {
    key: 'support', label: 'Customer support',
    description: 'Answers customer questions in a friendly, consistent voice.',
    prompt: 'You are a customer support specialist for our product. Be warm and concise. Confirm you understood the problem, give step-by-step fixes, and escalate politely when something needs a human. Never invent policies or prices.',
  },
  {
    key: 'code', label: 'Code reviewer',
    description: 'Reviews code and explains issues with fixes.',
    prompt: 'You are a senior software engineer doing code review. Point out bugs, security issues and unclear code, most important first. Show corrected code in fenced blocks. Prefer small, concrete suggestions over rewrites.',
  },
  {
    key: 'writer', label: 'Content writer',
    description: 'Drafts and edits marketing copy, emails and docs.',
    prompt: 'You are an experienced content writer. Match the requested tone, keep sentences tight, and offer two variants when asked for options. Flag any claims that would need a source.',
  },
  {
    key: 'analyst', label: 'Data analyst',
    description: 'Works through uploaded data and reports findings.',
    prompt: 'You are a data analyst. When given data or files, summarize what is in them, surface the key patterns with numbers, and state assumptions explicitly. Present results as short sections with tables where useful.',
  },
]
