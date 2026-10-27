'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { ArrowRight, Lock, MessageSquare, Pencil, Plus, Trash2, Zap } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import AgentAvatar from '@/components/ai-agent/AgentAvatar'
import AgentEditorModal from '@/components/ai-agent/AgentEditorModal'
import { aiAgentsApi, aiProvidersApi } from '@/lib/api'
import type { AIAgentConfig, AIProvider, PagedResult } from '@/types'

export default function AgentsHubPage() {
  const qc = useQueryClient()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<AIAgentConfig | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<AIAgentConfig | null>(null)

  const { data, isLoading } = useQuery<PagedResult<AIAgentConfig>>({
    queryKey: ['ai-agent-configs'],
    queryFn: () => aiAgentsApi.list({ page: 1, page_size: 100 }) as Promise<PagedResult<AIAgentConfig>>,
  })
  const { data: providers } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })
  const agents = data?.items ?? []
  const build = agents.find(a => a.kind !== 'assistant' && a.is_default) ?? agents.find(a => a.kind !== 'assistant')
  const assistants = agents.filter(a => a.kind === 'assistant')
  const providerFor = (a: AIAgentConfig) => providers?.find(p => p.id === a.provider_id)

  const deleteMut = useMutation({
    mutationFn: (id: string) => aiAgentsApi.delete(id),
    onSuccess: () => {
      toast.success('Agent removed')
      qc.invalidateQueries({ queryKey: ['ai-agent-configs'] })
      setDeleteTarget(null)
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || 'Delete failed')
    },
  })

  const openCreate = () => { setEditing(null); setEditorOpen(true) }
  const openEdit = (a: AIAgentConfig) => { setEditing(a); setEditorOpen(true) }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        subtitle="The build agent ships code. Add assistants for everything else, each with its own instructions and your own AI keys."
        actions={<Button icon={<Plus size={16} />} onClick={openCreate}>New agent</Button>}
      />

      {isLoading ? <LoadingSpinner fullPage /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {/* Build agent: always first, cannot be removed */}
          {build && (
            <div className="group relative overflow-hidden rounded-2xl border border-brand-200/70 dark:border-violet-800/50 bg-gradient-to-br from-brand-50 via-white to-violet-50 dark:from-brand-950/40 dark:via-gray-900 dark:to-violet-950/30 p-5 shadow-sm hover:shadow-lg transition-shadow">
              <Link href={`/app/ai-agent/run?config=${build.id}`} className="absolute inset-0" aria-label="Open the build agent" />
              <div className="pointer-events-none absolute -top-10 -right-10 w-36 h-36 rounded-full bg-violet-500/10 blur-2xl" />
              <div className="pointer-events-none relative flex items-start gap-4">
                <AgentAvatar kind="build" name={build.name} size="lg" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-gray-900 dark:text-white truncate">{build.name || 'Build Agent'}</h3>
                    <span className="inline-flex items-center gap-1 rounded-full bg-gray-900/5 dark:bg-white/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300">
                      <Lock size={9} /> Framework
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {build.description || 'Turns plain-English feature requests into code, pull requests and deployments.'}
                  </p>
                </div>
              </div>
              <div className="pointer-events-none relative mt-5 flex items-center justify-between text-xs">
                <span className="text-gray-500 dark:text-gray-400 truncate">
                  {build.repository_url ? build.repository_url.replace(/^https?:\/\/(www\.)?github\.com\//, '') : 'No repository connected yet'}
                </span>
                <span className="inline-flex items-center gap-1 font-semibold text-brand-600 dark:text-brand-400 group-hover:gap-2 transition-all">
                  Generate code <ArrowRight size={13} />
                </span>
              </div>
              <div className="relative mt-3 flex gap-3 text-xs">
                <Link href="/app/ai-agent/builder" className="text-gray-500 hover:text-brand-600 dark:hover:text-brand-400 hover:underline">Settings</Link>
                <Link href="/app/ai-agent/history" className="text-gray-500 hover:text-brand-600 dark:hover:text-brand-400 hover:underline">History</Link>
              </div>
            </div>
          )}

          {assistants.map(a => {
            const p = providerFor(a)
            return (
              <div key={a.id} className="group relative rounded-2xl border border-gray-200/80 dark:border-gray-700/60 bg-white dark:bg-gray-900 p-5 shadow-sm hover:shadow-lg hover:border-brand-200 dark:hover:border-brand-800 transition-all">
                <Link href={`/app/ai-agent/agents/${a.id}`} className="absolute inset-0 rounded-2xl" aria-label={`Open ${a.name}`} />
                <div className="relative pointer-events-none flex items-start gap-4">
                  <AgentAvatar name={a.name} avatar={a.avatar} size="lg" />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-bold text-gray-900 dark:text-white truncate">{a.name}</h3>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 line-clamp-2 min-h-[2.5rem]">
                      {a.description || 'No description yet.'}
                    </p>
                  </div>
                </div>
                <div className="relative mt-5 flex items-center justify-between text-xs">
                  <span className={clsx('inline-flex items-center gap-1 truncate', p ? 'text-gray-500 dark:text-gray-400' : 'text-amber-600')}>
                    <Zap size={11} />
                    {p ? `${p.display_name || p.provider_name}${a.ai_model || p.model_name ? ` · ${a.ai_model || p.model_name}` : ''}` : 'Provider missing'}
                  </span>
                  <span className="pointer-events-none inline-flex items-center gap-1 font-semibold text-brand-600 dark:text-brand-400 group-hover:gap-2 transition-all">
                    <MessageSquare size={13} /> Chat
                  </span>
                </div>
                <div className="relative mt-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button type="button" onClick={() => openEdit(a)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white">
                    <Pencil size={12} /> Edit
                  </button>
                  <button type="button" onClick={() => setDeleteTarget(a)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-error-50 dark:hover:bg-error-900/20 hover:text-error-600">
                    <Trash2 size={12} /> Remove
                  </button>
                </div>
              </div>
            )
          })}

          {/* New agent tile */}
          <button
            type="button"
            onClick={openCreate}
            className="flex min-h-[180px] flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-gray-300 dark:border-gray-700 text-gray-500 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50/40 dark:hover:bg-brand-900/10 transition-colors"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 dark:bg-gray-800">
              <Plus size={22} />
            </span>
            <span className="text-sm font-semibold">Create an agent</span>
            <span className="text-xs text-gray-400 px-6 text-center">Support, research, writing, code review — give it a job and a key.</span>
          </button>
        </div>
      )}

      <AgentEditorModal open={editorOpen} onClose={() => setEditorOpen(false)} agent={editing} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
        loading={deleteMut.isPending}
        title={`Remove ${deleteTarget?.name ?? 'agent'}`}
        message="Its conversations and attachments will be deleted. The provider and its API key stay."
        confirmLabel="Remove"
      />
    </div>
  )
}
