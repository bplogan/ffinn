'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { tenantsApi } from '@/lib/api'
import type { UserListItem, PagedResult, Tenant } from '@/types'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Badge from '@/components/ui/Badge'
import { LogIn, Search } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import toast from 'react-hot-toast'

interface Props {
  open: boolean
  onClose: () => void
  tenant: Pick<Tenant, 'id' | 'name'> | null
}

export default function ImpersonateUserModal({ open, onClose, tenant }: Props) {
  const [search, setSearch] = useState('')
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const { impersonate, user: currentUser } = useAuth()

  const { data, isLoading } = useQuery<PagedResult<UserListItem>>({
    queryKey: ['tenant-users', tenant?.id, search],
    queryFn: () => tenantsApi.users(tenant!.id, { filter: search, page_size: 50 }) as Promise<PagedResult<UserListItem>>,
    enabled: open && !!tenant?.id,
  })

  const handleSelect = async (userId: string) => {
    if (!tenant) return
    setLoadingId(userId)
    try {
      await impersonate(userId, tenant.id)
      onClose()
      toast.success('Signed in as user')
    } catch {
      toast.error('Failed to sign in as user')
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={tenant ? `Sign in as user — ${tenant.name}` : 'Sign in as user'}
      size="lg"
    >
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Choose a user in this tenant. You will see the app as they would until you return to your account.
      </p>

      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search users…"
          className="input-field pl-9"
        />
      </div>

      {isLoading ? (
        <LoadingSpinner label="Loading users…" />
      ) : !data?.items?.length ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 py-6 text-center">No users found in this tenant.</p>
      ) : (
        <ul className="divide-y divide-gray-100 dark:divide-gray-700 -mx-2">
          {data.items.map(u => {
            const isSelf = u.id === currentUser?.id
            return (
              <li key={u.id} className="flex items-center justify-between gap-3 px-2 py-3">
                <div className="min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white truncate">
                    {u.fullName || u.userName}
                  </p>
                  <p className="text-xs text-gray-500 truncate">{u.email}</p>
                  {u.roles?.length ? (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {u.roles.slice(0, 3).map(r => <Badge key={r} variant="info">{r}</Badge>)}
                    </div>
                  ) : null}
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<LogIn size={14} />}
                  disabled={isSelf || u.isActive === false || loadingId === u.id}
                  loading={loadingId === u.id}
                  onClick={() => handleSelect(u.id)}
                  title={isSelf ? 'Cannot sign in as yourself' : u.isActive === false ? 'User is inactive' : 'Sign in as this user'}
                >
                  Sign in
                </Button>
              </li>
            )
          })}
        </ul>
      )}
    </Modal>
  )
}
