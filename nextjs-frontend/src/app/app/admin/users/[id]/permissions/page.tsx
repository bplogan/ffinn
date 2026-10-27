'use client'
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi, permissionsApi } from '@/lib/api'
import { useParams, useRouter } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Breadcrumb from '@/components/ui/Breadcrumb'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import type { PermissionGroup, UserListItem } from '@/types'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { clsx } from 'clsx'

function PermissionGroupNode({
  group,
  selected,
  onToggle,
}: {
  group: PermissionGroup
  selected: Set<string>
  onToggle: (name: string) => void
}) {
  const [open, setOpen] = useState(true)
  const groupPerms = group.permissions || []
  const allSelected = groupPerms.length > 0 && groupPerms.every(p => selected.has(p.name))
  const someSelected = groupPerms.some(p => selected.has(p.name))

  const toggleAll = () => {
    if (allSelected) groupPerms.forEach(p => selected.has(p.name) && onToggle(p.name))
    else groupPerms.forEach(p => !selected.has(p.name) && onToggle(p.name))
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mb-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800 text-left"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <input
          type="checkbox"
          checked={allSelected}
          ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
          onChange={toggleAll}
          className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
          onClick={e => e.stopPropagation()}
        />
        <span className="text-sm font-semibold text-gray-900 dark:text-white">
          {group.displayName || group.name}
        </span>
        <span className="ml-auto text-xs text-gray-400">
          {groupPerms.filter(p => selected.has(p.name)).length}/{groupPerms.length}
        </span>
      </button>
      {open && (
        <div className="px-4 py-2 divide-y divide-gray-100 dark:divide-gray-700">
          {groupPerms.map(p => (
            <label key={p.name} className="flex items-center gap-2 py-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selected.has(p.name)}
                onChange={() => onToggle(p.name)}
                className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">{p.displayName || p.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export default function UserPermissionsPage() {
  const { id } = useParams() as { id: string }
  const router = useRouter()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data: user } = useQuery<UserListItem>({
    queryKey: ['user', id],
    queryFn: () => usersApi.get(id) as Promise<UserListItem>,
  })

  const { data: allPerms, isLoading: loadingPerms } = useQuery<PermissionGroup[]>({
    queryKey: ['all-permissions'],
    queryFn: () => permissionsApi.getAll() as Promise<PermissionGroup[]>,
  })

  const { data: userGrants } = useQuery<{ user_id: string; items: Array<{ permission_name: string; is_granted: boolean }> }>({
    queryKey: ['user-permissions', id],
    queryFn: () => usersApi.getPermissions(id) as Promise<{ user_id: string; items: Array<{ permission_name: string; is_granted: boolean }> }>,
  })

  useEffect(() => {
    if (userGrants?.items) {
      setSelected(new Set(userGrants.items.filter(g => g.is_granted).map(g => g.permission_name)))
    }
  }, [userGrants])

  const toggle = (name: string) =>
    setSelected(s => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n })

  const saveMut = useMutation({
    mutationFn: () =>
      usersApi.setPermissions(id, {
        permissions: Array.from(selected).map(name => ({ name, is_granted: true })),
      }),
    onSuccess: () => {
      toast.success('Permissions updated')
      qc.invalidateQueries({ queryKey: ['user-permissions', id] })
    },
    onError: () => toast.error('Failed to update permissions'),
  })

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[
        { label: 'Users', href: '/app/admin/users' },
        { label: user?.fullName || user?.userName || 'User', href: `/app/admin/users/${id}` },
        { label: 'Permissions' },
      ]} />
      <PageHeader
        title="Manage Permissions"
        subtitle={`Direct permission overrides for ${user?.fullName || user?.email || 'user'} (in addition to role permissions)`}
      />

      {loadingPerms ? <LoadingSpinner fullPage /> : (
        <div className="max-w-3xl space-y-2">
          <p className="text-sm text-gray-500 dark:text-gray-400 pb-2">
            These are explicit per-user grants. Leave unchecked to inherit from assigned roles.
          </p>
          {allPerms?.map(group => (
            <PermissionGroupNode key={group.name} group={group} selected={selected} onToggle={toggle} />
          ))}
          <div className={clsx('flex gap-3 pt-4', !allPerms?.length && 'hidden')}>
            <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending}>
              Save Permissions
            </Button>
            <Button variant="secondary" onClick={() => router.push('/app/admin/users')}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
