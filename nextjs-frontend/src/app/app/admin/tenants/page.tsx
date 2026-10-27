'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tenantsApi } from '@/lib/api'
import type { Tenant, PagedResult } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Plus, Pencil, Trash2, Search, Building2, Power, PowerOff, LogIn } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'
import ImpersonateUserModal from '@/components/admin/ImpersonateUserModal'

export default function TenantListPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [impersonateTenant, setImpersonateTenant] = useState<Pick<Tenant, 'id' | 'name'> | null>(null)

  const { data, isLoading } = useQuery<PagedResult<Tenant>>({
    queryKey: ['tenants', search],
    queryFn: () => tenantsApi.list({ filter: search }) as Promise<PagedResult<Tenant>>,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => tenantsApi.delete(id),
    onSuccess: () => { toast.success('Tenant deleted'); qc.invalidateQueries({ queryKey: ['tenants'] }); setDeleteId(null) },
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => active ? tenantsApi.activate(id) : tenantsApi.deactivate(id),
    onSuccess: () => { toast.success('Updated'); qc.invalidateQueries({ queryKey: ['tenants'] }) },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenants"
        subtitle="Manage multi-tenant organizations"
        actions={<Link href="/app/admin/tenants/new"><Button icon={<Plus size={16} />}>Add Tenant</Button></Link>}
      />

      <div className="card p-4">
        <div className="relative max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tenants…" className="input-field pl-9" />
        </div>
      </div>

      <div className="card">
        {isLoading ? <LoadingSpinner fullPage /> : !data?.items?.length ? (
          <EmptyState icon={<Building2 size={40} />} title="No tenants" action={<Link href="/app/admin/tenants/new"><Button icon={<Plus size={15} />}>Add Tenant</Button></Link>} />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Name</th><th>Tenancy Name</th><th>Edition</th><th>Status</th><th>Created</th><th className="text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.items.map(t => (
                  <tr key={t.id}>
                    <td className="font-medium text-gray-900 dark:text-white">{t.name}</td>
                    <td><span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">{t.tenancyName}</span></td>
                    <td>{t.editionName || <span className="text-gray-400">—</span>}</td>
                    <td><Badge variant={t.isActive !== false ? 'success' : 'error'}>{t.isActive !== false ? 'Active' : 'Inactive'}</Badge></td>
                    <td><span className="text-xs text-gray-500">{t.createdAt ? formatDistanceToNow(new Date(t.createdAt), { addSuffix: true }) : '—'}</span></td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" icon={<LogIn size={14} />}
                          title="Sign in as user"
                          onClick={() => setImpersonateTenant({ id: t.id, name: t.name })} />
                        <Button variant="ghost" size="sm" icon={t.isActive !== false ? <PowerOff size={14} /> : <Power size={14} />}
                          onClick={() => toggleMut.mutate({ id: t.id, active: t.isActive === false })}
                          title={t.isActive !== false ? 'Deactivate' : 'Activate'} />
                        <Link href={`/app/admin/tenants/${t.id}`}><Button variant="ghost" size="sm" icon={<Pencil size={14} />} /></Link>
                        <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} className="hover:text-error-500" onClick={() => setDeleteId(t.id)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog open={!!deleteId} onClose={() => setDeleteId(null)} onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending} title="Delete Tenant" message="This will permanently delete the tenant and all associated data." confirmLabel="Delete" />

      <ImpersonateUserModal
        open={!!impersonateTenant}
        onClose={() => setImpersonateTenant(null)}
        tenant={impersonateTenant}
      />
    </div>
  )
}
