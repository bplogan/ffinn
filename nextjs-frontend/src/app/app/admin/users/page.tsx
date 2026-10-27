'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '@/lib/api'
import type { UserListItem, PagedResult } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { Plus, Pencil, Trash2, Search, Users, Shield, ShieldCheck, Lock, Unlock, LogIn } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'
import { useAuth } from '@/contexts/AuthContext'

export default function UserListPage() {
  const qc = useQueryClient()
  const { user: currentUser, impersonate } = useAuth()
  const [impersonatingId, setImpersonatingId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  const { data, isLoading } = useQuery<PagedResult<UserListItem>>({
    queryKey: ['users', search, page],
    queryFn: () => usersApi.list({ filter: search, maxResultCount: PAGE_SIZE, skipCount: page * PAGE_SIZE }) as Promise<PagedResult<UserListItem>>,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => usersApi.delete(id),
    onSuccess: () => { toast.success('User deleted'); qc.invalidateQueries({ queryKey: ['users'] }); setDeleteId(null) },
    onError: () => toast.error('Failed to delete user'),
  })

  const activateMut = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => active ? usersApi.activate(id) : usersApi.deactivate(id),
    onSuccess: () => { toast.success('Updated'); qc.invalidateQueries({ queryKey: ['users'] }) },
  })

  const handleImpersonate = async (userId: string) => {
    setImpersonatingId(userId)
    try {
      await impersonate(userId)
      toast.success('Signed in as user')
    } catch {
      toast.error('Failed to sign in as user')
    } finally {
      setImpersonatingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        subtitle="Manage user accounts and access"
        actions={
          <Link href="/app/admin/users/new">
            <Button icon={<Plus size={16} />}>Add User</Button>
          </Link>
        }
      />

      {/* Search */}
      <div className="card p-4">
        <div className="relative max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0) }}
            placeholder="Search users…"
            className="input-field pl-9"
          />
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {isLoading ? (
          <LoadingSpinner fullPage label="Loading users…" />
        ) : !data?.items?.length ? (
          <EmptyState
            icon={<Users size={40} />}
            title="No users found"
            description={search ? 'Try a different search term' : 'Add your first user to get started'}
            action={<Link href="/app/admin/users/new"><Button icon={<Plus size={15} />}>Add User</Button></Link>}
          />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Roles</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.items.map(u => (
                  <tr key={u.id}>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-900 flex items-center justify-center text-brand-600 dark:text-brand-400 text-xs font-semibold flex-shrink-0">
                          {(u.firstName?.[0] || u.userName?.[0] || '?').toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">{u.fullName || u.userName}</p>
                          <p className="text-xs text-gray-400">@{u.userName}</p>
                        </div>
                      </div>
                    </td>
                    <td>{u.email}</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {u.roles?.slice(0, 2).map(r => <Badge key={r} variant="info">{r}</Badge>)}
                        {(u.roles?.length ?? 0) > 2 && <Badge variant="gray">+{(u.roles?.length ?? 0) - 2}</Badge>}
                      </div>
                    </td>
                    <td>
                      <Badge variant={u.isActive !== false ? 'success' : 'error'}>
                        {u.isActive !== false ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td>
                      <span className="text-xs text-gray-500">
                        {u.createdAt ? formatDistanceToNow(new Date(u.createdAt), { addSuffix: true }) : '—'}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm"
                          icon={<LogIn size={14} />}
                          title={u.id === currentUser?.id ? 'Cannot sign in as yourself' : 'Sign in as user'}
                          disabled={u.id === currentUser?.id || u.isActive === false || impersonatingId === u.id}
                          loading={impersonatingId === u.id}
                          onClick={() => handleImpersonate(u.id)}
                        />
                        <Link href={`/app/admin/users/${u.id}/roles`} title="Manage roles">
                          <Button variant="ghost" size="sm" icon={<Shield size={14} />} />
                        </Link>
                        <Link href={`/app/admin/users/${u.id}/permissions`} title="Manage permissions">
                          <Button variant="ghost" size="sm" icon={<ShieldCheck size={14} />} />
                        </Link>
                        <Button variant="ghost" size="sm"
                          icon={u.isActive !== false ? <Lock size={14} /> : <Unlock size={14} />}
                          title={u.isActive !== false ? 'Deactivate' : 'Activate'}
                          onClick={() => activateMut.mutate({ id: u.id, active: u.isActive === false })}
                        />
                        <Link href={`/app/admin/users/${u.id}`}>
                          <Button variant="ghost" size="sm" icon={<Pencil size={14} />} />
                        </Link>
                        <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} className="hover:text-error-500"
                          onClick={() => setDeleteId(u.id)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {data && (data.total_count ?? data.totalCount ?? 0) > PAGE_SIZE && (
          <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm text-gray-500">
            <span>Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total_count ?? data.totalCount ?? 0)} of {data.total_count ?? data.totalCount ?? 0}</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</Button>
              <Button variant="secondary" size="sm" disabled={(page + 1) * PAGE_SIZE >= (data.total_count ?? data.totalCount ?? 0)} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending}
        title="Delete User"
        message="Are you sure you want to delete this user? This action cannot be undone."
        confirmLabel="Delete"
      />
    </div>
  )
}
