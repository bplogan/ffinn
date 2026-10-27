'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiAgentsApi, aiProvidersApi } from '@/lib/api'
import type { AIAgentConfig, AIProvider, PagedResult } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Badge from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import Modal from '@/components/ui/Modal'
import Input, { Select } from '@/components/ui/Input'
import { Plus, Bot, Trash2, Play, Wand2, GitBranch, Settings2, Pencil } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import { isAzureProvider } from '@/lib/aiProviderFormMeta'
import AzureOpenAIFields from '@/components/ai-agent/AzureOpenAIFields'

function agentAzureDeployment(c: AIAgentConfig): string {
  return c.azure_deployment_name?.trim() || ''
}

function providerLabel(p: AIProvider): string {
  return p.display_name || p.provider_name || p.name || 'Provider'
}

function agentModelLabel(c: AIAgentConfig, providers: AIProvider[]): string {
  const linked = c.provider_id ? providers.find(p => p.id === c.provider_id) : undefined
  if (c.provider_id) {
    if (!linked) return 'Linked provider was deleted — edit the agent and choose another'
    return `${providerLabel(linked)}${c.ai_model ? ` · model: ${c.ai_model}` : linked.model_name ? ` · ${linked.model_name}` : ''}`
  }
  const provider = c.ai_provider ?? ''
  if (isAzureProvider(provider)) {
    const deployment = agentAzureDeployment(c) || c.ai_model || '—'
    return `${provider} · deployment: ${deployment} (not linked to a provider)`
  }
  return [provider, c.ai_model].filter(Boolean).join(' / ') || 'No model configured'
}

