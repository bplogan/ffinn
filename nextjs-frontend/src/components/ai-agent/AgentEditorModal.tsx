'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { ChevronDown, Plus, Sparkles } from 'lucide-react'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import Input, { Select, TextArea } from '@/components/ui/Input'
import AgentAvatar from '@/components/ai-agent/AgentAvatar'
import ProviderSetupForm, {
  EMPTY_PROVIDER_DRAFT,
  providerDraftReady,
  providerDraftToPayload,
  type ProviderDraft,
} from '@/components/ai-agent/ProviderSetupForm'
import { aiAgentsApi, aiProvidersApi } from '@/lib/api'
import { AGENT_AVATARS, AGENT_TEMPLATES } from '@/lib/agentAvatars'
import type { AIAgentConfig, AIProvider } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  /** Pass an existing assistant agent to edit it; omit to create one. */
  agent?: AIAgentConfig | null
  onSaved?: (agent: AIAgentConfig) => void
}

interface Draft {
  name: string
  description: string
  system_prompt: string
  avatar: string
  provider_id: string
  model: string
  temperature: number
}

const EMPTY: Draft = {
  name: '', description: '', system_prompt: AGENT_TEMPLATES[0].prompt, avatar: 'violet',
  provider_id: '', model: '', temperature: 0.7,
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, '')
  return fallback
}

