'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiAgentsApi, aiGenerationsApi, aiPromptApi, aiProvidersApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import type { AIAgentConfig, AIProvider, AIGeneration, GenerationProgressEvent, GenerationTargetScope } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Button from '@/components/ui/Button'
import { Select, TextArea } from '@/components/ui/Input'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import toast from 'react-hot-toast'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import GenerationPipeline from '@/components/ai-agent/GenerationPipeline'
import GenerationActivity from '@/components/ai-agent/GenerationActivity'
import GenerationHelpGuide from '@/components/ai-agent/GenerationHelpGuide'
import HelpPopover from '@/components/ui/HelpPopover'
import {
  ACTION_HELP,
  FORM_FIELD_HELP,
  GENERATION_PAGE_HELP,
} from '@/lib/generationHelp'
import {
  TERMINAL_STATUSES,
  FAILED_STATUSES,
  getUserStatusLabel,
  getUserStatusDescription,
  statusBadgeVariant,
} from '@/lib/generationStatus'
import {
  Zap, Play, ExternalLink, RefreshCcw, XCircle, GitBranch,
  Rocket, RotateCcw, ChevronDown, ChevronUp, FileCode2,
  CheckCircle2, Loader2, AlertCircle, AlertTriangle, Sparkles,
} from 'lucide-react'

function fieldLabel(text: string, help: { title: string; body: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      {text}
      <HelpPopover label={`Help: ${help.title}`} title={help.title} size={14}>
        <p>{help.body}</p>
      </HelpPopover>
    </span>
  )
}

function actionHelp(key: keyof typeof ACTION_HELP) {
  const help = ACTION_HELP[key]
  return (
    <HelpPopover label={`Help: ${help.title}`} title={help.title} size={14}>
      <p>{help.body}</p>
      <p>
        <span className="font-medium text-gray-700 dark:text-gray-200">When to use: </span>
        {help.whenToUse}
      </p>
    </HelpPopover>
  )
}

