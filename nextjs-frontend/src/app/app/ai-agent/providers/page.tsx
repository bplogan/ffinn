'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiProvidersApi } from '@/lib/api'
import type { AIProvider } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { Plus, Pencil, Trash2, Zap, CheckCircle2, TestTube } from 'lucide-react'
import toast from 'react-hot-toast'
import { isAzureProvider, normalizeProviderType } from '@/lib/aiProviderFormMeta'
import ProviderSetupForm, {
  EMPTY_PROVIDER_DRAFT,
  providerDraftReady,
  providerDraftToPayload,
  type ProviderDraft,
} from '@/components/ai-agent/ProviderSetupForm'

function providerExtra(p: AIProvider): Record<string, string> {
  const raw = p.extra_config
  return raw && typeof raw === 'object' ? raw as Record<string, string> : {}
}

function providerToDraft(p: AIProvider): ProviderDraft {
  const extra = providerExtra(p)
  const type = normalizeProviderType(p.provider_name || p.type)
  const azure = isAzureProvider(type)
  return {
    type,
    name: p.display_name ?? p.name ?? '',
    apiKey: '',
    baseUrl: p.endpoint_url || p.endpoint || '',
    deployment: extra.deployment_name ?? p.deployment_name ?? (azure ? p.model_name ?? '' : ''),
    model: azure ? (extra.model ?? p.model_name ?? '') : (p.model_name ?? ''),
  }
}

export default function AIProvidersPage() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<AIProvider | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)

  const { data: providers, isLoading } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })

  const [draft, setDraft] = useState<ProviderDraft>(EMPTY_PROVIDER_DRAFT)
  const patchDraft = (patch: Partial<ProviderDraft>) => setDraft(d => ({ ...d, ...patch }))

  const openCreate = () => {
    setEditItem(null)
    setDraft(EMPTY_PROVIDER_DRAFT)
    setModalOpen(true)
  }

  const openEdit = async (p: AIProvider) => {
    try {
      const full = (await aiProvidersApi.get(p.id)) as AIProvider
      setEditItem(full)
      setDraft(providerToDraft(full))
    } catch {
      setEditItem(p)
      setDraft(providerToDraft(p))
      toast.error('Could not refresh provider details — showing cached data')
    }
    setModalOpen(true)
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = providerDraftToPayload(draft)
      return editItem
        ? aiProvidersApi.update(editItem.id, payload)
        : aiProvidersApi.create(payload)
    },
    onSuccess: () => {
      toast.success('Saved')
      qc.invalidateQueries({ queryKey: ['ai-providers'] })
      setModalOpen(false)
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || 'Save failed')
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => aiProvidersApi.delete(id),
    onSuccess: () => {
      toast.success('Deleted')
      qc.invalidateQueries({ queryKey: ['ai-providers'] })
      setDeleteId(null)
    },
  })

  const testMut = useMutation({
    mutationFn: (id: string) => {
      setTestingId(id)
      return aiProvidersApi.testConnection(id) as Promise<{ success?: boolean; message?: string }>
    },
    onSuccess: (result) => {
      if (result?.success) {
        toast.success(result.message || 'Connection successful!')
      } else {
        toast.error(result?.message || 'Connection test failed')
      }
      setTestingId(null)
    },
    onError: () => {
      toast.error('Connection failed')
      setTestingId(null)
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Providers"
        subtitle="Add your API keys once — agents link to a provider, so rotating a key here updates every agent that uses it"
        actions={<Button icon={<Plus size={16} />} onClick={openCreate}>Add Provider</Button>}
      />

      <div className="card">
        {isLoading ? (
          <LoadingSpinner fullPage />
        ) : !providers?.length ? (
          <EmptyState
            icon={<Zap size={40} />}
            title="No providers configured"
            description="Add an AI provider to start building agents"
            action={<Button icon={<Plus size={15} />} onClick={openCreate}>Add Provider</Button>}
          />
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {providers.map(p => (
              <div key={p.id} className="flex items-center gap-4 p-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                  <Zap size={18} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-gray-900 dark:text-white">
                      {p.display_name || p.provider_name || p.name || '—'}
                    </p>
                    <Badge variant="gray">{p.provider_name || p.type}</Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                    <span className="flex items-center gap-1 text-xs text-success-600">
                      <CheckCircle2 size={12} /> Key stored
                    </span>
                    {p.model_name && (
                      <span className="text-xs text-gray-400">
                        {isAzureProvider(p.provider_name || p.type)
                          ? `Deployment: ${providerExtra(p).deployment_name || '—'} · Model: ${providerExtra(p).model || p.model_name || '—'}`
                          : `Model: ${p.model_name}`}
                      </span>
                    )}
                    {(p.endpoint_url || p.endpoint) && (
                      <span className="text-xs text-gray-400 truncate max-w-xs">
                        {p.endpoint_url || p.endpoint}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={(p.is_active ?? p.isActive) ? 'success' : 'error'}>
                    {(p.is_active ?? p.isActive) ? 'Active' : 'Inactive'}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<TestTube size={14} />}
                    loading={testingId === p.id}
                    onClick={() => testMut.mutate(p.id)}
                    title="Send a tiny test request using the saved model/deployment"
                  />
                  <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEdit(p)} />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    className="hover:text-error-500"
                    onClick={() => setDeleteId(p.id)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editItem ? 'Edit Provider' : 'Add AI Provider'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending} disabled={!providerDraftReady(draft, !!editItem)}>Save</Button>
          </>
        }
      >
        <div key={editItem?.id ?? 'new'}>
          <ProviderSetupForm value={draft} onChange={patchDraft} providerId={editItem?.id} />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending}
        title="Delete Provider"
        message="Remove this AI provider?"
        confirmLabel="Delete"
      />
    </div>
  )
}
