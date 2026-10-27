'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { teamInvitationsApi, rolesApi } from '@/lib/api'
import type { TeamInvitation, Role } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import { Select } from '@/components/ui/Input'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { Plus, RefreshCw, X, Mail } from 'lucide-react'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import { format } from 'date-fns'

export default function TeamInvitationsPage() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [revokeId, setRevokeId] = useState<string | null>(null)

  const { data: invitations, isLoading } = useQuery<TeamInvitation[]>({ queryKey: ['team-invitations'], queryFn: () => teamInvitationsApi.list() as Promise<TeamInvitation[]> })
  const { data: roles } = useQuery<Role[]>({ queryKey: ['roles'], queryFn: () => rolesApi.list() as Promise<Role[]> })

  const { register, handleSubmit, reset } = useForm<{ email: string; roleId?: string }>()

  const inviteMut = useMutation({
    mutationFn: (d: { email: string; roleId?: string }) => {
      const roleName = d.roleId ? roles?.find(r => r.id === d.roleId)?.name : undefined
      return teamInvitationsApi.invite({ email: d.email, role_name: roleName ?? 'User' })
    },
    onSuccess: () => { toast.success('Invitation sent'); qc.invalidateQueries({ queryKey: ['team-invitations'] }); setModalOpen(false); reset() },
    onError: () => toast.error('Failed to send invitation'),
  })

  const resendMut = useMutation({
    mutationFn: (id: string) => teamInvitationsApi.resend(id),
    onSuccess: () => toast.success('Invitation resent'),
  })

  const revokeMut = useMutation({
    mutationFn: (id: string) => teamInvitationsApi.revoke(id),
    onSuccess: () => { toast.success('Invitation revoked'); qc.invalidateQueries({ queryKey: ['team-invitations'] }); setRevokeId(null) },
  })

  const statusVariant = (s?: string) => {
    if (s === 'Accepted') return 'success'
    if (s === 'Expired') return 'error'
    return 'warning'
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Team Invitations" subtitle="Invite team members to join your workspace"
        actions={<Button icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>Invite Member</Button>} />

      <div className="card">
        {isLoading ? <LoadingSpinner fullPage /> : !invitations?.length ? (
          <EmptyState icon={<Mail size={40} />} title="No invitations sent" action={<Button icon={<Plus size={15} />} onClick={() => setModalOpen(true)}>Invite Member</Button>} />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Sent</th><th>Expires</th><th className="text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {invitations.map(inv => (
                  <tr key={inv.id}>
                    <td className="font-medium">{inv.email}</td>
                    <td>{inv.roleName || <span className="text-gray-400">—</span>}</td>
                    <td><Badge variant={statusVariant(inv.status)}>{inv.status || 'Pending'}</Badge></td>
                    <td><span className="text-xs text-gray-500">{inv.createdAt ? format(new Date(inv.createdAt), 'MMM d, yyyy') : '—'}</span></td>
                    <td><span className="text-xs text-gray-500">{inv.expiresAt ? format(new Date(inv.expiresAt), 'MMM d, yyyy') : '—'}</span></td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        {inv.status === 'Pending' && <>
                          <Button variant="ghost" size="sm" icon={<RefreshCw size={13} />} title="Resend" onClick={() => resendMut.mutate(inv.id)} />
                          <Button variant="ghost" size="sm" icon={<X size={13} />} title="Revoke" className="hover:text-error-500" onClick={() => setRevokeId(inv.id)} />
                        </>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Invite Team Member"
        footer={<><Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit(d => inviteMut.mutate(d))} loading={inviteMut.isPending}>Send Invitation</Button></>}>
        <div className="space-y-4">
          <Input {...register('email', { required: 'Required' })} label="Email address" type="email" placeholder="colleague@example.com" />
          <Select {...register('roleId')} label="Role (optional)">
            <option value="">No specific role</option>
            {roles?.map(r => <option key={r.id} value={r.id}>{r.displayName || r.name}</option>)}
          </Select>
        </div>
      </Modal>

      <ConfirmDialog open={!!revokeId} onClose={() => setRevokeId(null)} onConfirm={() => revokeId && revokeMut.mutate(revokeId)}
        loading={revokeMut.isPending} title="Revoke Invitation" message="This invitation will be invalidated." confirmLabel="Revoke" />
    </div>
  )
}