export default function AgentEditorModal({ open, onClose, agent, onSaved }: Props) {
  const qc = useQueryClient()
  const editing = !!agent
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const patch = (p: Partial<Draft>) => setDraft(d => ({ ...d, ...p }))
  const [showNewProvider, setShowNewProvider] = useState(false)
  const [providerDraft, setProviderDraft] = useState<ProviderDraft>(EMPTY_PROVIDER_DRAFT)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const { data: providers } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
    enabled: open,
  })
  const providerList = providers ?? []

  useEffect(() => {
    if (!open) return
    if (agent) {
      setDraft({
        name: agent.name ?? '',
        description: agent.description ?? '',
        system_prompt: agent.system_prompt ?? '',
        avatar: agent.avatar ?? 'violet',
        provider_id: agent.provider_id ?? '',
        model: agent.ai_model ?? '',
        temperature: agent.temperature ?? 0.7,
      })
    } else {
      setDraft({ ...EMPTY, avatar: AGENT_AVATARS[Math.floor(Math.random() * 6)].key })
    }
    setShowNewProvider(false)
    setProviderDraft(EMPTY_PROVIDER_DRAFT)
    setShowAdvanced(false)
  }, [open, agent])

  // With no saved providers the only path is to add one, so open that form by default.
  useEffect(() => {
    if (open && providers && providers.length === 0) setShowNewProvider(true)
  }, [open, providers])

  const saveMut = useMutation({
    mutationFn: async () => {
      let providerId = draft.provider_id
      if (showNewProvider) {
        const created = (await aiProvidersApi.create(providerDraftToPayload(providerDraft))) as { id: string }
        providerId = created.id
        qc.invalidateQueries({ queryKey: ['ai-providers'] })
      }
      const body = {
        name: draft.name.trim(),
        description: draft.description.trim() || undefined,
        system_prompt: draft.system_prompt.trim() || undefined,
        avatar: draft.avatar,
        temperature: draft.temperature,
        ai_model: draft.model.trim() || undefined,
      }
      if (editing && agent) {
        return aiAgentsApi.update(agent.id, { ...body, provider_id: providerId || undefined }) as Promise<AIAgentConfig>
      }
      return aiAgentsApi.create({ ...body, kind: 'assistant', provider_config_id: providerId }) as Promise<AIAgentConfig>
    },
    onSuccess: (saved) => {
      toast.success(editing ? 'Agent updated' : `${saved.name} is ready`)
      qc.invalidateQueries({ queryKey: ['ai-agent-configs'] })
      qc.invalidateQueries({ queryKey: ['ai-agents'] })
      onSaved?.(saved)
      onClose()
    },
    onError: (err) => toast.error(errorDetail(err, 'Could not save the agent.')),
  })

  const selectedProvider = providerList.find(p => p.id === draft.provider_id)
  const ready =
    draft.name.trim().length >= 2 &&
    (showNewProvider ? providerDraftReady(providerDraft) : !!draft.provider_id)

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={editing ? `Edit ${agent?.name ?? 'agent'}` : 'Create an agent'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending} disabled={!ready} icon={<Sparkles size={15} />}>
            {editing ? 'Save changes' : 'Create agent'}
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* Identity + instructions */}
        <div className="space-y-5">
          <div className="flex items-start gap-4">
            <AgentAvatar name={draft.name || 'New agent'} avatar={draft.avatar} size="xl" />
            <div className="flex-1 space-y-3">
              <Input
                label="Name"
                required
                placeholder="e.g. Support Helper, Contract Reviewer"
                value={draft.name}
                onChange={e => patch({ name: e.target.value })}
                autoFocus
              />
              <Input
                label="What is this agent responsible for?"
                placeholder="One line shown on its card, e.g. Answers billing questions from the help desk"
                value={draft.description}
                onChange={e => patch({ description: e.target.value })}
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="label !mb-0">Instructions</label>
              {!editing && (
                <div className="relative">
                  <select
                    className="text-xs bg-transparent text-brand-600 dark:text-brand-400 font-medium cursor-pointer pr-4 focus:outline-none"
                    value=""
                    onChange={e => {
                      const t = AGENT_TEMPLATES.find(x => x.key === e.target.value)
                      if (t) patch({ system_prompt: t.prompt, description: draft.description || t.description })
                    }}
                  >
                    <option value="">Start from a template…</option>
                    {AGENT_TEMPLATES.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
                  </select>
                  <ChevronDown size={12} className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-brand-500" />
                </div>
              )}
            </div>
            <TextArea
              label=""
              rows={9}
              placeholder="Tell the agent who it is, what it should do, and how it should answer…"
              value={draft.system_prompt}
              onChange={e => patch({ system_prompt: e.target.value })}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
              Sent with every conversation. The agent only sees what you write here plus the chat itself.
            </p>
          </div>

          <div>
            <p className="label">Colour</p>
            <div className="flex flex-wrap gap-2">
              {AGENT_AVATARS.filter(a => a.key !== 'build').map(a => (
                <button
                  key={a.key}
                  type="button"
                  title={a.label}
                  onClick={() => patch({ avatar: a.key })}
                  className={clsx(
                    'w-8 h-8 rounded-xl bg-gradient-to-br transition-transform',
                    a.gradient,
                    draft.avatar === a.key ? 'ring-2 ring-offset-2 ring-brand-500 dark:ring-offset-gray-800 scale-110' : 'hover:scale-105',
                  )}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Brain */}
        <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-5">
          <div>
            <p className="label">AI provider</p>
            <p className="text-xs text-gray-500 dark:text-gray-400 -mt-1 mb-2">The model and key this agent will use. Keys are stored encrypted and shared across agents.</p>
            {!showNewProvider ? (
              <div className="space-y-2">
                <Select value={draft.provider_id} onChange={e => patch({ provider_id: e.target.value, model: '' })}>
                  <option value="">Choose a saved provider</option>
                  {providerList.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.display_name || p.provider_name || p.name}{p.model_name ? ` — ${p.model_name}` : ''}
                    </option>
                  ))}
                </Select>
                <button
                  type="button"
                  onClick={() => setShowNewProvider(true)}
                  className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline"
                >
                  <Plus size={12} /> Add a provider with your own key
                </button>
              </div>
            ) : (
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-3 space-y-3 bg-gray-50/60 dark:bg-gray-800/40">
                <ProviderSetupForm value={providerDraft} onChange={p => setProviderDraft(d => ({ ...d, ...p }))} />
                {providerList.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowNewProvider(false)}
                    className="text-xs text-gray-500 hover:underline"
                  >
                    Use a saved provider instead
                  </button>
                )}
              </div>
            )}
          </div>

          {!showNewProvider && (
            <div className="max-w-sm">
              <Input
                label="Model (optional)"
                placeholder={selectedProvider?.model_name || 'Provider default'}
                value={draft.model}
                onChange={e => patch({ model: e.target.value })}
                hint="Leave blank to use the model set on the provider."
              />
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowAdvanced(s => !s)}
            className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <ChevronDown size={12} className={clsx('transition-transform', showAdvanced && 'rotate-180')} /> Advanced
          </button>
          {showAdvanced && (
            <div className="max-w-sm">
              <div className="flex items-center justify-between">
                <label className="label !mb-0" htmlFor="agent-temperature">Creativity</label>
                <span className="text-xs tabular-nums text-gray-500">{draft.temperature.toFixed(1)}</span>
              </div>
              <input
                id="agent-temperature"
                type="range" min={0} max={1.5} step={0.1}
                value={draft.temperature}
                onChange={e => patch({ temperature: Number(e.target.value) })}
                className="w-full accent-brand-500 mt-2"
              />
              <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                <span>Precise</span><span>Balanced</span><span>Creative</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