export default function AIAgentConfigurationsPage() {
  const qc = useQueryClient()
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [editAgent, setEditAgent] = useState<AIAgentConfig | null>(null)
  const [editDeployment, setEditDeployment] = useState('')
  const [editModel, setEditModel] = useState('')
  const [editEndpoint, setEditEndpoint] = useState('')
  const [editProviderId, setEditProviderId] = useState('')
  const [editRepoUrl, setEditRepoUrl] = useState('')

  const { data: configsRaw, isLoading } = useQuery<PagedResult<AIAgentConfig>>({
    queryKey: ['ai-agent-configs'],
    queryFn: () => aiAgentsApi.list({ page: 1, page_size: 100 }) as Promise<PagedResult<AIAgentConfig>>,
  })
  // Assistants are managed from the Agents hub; this page is the build agent's repo/provider settings.
  const configs = (configsRaw?.items ?? []).filter(c => c.kind !== 'assistant')

  const { data: providers } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })
  const providerList = providers ?? []

  const deleteMut = useMutation({
    mutationFn: (id: string) => aiAgentsApi.delete(id),
    onSuccess: () => {
      toast.success('Agent deleted')
      qc.invalidateQueries({ queryKey: ['ai-agent-configs'] })
      setDeleteId(null)
    },
    onError: () => toast.error('Delete failed'),
  })

  const setupMut = useMutation({
    mutationFn: (id: string) => aiAgentsApi.setupRepository(id, {}),
    onSuccess: (data: { success: boolean; steps?: { name: string; success: boolean; detail: string }[] }) => {
      if (data.success) {
        toast.success('Repository CI/CD configured')
      } else {
        const failed = data.steps?.filter(s => !s.success).map(s => s.name).join(', ')
        toast.error(failed ? `Setup incomplete: ${failed}` : 'Setup finished with errors')
      }
      qc.invalidateQueries({ queryKey: ['repo-setup'] })
    },
    onError: () => toast.error('Repository setup failed'),
  })

  const saveMut = useMutation({
    mutationFn: () => {
      if (!editAgent) throw new Error('No agent selected')
      const base = { repository_url: editRepoUrl.trim() || undefined }
      if (editProviderId) {
        const linkedProvider = providerList.find(p => p.id === editProviderId)
        const azureProvider = isAzureProvider(linkedProvider?.provider_name || linkedProvider?.type)
        return aiAgentsApi.update(editAgent.id, {
          ...base,
          provider_id: editProviderId,
          // Optional per-agent model; blank means "use the provider's model".
          ai_model: azureProvider ? undefined : editModel.trim(),
        })
      }
      const azure = isAzureProvider(editAgent.ai_provider)
      return aiAgentsApi.update(editAgent.id, {
        ...base,
        azure_deployment_name: azure ? editDeployment.trim() || null : undefined,
        azure_openai_endpoint: azure ? editEndpoint.trim() || null : undefined,
        ai_model: azure ? (editModel.trim() || editDeployment.trim()) : editAgent.ai_model,
      })
    },
    onSuccess: () => {
      toast.success('Agent saved')
      qc.invalidateQueries({ queryKey: ['ai-agent-configs'] })
      qc.invalidateQueries({ queryKey: ['ai-agents'] })
      setEditAgent(null)
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Save failed')
    },
  })

  const openEdit = (c: AIAgentConfig) => {
    setEditAgent(c)
    setEditRepoUrl(c.repository_url ?? '')
    setEditProviderId(c.provider_id ?? '')
    setEditDeployment(c.azure_deployment_name ?? c.ai_model ?? '')
    setEditModel(c.ai_model ?? '')
    setEditEndpoint(c.azure_openai_endpoint ?? c.ai_endpoint ?? '')
  }

  return (
    <div className="space-y-4">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'Agents', href: '/app/ai-agent/agents' }, { label: 'Build agent settings' }]} />
      <PageHeader
        title="Build agent settings"
        subtitle="Repository and AI provider settings for code generation. Chat assistants live under Agents."
        actions={
          <Link href="/app/ai-agent/wizard">
            <Button icon={<Wand2 size={15} />}>Set up with wizard</Button>
          </Link>
        }
      />

      <div className="card overflow-hidden">
        {isLoading ? (
          <LoadingSpinner className="my-8" />
        ) : configs.length === 0 ? (
          <EmptyState
            icon={<Bot size={32} />}
            title="No agents yet"
            description="Run the setup wizard to connect a repository and AI provider."
            action={
              <Link href="/app/ai-agent/wizard">
                <Button icon={<Plus size={14} />}>Open wizard</Button>
              </Link>
            }
          />
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {configs.map(c => (
              <div key={c.id} className="p-4 flex flex-wrap items-center gap-4 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/40 flex items-center justify-center flex-shrink-0">
                  <Bot size={18} className="text-purple-600 dark:text-purple-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white">{c.name ?? c.id}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 truncate">
                    <GitBranch size={12} className="flex-shrink-0" />
                    {c.repository_url || 'No repository'}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">{agentModelLabel(c, providerList)}</p>
                  {!c.provider_id && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      Uses its own copy of the API key — edit the agent and pick a provider so key changes apply here.
                    </p>
                  )}
                </div>
                <Badge variant={c.is_active ? 'success' : 'gray'}>{c.is_active ? 'Active' : 'Inactive'}</Badge>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={() => openEdit(c)}>
                    Edit
                  </Button>
                  {c.repository_url && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Settings2 size={13} />}
                      loading={setupMut.isPending && setupMut.variables === c.id}
                      onClick={() => setupMut.mutate(c.id)}
                    >
                      Setup CI
                    </Button>
                  )}
                  <Link href={`/app/ai-agent/run?config=${c.id}`}>
                    <Button size="sm" variant="secondary" icon={<Play size={13} />}>Generate</Button>
                  </Link>
                  {!c.is_default && (
                    <button
                      type="button"
                      onClick={() => setDeleteId(c.id)}
                      className="p-2 text-error-500 hover:text-error-600 rounded-lg hover:bg-error-50 dark:hover:bg-error-900/20"
                      aria-label="Delete agent"
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!editAgent}
        onClose={() => setEditAgent(null)}
        title={`Edit agent — ${editAgent?.name ?? 'Agent'}`}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditAgent(null)}>Cancel</Button>
            <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending}>Save</Button>
          </>
        }
      >
        {editAgent && (
          <div className="space-y-4">
            <Input
              label="Repository URL"
              value={editRepoUrl}
              onChange={e => setEditRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              hint="Must match an existing GitHub repo your access token can reach."
            />

            <div>
              <Select
                label="AI provider"
                value={editProviderId}
                onChange={e => setEditProviderId(e.target.value)}
              >
                <option value="">{editAgent.provider_id ? 'Select a provider' : 'Keep this agent’s own settings'}</option>
                {providerList.map(p => (
                  <option key={p.id} value={p.id}>
                    {providerLabel(p)}{p.model_name ? ` — ${p.model_name}` : ''}
                  </option>
                ))}
              </Select>
              <Link href="/app/ai-agent/providers" className="text-xs text-brand-600 dark:text-brand-400 hover:underline">
                Add or edit providers →
              </Link>
            </div>

            {editProviderId ? (
              !isAzureProvider(providerList.find(p => p.id === editProviderId)?.provider_name) && (
                <Input
                  label="Model (optional)"
                  value={editModel}
                  onChange={e => setEditModel(e.target.value)}
                  placeholder={providerList.find(p => p.id === editProviderId)?.model_name || 'Provider default'}
                  hint="Leave blank to use the model set on the provider."
                />
              )
            ) : (
              isAzureProvider(editAgent.ai_provider) && (
                <>
                  <Input
                    label="Azure endpoint"
                    value={editEndpoint}
                    onChange={e => setEditEndpoint(e.target.value)}
                    placeholder="https://your-resource.openai.azure.com/"
                  />
                  <AzureOpenAIFields
                    endpoint={editEndpoint}
                    apiKey=""
                    deployment={editDeployment}
                    model={editModel}
                    onDeploymentChange={setEditDeployment}
                    onModelChange={setEditModel}
                  />
                </>
              )
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending}
        title="Delete agent"
        message="Remove this agent? Existing generation history is kept."
        confirmLabel="Delete"
      />
    </div>
  )
}
