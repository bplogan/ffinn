'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { customDomainsApi } from '@/lib/api'
import type { CustomDomain } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import { Globe, Plus, Trash2, RefreshCw, CheckCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { useForm } from 'react-hook-form'

export default function DomainsPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const { data: domains = [], isLoading } = useQuery<CustomDomain[]>({
    queryKey: ['custom-domains'],
    queryFn: () => customDomainsApi.list() as Promise<CustomDomain[]>,
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ domain: string }>()

  const addMut = useMutation({
    mutationFn: (d: { domain: string }) => customDomainsApi.add(d),
    onSuccess: () => { toast.success('Domain added'); qc.invalidateQueries({ queryKey: ['custom-domains'] }); setShowAdd(false); reset() },
    onError: () => toast.error('Failed to add domain'),
  })

  const verifyMut = useMutation({
    mutationFn: (id: string) => customDomainsApi.verify(id),
    onSuccess: () => { toast.success('Verification initiated'); qc.invalidateQueries({ queryKey: ['custom-domains'] }) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => customDomainsApi.delete(id),
    onSuccess: () => { toast.success('Domain removed'); qc.invalidateQueries({ queryKey: ['custom-domains'] }); setDeleteId(null) },
  })

  const statusVariant = (s?: string) => {
    const lower = (s ?? '').toLowerCase()
    return lower === 'active' || lower === 'verified' ? 'success'
      : lower === 'pending' || lower === 'verifying' ? 'warning'
      : lower === 'failed' ? 'error'
      : 'gray'
  }

  return (
    <div className="space-y-4">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'Custom Domains' }]} />
      <PageHeader title="Custom Domains" subtitle="Map custom domains to your AI agents"
        actions={<Button icon={<Plus size={15} />} onClick={() => setShowAdd(true)}>Add domain</Button>} />

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading…</div>
        ) : !domains.length ? (
          <EmptyState icon={<Globe size={32} />} title="No custom domains" description="Add a custom domain to brand your AI agent endpoints"
            action={<Button icon={<Plus size={15} />} onClick={() => setShowAdd(true)}>Add domain</Button>} />
        ) : (
          <table className="table">
            <thead><tr><th>Domain</th><th>Status</th><th>Verified At</th><th className="w-32">Actions</th></tr></thead>
            <tbody>
              {domains.map(d => (
                <tr key={d.id}>
                  <td className="font-mono font-medium">{d.domain}</td>
                  <td><Badge variant={statusVariant(d.status)}>{d.status ?? 'unknown'}</Badge></td>
                  <td className="text-sm text-gray-500">{(d.last_verified_at ?? d.verifiedAt) ? new Date((d.last_verified_at ?? d.verifiedAt)!).toLocaleDateString() : '—'}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      {(d.status ?? '').toLowerCase() !== 'active' && (
                        <button onClick={() => verifyMut.mutate(d.id)} className="text-brand-500 hover:text-brand-600 text-xs flex items-center gap-1">
                          <RefreshCw size={13} /> Verify
                        </button>
                      )}
                      {(d.status ?? '').toLowerCase() === 'active' && <CheckCircle size={14} className="text-success-500" />}
                      <button onClick={() => setDeleteId(d.id)} className="text-error-500 hover:text-error-600">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* DNS instructions */}
        <div className="p-4 border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">DNS Setup</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Add a <code className="bg-white dark:bg-gray-700 px-1 rounded">CNAME</code> record pointing your domain to{' '}
            <code className="bg-white dark:bg-gray-700 px-1 rounded">agents.ffinn.app</code>, then click Verify.
          </p>
        </div>
      </div>

      <Modal open={showAdd} onClose={() => { setShowAdd(false); reset() }} title="Add custom domain">
        <form onSubmit={handleSubmit(d => addMut.mutate(d))} className="space-y-4">
          <Input {...register('domain', { required: 'Domain is required', pattern: { value: /^[a-z0-9.-]+\.[a-z]{2,}$/i, message: 'Enter a valid domain' } })}
            label="Domain name" placeholder="agents.yourdomain.com" error={errors.domain?.message} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" type="button" onClick={() => { setShowAdd(false); reset() }}>Cancel</Button>
            <Button type="submit" loading={addMut.isPending}>Add domain</Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!deleteId} onClose={() => setDeleteId(null)} onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending} title="Remove domain" message="Remove this custom domain?" confirmLabel="Remove" />
    </div>
  )
}
