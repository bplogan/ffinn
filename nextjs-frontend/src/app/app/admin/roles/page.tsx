'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rolesApi } from '@/lib/api'
import type { Role } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Plus, Pencil, Trash2, Shield } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

export default function RoleListPage() {
  const qc = useQueryClient()
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const { data: roles, isLoading } = useQuery<Role[]>({ queryKey: ['roles'], queryFn: () => rolesApi.list() as Promise<Role[]> })

  const deleteMut = useMutation({
    mutationFn: (id: string) => rolesApi.delete(id),
    onSuccess: () => { toast.success('Role deleted'); qc.invalidateQueries({ queryKey: ['roles'] }); setDeleteId(null) },
    onError: () => toast.error('Cannot delete role'),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles"
        subtitle="Manage roles and their permissions"
        actions={<Link href="/app/admin/roles/new"><Button icon={<Plus size={16} />}>Add Role</Button></Link>}
      />

      <div className="card">
        {isLoading ? <LoadingSpinner fullPage /> : !roles?.length ? (
          <EmptyState icon={<Shield size={40} />} title="No roles" action={<Link href="/app/admin/roles/new"><Button icon={<Plus size={15} />}>Add Role</Button></Link>} />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Name</th><th>Display Name</th><th>Type</th><th className="text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {roles.map(r => (
                  <tr key={r.id}>
                    <td className="font-medium text-gray-900 dark:text-white">{r.name}</td>
                    <td>{r.displayName || '—'}</td>
                    <td><Badge variant={r.isStatic ? 'gray' : 'info'}>{r.isStatic ? 'System' : 'Custom'}</Badge></td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Link href={`/app/admin/roles/${r.id}/permissions`}>
                          <Button variant="ghost" size="sm" icon={<Shield size={14} />} title="Permissions" />
                        </Link>
                        {!r.isStatic && <Link href={`/app/admin/roles/${r.id}`}>
                          <Button variant="ghost" size="sm" icon={<Pencil size={14} />} />
                        </Link>}
                        {!r.isStatic && <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} className="hover:text-error-500" onClick={() => setDeleteId(r.id)} />}
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
        loading={deleteMut.isPending} title="Delete Role" message="Delete this role?" confirmLabel="Delete" />
    </div>
  )
}
