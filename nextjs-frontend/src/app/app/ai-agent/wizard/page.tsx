'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { aiAgentsApi, aiProvidersApi, aiSourceControlApi } from '@/lib/api'
import type { AIProvider } from '@/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import {
  Zap, GitBranch, CheckCircle2, ChevronRight, ChevronLeft, Github,
  Sparkles, PartyPopper, Info, Plus, Bot,
} from 'lucide-react'
import Link from 'next/link'
import ProviderSetupForm, {
  EMPTY_PROVIDER_DRAFT,
  providerDraftReady,
  providerDraftToPayload,
  type ProviderDraft,
} from '@/components/ai-agent/ProviderSetupForm'

// ─── Types ────────────────────────────────────────────────────────────────────

interface AgentState {
  agentName: string
  connectRepo: boolean
  repoUrl: string
  branch: string
  token: string
}

const STEP_LABELS = ['AI Provider', 'Name & repository']

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

function StepIndicator({ step }: { step: number }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-center gap-1">
        {STEP_LABELS.map((label, i) => (
          <div key={label} className="flex items-center gap-1">
            <div className={clsx(
              'flex items-center justify-center w-8 h-8 rounded-full text-xs font-black transition-all',
              i <= step
                ? 'bg-gradient-to-br from-brand-500 to-violet-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400',
              i === step && 'ring-4 ring-brand-200 dark:ring-violet-900/60',
            )}>
              {i < step ? <CheckCircle2 size={14} /> : i + 1}
            </div>
            {i < STEP_LABELS.length - 1 && (
              <div className={clsx('w-10 h-1 rounded-full', i < step ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-700')} />
            )}
          </div>
        ))}
      </div>
      <p className="text-center text-xs font-bold mt-3 text-violet-600 dark:text-violet-400 uppercase tracking-widest">
        Step {step + 1} of {STEP_LABELS.length} &mdash; {STEP_LABELS[step]}
      </p>
    </div>
  )
}

function HintBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 text-sm text-blue-700 dark:text-blue-300">
      <Info size={15} className="flex-shrink-0 mt-0.5" />
      <span>{children}</span>
    </div>
  )
}

// ─── Wizard ───────────────────────────────────────────────────────────────────

