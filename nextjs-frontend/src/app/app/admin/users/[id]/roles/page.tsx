'use client'
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi, rolesApi } from '@/lib/api'
import { useParams, useRouter } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Breadcrumb from '@/components/ui/Breadcrumb'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Badge from '@/components/ui/Badge'
import toast from 'react-hot-toast'
import type { Role, UserListItem } from '@/types'
import { Shield } from 'lucide-react'
import { clsx } from 'clsx'

export default function UserRolesPage() {
  const { id } = useParams() as { id: string }
  const router = useRouter()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data: user } = useQuery<UserListItem>({
    queryKey: ['user', id],
    queryFn: () => usersApi.get(id) as Promise<UserListItem>,
  })
  const { data: allRoles, isLoading: loadingRoles } = useQuery<Role[]>({
    queryKey: ['roles'],
    queryFn: () => rolesApi.list() as Promise<Role[]>,
  })
  const { data: userRoles, isLoading: loadingUserRoles } = useQuery<{ roles: string[] }>({
    queryKey: ['user-roles', id],
    queryFn: () => usersApi.getRoles(id) as Promise<{ roles: string[] }>,
  })

  useEffect(() => {
    if (userRoles?.roles) setSelected(new Set(userRoles.roles))
  }, [userRoles])

  const toggle = (name: string) =>
    setSelected(s => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n })

  const saveMut = useMutation({
    mutationFn: () => usersApi.setRoles(id, Array.from(selected)),
    onSuccess: () => {
      toast.success('Roles updated')
      qc.invalidateQueries({ queryKey: ['user-roles', id] })
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: () => toast.error('Failed to update roles'),
  })

  const isLoading = loadingRoles || loadingUserRoles

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[
        { label: 'Users', href: '/app/admin/users' },
        { label: user?.fullName || user?.userName || 'User', href: `/app/admin/users/${id}` },
        { label: 'Roles' },
      ]} />
      <PageHeader
        title="Manage Roles"
        subtitle={`Assign roles to ${user?.fullName || user?.email || 'user'}`}
      />

      {isLoading ? <LoadingSpinner fullPage /> : (
        <div className="max-w-2xl space-y-3">
          {allRoles?.map(role => {
            const checked = selected.has(role.name)
            return (
              <button
                key={role.id}
                onClick={() => toggle(role.name)}
                className={clsx(
                  'w-full flex items-center gap-4 px-5 py-4 rounded-xl border text-left transition-all',
                  checked
                    ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20 dark:border-brand-600'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600',
                )}
              >
                <div className={clsx(
                  'w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors',
                  checked ? 'bg-brand-500 border-brand-500' : 'border-gray-300 dark:border-gray-600',
                )}>
                  {checked && (
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <Shield size={18} className={checked ? 'text-brand-500' : 'text-gray-400'} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white">{role.displayName || role.name}</p>
                  {role.description && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{role.description}</p>
                  )}
                </div>
                {role.isStatic && <Badge variant="gray">System</Badge>}
                {role.isDefault && <Badge variant="info">Default</Badge>}
              </button>
            )
          })}

          <div className="flex gap-3 pt-2">
            <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending}>Save Roles</Button>
            <Button variant="secondary" onClick={() => router.push('/app/admin/users')}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  )
}