// ── Generated files viewer ────────────────────────────────────────────────────
function GeneratedFilesViewer({ files }: { files: Record<string, string> }) {
  const [openFile, setOpenFile] = useState<string | null>(null)
  const paths = Object.keys(files).sort()

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
        <FileCode2 size={14} className="text-gray-500" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {paths.length} generated file{paths.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        {paths.map(path => (
          <div key={path}>
            <button
              onClick={() => setOpenFile(openFile === path ? null : path)}
              className="w-full flex items-center justify-between px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-left"
            >
              <span className="text-xs font-mono text-brand-600 dark:text-brand-400 truncate">{path}</span>
              {openFile === path ? <ChevronUp size={14} className="text-gray-400 flex-shrink-0" /> : <ChevronDown size={14} className="text-gray-400 flex-shrink-0" />}
            </button>
            {openFile === path && (
              <pre className="px-4 pb-4 text-xs font-mono text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto">
                {files[path]}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function RunGenerationPage() {
  const { user, token: authToken } = useAuth()
  const qc = useQueryClient()
  const searchParams = useSearchParams()

  const [configId, setConfigId]       = useState('')
  const [featureName, setFeatureName] = useState('')
  const [targetScope, setTargetScope] = useState<GenerationTargetScope>('tenant')
  const [prompt, setPrompt]           = useState('')
  const [providerOverride, setProviderOverride] = useState('')
  const [modelOverride, setModelOverride]       = useState('')

  const [activeGenId, setActiveGenId]       = useState<string | null>(null)
  const [progressEvents, setProgressEvents] = useState<GenerationProgressEvent[]>([])
  const [showFiles, setShowFiles]           = useState(false)
  const [showActivity, setShowActivity]     = useState(false)
  const [showRetryConfirm, setShowRetryConfirm] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const formPrefilledRef = useRef<string | null>(null)

  const { data: configsRaw } = useQuery({
    queryKey: ['ai-agent-configs'],
    queryFn: () => aiAgentsApi.list({ page: 1, page_size: 100 }),
  })
  const configs = ((configsRaw as unknown as { items?: AIAgentConfig[] })?.items ?? []) as AIAgentConfig[]

  const { data: savedProviders } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })

  useEffect(() => {
    const fromQuery = searchParams.get('config')
    if (fromQuery) setConfigId(fromQuery)
  }, [searchParams])

  useEffect(() => {
    const genId = searchParams.get('gen')
    if (genId) setActiveGenId(genId)
  }, [searchParams])

  const optimizeMut = useMutation({
    mutationFn: () => aiPromptApi.optimize(prompt) as Promise<{ optimized: string; changes_applied?: string[] }>,
    onSuccess: (res) => {
      setPrompt(res.optimized)
      const n = res.changes_applied?.length ?? 0
      toast.success(n ? `Prompt optimized (${n} improvement${n === 1 ? '' : 's'})` : 'Prompt optimized')
    },
    onError: () => toast.error('Could not optimize prompt'),
  })

  const { data: generationRaw, refetch: refetchGen } = useQuery<AIGeneration>({
    queryKey: ['ai-generation', activeGenId],
    queryFn: () => aiGenerationsApi.get(activeGenId!) as Promise<AIGeneration>,
    enabled: !!activeGenId,
    refetchInterval: (query) => {
      const gen = query.state.data as AIGeneration | undefined
      if (!gen) return 2000
      return TERMINAL_STATUSES.includes(gen.status as (typeof TERMINAL_STATUSES)[number]) ? false : 3000
    },
  })
  const generation = generationRaw as AIGeneration | undefined

  const invalidateProgressQueries = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['ai-history'] })
    qc.invalidateQueries({ queryKey: ['ai-generations-in-progress'] })
  }, [qc])

  const connectWebSocket = useCallback(async (tenantId: string, genId: string) => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl   = apiBase.replace(/^http/, 'ws') + `/api/aiagent/ws/${tenantId}`
    try {
      const { ticket } = await aiAgentsApi.wsTicket() as { ticket: string }
      const ws = new WebSocket(wsUrl)
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', ticket }))
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'ai_agent_progress' && msg.generationId === genId) {
            setProgressEvents(prev => [
              ...prev,
              {
                id: crypto.randomUUID(),
                event_type: 'progress',
                message: msg.message,
                step: msg.status,
                created_at: msg.timestamp ?? new Date().toISOString(),
              },
            ])
            refetchGen()
          }
        } catch { /* ignore */ }
      }
      ws.onerror = () => { toast('Live updates unavailable — refreshing automatically', { icon: '⚠️' }) }
      wsRef.current = ws
    } catch { /* WebSocket not available */ }
  }, [refetchGen])

  const loadProgressEvents = useCallback(async (genId: string) => {
    try {
      const res = (await aiGenerationsApi.progress(genId)) as { events?: GenerationProgressEvent[] }
      if (res.events?.length) setProgressEvents(res.events)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    if (!generation || formPrefilledRef.current === generation.id) return
    formPrefilledRef.current = generation.id
    const cfgId = generation.config_id ?? generation.configuration_id
    if (cfgId) setConfigId(cfgId)
    if (generation.feature_name) setFeatureName(generation.feature_name)
    if (generation.user_prompt) setPrompt(generation.user_prompt)
    if (generation.target_scope) setTargetScope(generation.target_scope)
  }, [generation])

  useEffect(() => {
    if (!activeGenId || !generation) return
    if (progressEvents.length === 0) loadProgressEvents(activeGenId)
    const tenantId = user?.tenantId
    if (tenantId && !TERMINAL_STATUSES.includes(generation.status as (typeof TERMINAL_STATUSES)[number])) {
      connectWebSocket(tenantId, activeGenId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGenId, generation?.id, generation?.status])

  const startGeneration = useCallback(async (params: {
    config_id: string
    feature_name: string
    prompt: string
    target_scope?: GenerationTargetScope
    provider_override?: string
    model_override?: string
  }) => {
    const gen = (await aiGenerationsApi.create(params)) as AIGeneration
    setActiveGenId(gen.id)
    setProgressEvents([])
    setShowFiles(false)
    setShowActivity(false)
    formPrefilledRef.current = null
    toast.success('Got it — we are working on your feature')

    try {
      await aiGenerationsApi.process(gen.id)
    } catch { /* scheduler may pick it up */ }

    await loadProgressEvents(gen.id)
    const tenantId = user?.tenantId
    if (tenantId) connectWebSocket(tenantId, gen.id)
    invalidateProgressQueries()
    return gen
  }, [authToken, connectWebSocket, invalidateProgressQueries, loadProgressEvents, user?.tenantId])

  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!configId)    throw new Error('Select an agent')
      if (!featureName) throw new Error('Enter a feature name')
      if (!prompt)      throw new Error('Describe what you want built')

      return startGeneration({
        config_id:         configId,
        feature_name:      featureName,
        prompt,
        target_scope:      targetScope,
        provider_override: providerOverride || undefined,
        model_override:    modelOverride || undefined,
      })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const retryMutation = useMutation({
    mutationFn: async (source: AIGeneration) => {
      const cfgId = source.config_id ?? source.configuration_id ?? configId
      if (!cfgId) throw new Error('No agent configuration found for this run')
      return startGeneration({
        config_id:         cfgId,
        feature_name:      source.feature_name ?? featureName,
        prompt:            source.user_prompt ?? prompt,
        target_scope:      source.target_scope ?? targetScope,
        provider_override: (source.provider_override ?? providerOverride) || undefined,
        model_override:    (source.model_override ?? modelOverride) || undefined,
      })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const handleRetryConfirm = () => {
    if (!generation || retryMutation.isPending || submitMutation.isPending) return
    setShowRetryConfirm(false)
    retryMutation.mutate(generation)
  }

  useEffect(() => {
    if (generation && TERMINAL_STATUSES.includes(generation.status as (typeof TERMINAL_STATUSES)[number])) {
      wsRef.current?.close()
      wsRef.current = null
      invalidateProgressQueries()
    }
  }, [generation?.status, invalidateProgressQueries])

  useEffect(() => () => { wsRef.current?.close() }, [])

  const releaseMutation = useMutation({
    mutationFn: () => aiGenerationsApi.release(activeGenId!),
    onSuccess: () => { toast.success('Release started'); refetchGen(); invalidateProgressQueries() },
    onError: () => toast.error('Release failed'),
  })

  const revertMutation = useMutation({
    mutationFn: () => aiGenerationsApi.revert(activeGenId!),
    onSuccess: () => { toast.success('Reverted'); refetchGen(); invalidateProgressQueries() },
    onError: () => toast.error('Revert failed'),
  })

  const cancelMutation = useMutation({
    mutationFn: () => aiGenerationsApi.cancel(activeGenId!),
    onSuccess: () => { toast.success('Cancelled'); refetchGen(); invalidateProgressQueries() },
    onError: () => toast.error('Cancel failed'),
  })

  const stagingMutation = useMutation({
    mutationFn: () => aiGenerationsApi.deployStaging(activeGenId!),
    onSuccess: () => { toast.success('Staging preview started'); refetchGen(); invalidateProgressQueries() },
    onError: () => toast.error('Deploy failed'),
  })

  const status       = generation?.status ?? ''
  const isInProgress = !!activeGenId && (!TERMINAL_STATUSES.includes(status as (typeof TERMINAL_STATUSES)[number]) || submitMutation.isPending || retryMutation.isPending) && (!!status || submitMutation.isPending || retryMutation.isPending)
  const isReady      = status === 'Ready' || status === 'Staging'
  const isReleased   = status === 'Released'
  const isReleasing  = status === 'Releasing'
  const isFailed     = FAILED_STATUSES.includes(status as (typeof FAILED_STATUSES)[number])
  const canRevert    = ['Ready', 'Staging', 'Building', 'Released'].includes(status)
  const canCancel    = !!activeGenId && !['Released', 'Reverted', 'Failed'].includes(status)
  const generatedFiles = generation?.generated_files as Record<string, string> | undefined
  const viewingGeneration = !!activeGenId && (generation || submitMutation.isPending || retryMutation.isPending)
  const selectedAgent = configs.find(c => c.id === configId)

  const requestForm = (
    <div className="card p-6 space-y-5">
      <h2 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <Zap size={16} className="text-brand-500" />
        {viewingGeneration ? 'Your request' : 'Describe your feature'}
      </h2>

      {!viewingGeneration && (
        <p className="text-sm text-gray-500 dark:text-gray-400 -mt-2">
          Tell us what you want in plain language. We will write the code, open a pull request, and deploy a staging app you can test before going live.
        </p>
      )}

      <Select
        label={fieldLabel('Agent', FORM_FIELD_HELP.agent)}
        value={configId}
        onChange={e => setConfigId(e.target.value)}
        disabled={viewingGeneration && isInProgress}
      >
        <option value="">Select an agent…</option>
        {configs.map(c => (
          <option key={c.id} value={c.id}>
            {c.name ?? c.id}
          </option>
        ))}
      </Select>

      {configs.length === 0 && !viewingGeneration && (
        <div className="p-3 rounded-lg bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 flex items-start gap-2">
          <AlertTriangle size={15} className="text-warning-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-warning-700 dark:text-warning-400">
            No agents found.{' '}
            <a href="/app/ai-agent/wizard" className="underline font-medium">Set up an agent</a> first.
          </p>
        </div>
      )}

      <Select
        label={fieldLabel('Who is this for?', FORM_FIELD_HELP.audience)}
        value={targetScope}
        onChange={e => setTargetScope(e.target.value as GenerationTargetScope)}
        disabled={viewingGeneration && isInProgress}
      >
        <option value="tenant">Tenant / customer app</option>
        <option value="host">Host / platform admin</option>
      </Select>
      {!viewingGeneration && (
        <p className="text-xs text-gray-500 dark:text-gray-400 -mt-2">
          Tenant features show in organization menus. Host features show for platform admins like the default admin.
        </p>
      )}

      <Input
        label={fieldLabel('Feature name', FORM_FIELD_HELP.featureName)}
        placeholder="e.g. Product inventory tracker"
        value={featureName}
        onChange={e => setFeatureName(e.target.value)}
        hint={viewingGeneration ? undefined : 'A short name for this feature — used in GitHub and staging'}
        disabled={viewingGeneration && isInProgress}
      />

      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {fieldLabel('What should we build?', FORM_FIELD_HELP.prompt)}
        </span>
        {!viewingGeneration && (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            icon={<Sparkles size={13} />}
            loading={optimizeMut.isPending}
            disabled={!prompt.trim()}
            onClick={() => optimizeMut.mutate()}
          >
            Improve wording
          </Button>
        )}
      </div>
      <TextArea
        label=""
        rows={viewingGeneration ? 4 : 6}
        placeholder={viewingGeneration ? undefined : `Describe the feature in everyday language.\n\nExample: "I need a page where my team can track inventory — each item has a name, SKU, quantity, and price. They should be able to add, edit, and delete items."`}
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        disabled={viewingGeneration && isInProgress}
      />

      {!viewingGeneration && (
        <>
          <details className="group">
            <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 select-none flex items-center gap-1">
              <ChevronDown size={14} className="group-open:rotate-180 transition-transform" />
              Advanced options
            </summary>
            <div className="grid grid-cols-2 gap-4 mt-3">
              <Select
                label="Provider override"
                value={providerOverride}
                onChange={e => setProviderOverride(e.target.value)}
              >
                <option value="">Use the agent&apos;s provider</option>
                {(savedProviders ?? []).map(p => (
                  <option key={p.id} value={p.id}>
                    {p.display_name || p.provider_name || p.name}{p.model_name ? ` — ${p.model_name}` : ''}
                  </option>
                ))}
              </Select>
              <Input
                label="Model override"
                placeholder="Leave blank for default"
                value={modelOverride}
                onChange={e => setModelOverride(e.target.value)}
              />
            </div>
          </details>

          <Button
            icon={<Play size={15} />}
            loading={submitMutation.isPending}
            disabled={!configId || !featureName || !prompt || isInProgress}
            onClick={() => submitMutation.mutate()}
          >
            Generate code
          </Button>
        </>
      )}
    </div>
  )

  return (
    <div className="space-y-6 max-w-4xl">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'Generate Code' }]} />
      <PageHeader
        title="Generate Code"
        subtitle="Describe what you need — we deploy a full staging preview (app + API) before production release"
        actions={
          <HelpPopover label="Help: how code generation works" title={GENERATION_PAGE_HELP.title}>
            {GENERATION_PAGE_HELP.body.map(line => (
              <p key={line}>{line}</p>
            ))}
          </HelpPopover>
        }
      />

      {/* ── Status panel (top when viewing a generation) ─────────────────── */}
      {viewingGeneration && (
        <div className="card p-6 space-y-5">
          {(submitMutation.isPending || retryMutation.isPending) && !generation && (
            <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
              <Loader2 size={18} className="animate-spin text-brand-500" />
              Starting your request…
            </div>
          )}

          {generation && (
            <>
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div className="space-y-1">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    {isInProgress && <Loader2 size={18} className="animate-spin text-brand-500" />}
                    {isReady && !isInProgress && <CheckCircle2 size={18} className="text-success-500" />}
                    {isFailed && <AlertCircle size={18} className="text-error-500" />}
                    {generation.feature_name ?? 'Your feature'}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {getUserStatusDescription(status)}
                  </p>
                </div>
                <Badge variant={statusBadgeVariant(status)}>
                  {getUserStatusLabel(status)}
                </Badge>
              </div>

              <GenerationHelpGuide status={status} />

              <GenerationPipeline status={status} />

              {generation.error_message && (
                <div className="p-3 rounded-lg bg-error-50 dark:bg-error-900/20 border border-error-200 dark:border-error-800 flex items-start gap-2">
                  <AlertCircle size={15} className="text-error-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-error-700 dark:text-error-400">{generation.error_message}</p>
                </div>
              )}

              {progressEvents.length > 0 && (
                <div>
                  <button
                    type="button"
                    onClick={() => setShowActivity(v => !v)}
                    className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
                  >
                    {showActivity ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    {showActivity ? 'Hide' : 'Show'} activity ({progressEvents.length})
                  </button>
                  {(showActivity || isInProgress) && (
                    <div className="mt-2">
                      <GenerationActivity events={progressEvents} collapsed={!showActivity && isInProgress} />
                    </div>
                  )}
                </div>
              )}

              {((generation.pr_url ?? generation.pull_request_url) || generation.staging_frontend_url || generation.staging_url || generation.branch_name) && (
                <div className="flex flex-wrap gap-4">
                  {(generation.pr_url ?? generation.pull_request_url) && (
                    <div className="flex items-center gap-1">
                      <a
                        href={(generation.pr_url ?? generation.pull_request_url)!}
                        target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1.5 text-sm text-brand-600 dark:text-brand-400 hover:underline"
                      >
                        <GitBranch size={14} />
                        Review pull request #{generation.pr_number ?? generation.pull_request_number}
                        <ExternalLink size={12} />
                      </a>
                      {actionHelp('pullRequest')}
                    </div>
                  )}
                  {generation.staging_frontend_url && (
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-1">
                        <a
                          href={generation.staging_frontend_url}
                          target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-1.5 text-sm text-success-600 dark:text-success-400 hover:underline font-medium"
                        >
                          <Rocket size={14} />
                          Open staging app
                          <ExternalLink size={12} />
                        </a>
                        {actionHelp('stagingApp')}
                      </div>
                      <span className="text-xs text-gray-400 pl-5">
                        Full app preview — test before releasing to production
                      </span>
                    </div>
                  )}
                  {generation.staging_url && (
                    <a
                      href={`${generation.staging_url.replace(/\/$/, '')}/docs`}
                      target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:underline"
                    >
                      API docs
                      <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-100 dark:border-gray-700">
                {isReady && !isReleasing && (
                  <>
                    <div className="flex items-center gap-1">
                      <Button
                        icon={<Rocket size={14} />}
                        loading={releaseMutation.isPending}
                        onClick={() => releaseMutation.mutate()}
                      >
                        Release to production
                      </Button>
                      {actionHelp('release')}
                    </div>
                    {!generation.staging_url && (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="secondary"
                          icon={<Play size={14} />}
                          loading={stagingMutation.isPending}
                          onClick={() => stagingMutation.mutate()}
                        >
                          Deploy staging preview
                        </Button>
                        {actionHelp('staging')}
                      </div>
                    )}
                  </>
                )}
                {canRevert && !isReleasing && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="danger"
                      icon={<RotateCcw size={14} />}
                      loading={revertMutation.isPending}
                      onClick={() => revertMutation.mutate()}
                    >
                      {status === 'Released' ? 'Revert release' : 'Revert'}
                    </Button>
                    {actionHelp(status === 'Released' ? 'revertReleased' : 'revert')}
                  </div>
                )}
                {canCancel && isInProgress && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="secondary"
                      icon={<XCircle size={14} />}
                      loading={cancelMutation.isPending}
                      onClick={() => cancelMutation.mutate()}
                    >
                      Cancel
                    </Button>
                    {actionHelp('cancel')}
                  </div>
                )}
                {isFailed && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="secondary"
                      icon={<RefreshCcw size={14} />}
                      loading={retryMutation.isPending}
                      disabled={retryMutation.isPending || submitMutation.isPending}
                      onClick={() => setShowRetryConfirm(true)}
                    >
                      Try again
                    </Button>
                    {actionHelp('retry')}
                  </div>
                )}
                <Button
                  variant="ghost"
                  icon={<RefreshCcw size={14} />}
                  onClick={() => refetchGen()}
                  title="Refresh status"
                />
              </div>

              {generatedFiles && Object.keys(generatedFiles).length > 0 && (
                <div>
                  <button
                    onClick={() => setShowFiles(v => !v)}
                    className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                  >
                    <FileCode2 size={15} />
                    {showFiles ? 'Hide' : 'View'} generated files ({Object.keys(generatedFiles).length})
                    {showFiles ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {showFiles && (
                    <div className="mt-3">
                      <GeneratedFilesViewer files={generatedFiles} />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Request form (bottom when viewing; top when starting fresh) ── */}
      {viewingGeneration ? (
        <details className="group card overflow-hidden">
          <summary className="cursor-pointer p-4 flex items-center justify-between gap-2 select-none hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
            <div className="flex items-center gap-2 min-w-0">
              <Zap size={15} className="text-brand-500 flex-shrink-0" />
              <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                Original request: {featureName || generation?.feature_name || 'Untitled'}
              </span>
              {selectedAgent && (
                <span className="text-xs text-gray-400 hidden sm:inline">· {selectedAgent.name}</span>
              )}
            </div>
            <ChevronDown size={16} className="text-gray-400 group-open:rotate-180 transition-transform flex-shrink-0" />
          </summary>
          <div className="px-6 pb-6 pt-2 border-t border-gray-100 dark:border-gray-700 space-y-4">
            {selectedAgent && (
              <p className="text-sm text-gray-500">Agent: <span className="text-gray-700 dark:text-gray-300">{selectedAgent.name}</span></p>
            )}
            {featureName && (
              <p className="text-sm text-gray-500">Feature: <span className="text-gray-700 dark:text-gray-300">{featureName}</span></p>
            )}
            {prompt && (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Description</p>
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{prompt}</p>
              </div>
            )}
            {!isInProgress && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setActiveGenId(null)
                  setProgressEvents([])
                  formPrefilledRef.current = null
                }}
              >
                Start a new request
              </Button>
            )}
          </div>
        </details>
      ) : (
        requestForm
      )}

      <ConfirmDialog
        open={showRetryConfirm}
        onClose={() => setShowRetryConfirm(false)}
        onConfirm={handleRetryConfirm}
        title="Try again?"
        message="Start a new run with the same description?"
        confirmLabel="Try again"
        confirmVariant="primary"
      />
    </div>
  )
}