export default function AIAgentWizardPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null)
  const [setupSummary, setSetupSummary] = useState<string | null>(null)

  // Provider: pick a saved one, or fill in a new one. Once a new one is saved we keep its id
  // so going Back and Next again updates it instead of creating a duplicate.
  const [useNewProvider, setUseNewProvider] = useState(false)
  const [providerId, setProviderId] = useState('')
  const [savedNewProviderId, setSavedNewProviderId] = useState<string | null>(null)
  const [draft, setDraft] = useState<ProviderDraft>(EMPTY_PROVIDER_DRAFT)
  const patchDraft = (patch: Partial<ProviderDraft>) => setDraft(d => ({ ...d, ...patch }))

  const [agent, setAgent] = useState<AgentState>({
    agentName: '', connectRepo: true, repoUrl: '', branch: 'main', token: '',
  })
  const patchAgent = (patch: Partial<AgentState>) => setAgent(a => ({ ...a, ...patch }))

  const { data: providers, isLoading: providersLoading } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })
  const hasSaved = (providers?.length ?? 0) > 0
  const showNewForm = useNewProvider || (!providersLoading && !hasSaved)

  const saveProviderMut = useMutation({
    mutationFn: async () => {
      const payload = providerDraftToPayload(draft)
      if (savedNewProviderId) {
        await aiProvidersApi.update(savedNewProviderId, payload)
        return savedNewProviderId
      }
      const created = (await aiProvidersApi.create(payload)) as { id: string }
      return created.id
    },
    onSuccess: (id) => {
      setSavedNewProviderId(id)
      setProviderId(id)
      qc.invalidateQueries({ queryKey: ['ai-providers'] })
    },
  })

  const createAgentMut = useMutation({
    mutationFn: () =>
      aiAgentsApi.create({
        name: agent.agentName.trim(),
        provider_config_id: providerId,
        source_control_type: 'github',
        repository_url: agent.connectRepo ? agent.repoUrl.trim() : '',
        source_control_token: agent.connectRepo ? agent.token.trim() : '',
      }) as Promise<{ id: string }>,
  })

  const canAdvanceProvider = showNewForm ? providerDraftReady(draft, !!savedNewProviderId) : !!providerId
  const canCreate =
    agent.agentName.trim().length >= 2 &&
    (!agent.connectRepo || (agent.repoUrl.trim().length > 5 && agent.token.trim().length > 5))

  const handleProviderNext = async () => {
    if (showNewForm) {
      try {
        await saveProviderMut.mutateAsync()
      } catch (err) {
        toast.error(errorDetail(err, 'Could not save the provider — check the details and try again.'))
        return
      }
    }
    setStep(1)
  }

  const handleFinish = async () => {
    try {
      const created = await createAgentMut.mutateAsync()
      setCreatedAgentId(created.id)
      qc.invalidateQueries({ queryKey: ['ai-agents'] })
      qc.invalidateQueries({ queryKey: ['ai-agent-configs'] })
      if (agent.connectRepo && agent.repoUrl.trim()) {
        try {
          await aiSourceControlApi.save({
            provider: 'github',
            repo_url: agent.repoUrl.trim(),
            branch: agent.branch.trim() || 'main',
            access_token: agent.token.trim(),
            auto_sync: false,
            sync_path: '/',
          })
        } catch { /* tenant-level defaults are optional */ }
        try {
          const setup = await aiAgentsApi.setupRepository(created.id, {
            branch: agent.branch.trim() || undefined,
          })
          setSetupSummary(
            setup.success
              ? 'GitHub workflows and callback secrets are configured.'
              : 'Agent created — finish repository setup from Agents → Setup CI.',
          )
        } catch {
          setSetupSummary('Agent created — run Setup CI from the Agents page when ready.')
        }
      }
      setDone(true)
    } catch (err) {
      toast.error(errorDetail(err, 'Could not create your agent — please check your details and try again.'))
    }
  }

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-start py-6">
      <div className="w-full max-w-3xl">
        {!done && <StepIndicator step={step} />}

        {/* ── Step 1: Provider ───────────────────────────────────────────── */}
        {!done && step === 0 && (
          <div className="space-y-5">
            <div className="card p-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Connect an AI provider</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Paste an API key and pick a model. We load the model list straight from the provider and can test
                the connection before you continue.
              </p>
            </div>

            {hasSaved && (
              <div className="card p-5 space-y-3">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">Use a saved provider</p>
                <div className="grid sm:grid-cols-2 gap-2">
                  {providers!.map(p => {
                    const selected = !showNewForm && providerId === p.id
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => { setUseNewProvider(false); setProviderId(p.id) }}
                        className={clsx(
                          'flex items-center gap-3 p-3.5 rounded-xl border-2 text-left transition-all',
                          selected
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:border-brand-300',
                        )}
                      >
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                          <Zap size={14} className="text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                            {p.display_name || p.provider_name || p.name || '—'}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            {p.provider_name || p.type}{p.model_name ? ` · ${p.model_name}` : ''}
                          </p>
                        </div>
                        {selected && <CheckCircle2 size={15} className="text-brand-500 flex-shrink-0" />}
                      </button>
                    )
                  })}
                  <button
                    type="button"
                    onClick={() => { setUseNewProvider(true); setProviderId(savedNewProviderId ?? '') }}
                    className={clsx(
                      'flex items-center gap-3 p-3.5 rounded-xl border-2 border-dashed text-left transition-all',
                      showNewForm
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                        : 'border-gray-300 dark:border-gray-600 hover:border-brand-300',
                    )}
                  >
                    <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-shrink-0">
                      <Plus size={14} className="text-gray-500" />
                    </div>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">Add a new provider</p>
                  </button>
                </div>
              </div>
            )}

            {showNewForm && (
              <div className="card p-5">
                <ProviderSetupForm
                  value={draft}
                  onChange={patchDraft}
                  providerId={savedNewProviderId ?? undefined}
                />
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="secondary" onClick={() => router.push('/app/ai-agent')}>Cancel</Button>
              <Button
                className="flex-1"
                icon={<ChevronRight size={16} />}
                disabled={!canAdvanceProvider}
                loading={saveProviderMut.isPending}
                onClick={handleProviderNext}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 2: Name + repository ──────────────────────────────────── */}
        {!done && step === 1 && (
          <div className="card p-8 space-y-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Name your agent and connect a repository</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                The agent writes code changes and opens pull requests in your GitHub repository.
              </p>
            </div>

            <Input
              label="Agent name"
              required
              placeholder="e.g. Feature Builder"
              value={agent.agentName}
              onChange={e => patchAgent({ agentName: e.target.value })}
            />

            <div className="flex gap-3">
              {[
                { on: true, label: 'Connect a GitHub repo', icon: <Github size={15} /> },
                { on: false, label: 'Skip for now', icon: null },
              ].map(opt => (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => patchAgent({ connectRepo: opt.on })}
                  className={clsx(
                    'flex-1 flex items-center justify-center gap-2 p-3 rounded-xl border-2 text-sm font-semibold transition-all',
                    agent.connectRepo === opt.on
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300'
                      : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-brand-300',
                  )}
                >
                  {opt.icon}{opt.label}
                </button>
              ))}
            </div>

            {agent.connectRepo ? (
              <div className="space-y-4">
                <Input
                  label="Repository URL"
                  required
                  placeholder="https://github.com/yourorg/your-repo"
                  value={agent.repoUrl}
                  onChange={e => patchAgent({ repoUrl: e.target.value })}
                />
                <div className="grid sm:grid-cols-2 gap-4">
                  <Input
                    label="Branch"
                    placeholder="main"
                    value={agent.branch}
                    onChange={e => patchAgent({ branch: e.target.value })}
                  />
                  <Input
                    label="GitHub access token"
                    required
                    type="password"
                    autoComplete="off"
                    placeholder="ghp_... or github_pat_..."
                    value={agent.token}
                    onChange={e => patchAgent({ token: e.target.value })}
                  />
                </div>
                <HintBox>
                  Create the token at GitHub → Settings → Developer settings → Personal access tokens, limited to
                  this one repository with read/write access to contents, pull requests and workflows.
                  GitLab and Bitbucket are not supported yet.
                </HintBox>
              </div>
            ) : (
              <HintBox>
                You can connect a repository later from <strong>Agents</strong>. An agent needs one before it can
                generate code.
              </HintBox>
            )}

            <div className="flex gap-3 pt-2">
              <Button variant="secondary" icon={<ChevronLeft size={16} />} onClick={() => setStep(0)}>Back</Button>
              <Button
                className="flex-1"
                icon={<Sparkles size={16} />}
                disabled={!canCreate}
                loading={createAgentMut.isPending}
                onClick={handleFinish}
              >
                Create my agent
              </Button>
            </div>
          </div>
        )}

        {/* ── Done ───────────────────────────────────────────────────────── */}
        {done && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-gradient-to-br from-green-500 via-brand-500 to-violet-600 p-8 text-white text-center shadow-xl">
              <div className="w-16 h-16 rounded-2xl bg-white/20 border border-white/30 flex items-center justify-center mx-auto">
                <PartyPopper size={28} />
              </div>
              <h2 className="text-2xl font-extrabold mt-4">Your agent is ready!</h2>
              <p className="mt-1 text-green-100 text-sm"><strong>{agent.agentName}</strong> has been created.</p>
              {setupSummary && <p className="mt-2 text-xs text-green-50/90 max-w-sm mx-auto">{setupSummary}</p>}
            </div>

            <div className="card p-5 space-y-2">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">What to do next</p>
              {[
                {
                  href: createdAgentId ? `/app/ai-agent/run?config=${createdAgentId}` : '/app/ai-agent/run',
                  icon: <Sparkles size={16} />, label: 'Generate your first feature',
                  desc: 'Describe what you want built in plain language', primary: true,
                },
                { href: '/app/ai-agent/agents', icon: <Bot size={16} />, label: 'Manage agents', desc: 'Build agent settings and chat assistants', primary: false },
                { href: '/app/ai-agent/providers', icon: <GitBranch size={16} />, label: 'Manage providers', desc: 'Add providers or rotate API keys', primary: false },
              ].map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    'flex items-center gap-4 p-4 rounded-xl border transition-colors',
                    item.primary
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 hover:bg-brand-100 dark:hover:bg-brand-900/30'
                      : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800',
                  )}
                >
                  <div className={clsx(
                    'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
                    item.primary ? 'bg-gradient-to-br from-brand-500 to-violet-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500',
                  )}>
                    {item.icon}
                  </div>
                  <div className="flex-1 text-left">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">{item.label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{item.desc}</p>
                  </div>
                  <ChevronRight size={14} className="text-gray-400" />
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
