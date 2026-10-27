'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ssoApi } from '@/lib/api'
import type { SsoConfiguration } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import { Select, TextArea } from '@/components/ui/Input'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { Plus, Pencil, Trash2, KeyRound, ExternalLink } from 'lucide-react'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const OIDC_PRESETS: Record<string, string> = {
  google: 'https://accounts.google.com',
  microsoft: 'https://login.microsoftonline.com/common/v2.0',
  github: 'https://github.com',
  okta: '',
  auth0: '',
  custom: '',
}

interface SsoFormData {
  provider: 'OIDC' | 'SAML'
  provider_name: string
  client_id?: string
  client_secret?: string
  metadata_url?: string
  metadata_xml?: string
  is_enabled?: boolean
  auto_provision_users?: boolean
  default_role?: string
}

export default function SsoConfigurationPage() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<SsoConfiguration | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const { data: configs, isLoading } = useQuery<SsoConfiguration[]>({
    queryKey: ['sso-configs'],
    queryFn: () => ssoApi.list(),
  })
  const { register, handleSubmit, reset, watch } = useForm<SsoFormData>()
  const protocol = watch('provider')
  const preset = watch('provider_name')

  const openCreate = () => {
    reset({ provider: 'OIDC', provider_name: 'google', is_enabled: true, auto_provision_users: true })
    setEditItem(null)
    setModalOpen(true)
  }
  const openEdit = (c: SsoConfiguration) => {
    reset({
      provider: (c.provider as 'OIDC' | 'SAML') || 'OIDC',
      provider_name: c.provider_name || c.providerName || '',
      client_id: c.client_id || c.clientId,
      metadata_url: c.metadata_url || c.metadataUrl || c.authority,
      metadata_xml: c.metadata_xml,
      is_enabled: c.is_enabled ?? c.isActive ?? true,
      auto_provision_users: c.auto_provision_users ?? true,
      default_role: c.default_role,
    })
    setEditItem(c)
    setModalOpen(true)
  }

  const saveMut = useMutation({
    mutationFn: (d: SsoFormData) => {
      const payload = {
        ...d,
        metadata_url: d.provider === 'OIDC'
          ? (d.metadata_url || OIDC_PRESETS[d.provider_name] || d.metadata_url)
          : d.metadata_url,
      }
      return editItem ? ssoApi.update(editItem.id, payload) : ssoApi.create(payload)
    },
    onSuccess: () => { toast.success('Saved'); qc.invalidateQueries({ queryKey: ['sso-configs'] }); setModalOpen(false) },
    onError: () => toast.error('Save failed'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => ssoApi.delete(id),
    onSuccess: () => { toast.success('Deleted'); qc.invalidateQueries({ queryKey: ['sso-configs'] }); setDeleteId(null) },
  })

  const testMut = useMutation({
    mutationFn: (id: string) => ssoApi.test(id),
    onSuccess: (data) => { if (data.test_url) window.open(data.test_url, '_blank') },
    onError: () => toast.error('Test URL unavailable'),
  })

  return (
    <div className="space-y-6">
      <PageHeader title="SSO Configuration" subtitle="Configure OIDC or SAML Single Sign-On"
        actions={<Button icon={<Plus size={16} />} onClick={openCreate}>Add Provider</Button>} />

      <div className="card p-4 text-sm text-gray-600 dark:text-gray-400 space-y-1">
        <p>ACS / callback URL (OIDC redirect or SAML POST): <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">{API_BASE}/api/sso/callback/&#123;configId&#125;</code></p>
        <p>SAML SP metadata: <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">{API_BASE}/api/sso/sp/&#123;configId&#125;</code></p>
      </div>

      <div className="card">
        {isLoading ? <LoadingSpinner fullPage /> : !configs?.length ? (
          <EmptyState icon={<KeyRound size={40} />} title="No SSO providers configured"
            description="Add an OIDC or SAML provider to enable Single Sign-On"
            action={<Button icon={<Plus size={15} />} onClick={openCreate}>Add Provider</Button>} />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Name</th><th>Type</th><th>Entity / Client ID</th><th>Metadata</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {configs.map(c => (
                  <tr key={c.id}>
                    <td className="font-medium capitalize">{c.provider_name}</td>
                    <td><Badge variant="gray">{c.provider}</Badge></td>
                    <td><span className="font-mono text-xs">{c.client_id || '—'}</span></td>
                    <td><span className="text-xs text-gray-500 truncate max-w-[200px] inline-block">{c.metadata_url || (c.metadata_xml ? 'XML uploaded' : '—')}</span></td>
                    <td><Badge variant={c.is_enabled ? 'success' : 'error'}>{c.is_enabled ? 'Active' : 'Inactive'}</Badge></td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        {c.provider === 'SAML' && (
                          <Button variant="ghost" size="sm" onClick={() => window.open(ssoApi.getSpMetadataUrl(c.id), '_blank')} title="SP metadata">XML</Button>
                        )}
                        <Button variant="ghost" size="sm" icon={<ExternalLink size={14} />} onClick={() => testMut.mutate(c.id)} title="Test login" />
                        <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEdit(c)} />
                        <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} className="hover:text-error-500" onClick={() => setDeleteId(c.id)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editItem ? 'Edit SSO Provider' : 'Add SSO Provider'}
        footer={<><Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit(d => saveMut.mutate(d))} loading={saveMut.isPending}>Save</Button></>}>
        <div className="space-y-4">
          <Select {...register('provider', { required: true })} label="Protocol" defaultValue="OIDC">
            <option value="OIDC">OIDC (Google, Microsoft, Auth0…)</option>
            <option value="SAML">SAML 2.0 (Okta, ADFS, Azure AD SAML…)</option>
          </Select>
          <Select {...register('provider_name', { required: true })} label="Provider preset" defaultValue="google">
            <option value="google">Google</option>
            <option value="microsoft">Microsoft</option>
            <option value="okta">Okta</option>
            <option value="azure-ad">Azure AD</option>
            <option value="adfs">AD FS</option>
            <option value="auth0">Auth0</option>
            <option value="custom">Custom</option>
          </Select>

          {protocol === 'OIDC' ? (
            <>
              <Input {...register('client_id', { required: protocol === 'OIDC' })} label="Client ID" />
              <Input {...register('client_secret')} label="Client Secret" type="password" placeholder={editItem ? '(unchanged if empty)' : ''} />
              <Input
                {...register('metadata_url')}
                label="Issuer / Metadata URL"
                placeholder={OIDC_PRESETS[preset] || 'https://your-idp.com'}
              />
            </>
          ) : (
            <>
              <Input {...register('client_id')} label="SP Entity ID (optional)" placeholder="Defaults to /api/sso/sp/{configId}" />
              <Input {...register('client_secret')} label="SP signing private key (PEM, optional)" type="password" placeholder={editItem ? '(unchanged if empty)' : ''} />
              <Input {...register('metadata_url')} label="IdP metadata URL" placeholder="https://idp.example.com/metadata" />
              <TextArea {...register('metadata_xml')} label="IdP metadata XML (if not using URL)" rows={5} placeholder="<EntityDescriptor …>" />
            </>
          )}

          <Input {...register('default_role')} label="Default role (new users)" placeholder="User" />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <input type="checkbox" id="ssoEnabled" {...register('is_enabled')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" defaultChecked />
              <label htmlFor="ssoEnabled" className="text-sm font-medium text-gray-700 dark:text-gray-300">Active</label>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="ssoAutoProvision" {...register('auto_provision_users')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" defaultChecked />
              <label htmlFor="ssoAutoProvision" className="text-sm font-medium text-gray-700 dark:text-gray-300">Auto-provision users</label>
            </div>
          </div>
          {editItem && (
            <div className="text-xs text-gray-500 space-y-1">
              <p>Callback: <code>{API_BASE}/api/sso/callback/{editItem.id}</code></p>
              {editItem.provider === 'SAML' && <p>SP metadata: <code>{ssoApi.getSpMetadataUrl(editItem.id)}</code></p>}
            </div>
          )}
        </div>
      </Modal>

      <ConfirmDialog open={!!deleteId} onClose={() => setDeleteId(null)} onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending} title="Delete Provider" message="Remove this SSO provider?" confirmLabel="Delete" />
    </div>
  )
}
