'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { featureFlagsApi } from '@/lib/api'
import type { FeatureFlag } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Modal from '@/components/ui/Modal'
import Badge from '@/components/ui/Badge'
import { Plus, Zap, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import { useMemo, useState } from 'react'

/** Fallback labels/descriptions when DB rows pre-date seeded metadata. */
const FLAG_CATALOG: Record<string, { label: string; description: string }> = {
  ai_agent_enabled: {
    label: 'AI Agent',
    description: 'AI code generation, staging deploys, and release workflows.',
  },
  team_invitations_enabled: {
    label: 'Team Invitations',
    description: 'Invite teammates by email and assign roles within a tenant.',
  },
  two_factor_auth_enabled: {
    label: 'Two-Factor Authentication',
    description: 'TOTP two-factor authentication for user login.',
  },
  sso_enabled: {
    label: 'Single Sign-On',
    description: 'OIDC/SAML SSO via tenant SSO configurations.',
  },
  stripe_billing_enabled: {
    label: 'Stripe Billing',
    description: 'Stripe checkout, subscriptions, and billing webhooks.',
  },
  sms_notifications_enabled: {
    label: 'SMS Notifications',
    description: 'SMS notification channel for tenant alerts.',
  },
  push_notifications_enabled: {
    label: 'Push Notifications',
    description: 'Push notifications (e.g. Firebase) for tenant alerts.',
  },
}

function flagEnabled(flag: FeatureFlag): boolean {
  return flag.is_enabled ?? flag.isEnabled ?? false
}

function flagLabel(flag: FeatureFlag): string {
  return FLAG_CATALOG[flag.name]?.label ?? flag.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function flagDescription(flag: FeatureFlag): string {
  return flag.description?.trim() || FLAG_CATALOG[flag.name]?.description || 'No description provided.'
}

function FeatureToggle({
  enabled,
  disabled,
  onChange,
}: {
  enabled: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
        enabled ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-600'
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ${
          enabled ? 'translate-x-4' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

export default function PaywallConfigurationPage() {
  const qc = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newEnabled, setNewEnabled] = useState(true)
  const [pending, setPending] = useState<string | null>(null)

  const { data: flags, isLoading } = useQuery<FeatureFlag[]>({
    queryKey: ['feature-flags'],
    queryFn: () => featureFlagsApi.list() as Promise<FeatureFlag[]>,
  })

  const sortedFlags = useMemo(
    () => [...(flags ?? [])].sort((a, b) => flagLabel(a).localeCompare(flagLabel(b))),
    [flags],
  )

  const toggleMut = useMutation({
    mutationFn: ({ name, is_enabled }: { name: string; is_enabled: boolean }) =>
      featureFlagsApi.update(name, { is_enabled }),
    onMutate: ({ name, is_enabled }) => {
      setPending(name)
      qc.setQueryData<FeatureFlag[]>(['feature-flags'], old =>
        old?.map(f => (f.name === name ? { ...f, is_enabled } : f)),
      )
    },
    onSuccess: (_data, { name, is_enabled }) => {
      toast.success(`${flagLabel({ name })} ${is_enabled ? 'enabled' : 'disabled'}`)
      qc.invalidateQueries({ queryKey: ['feature-flags'] })
    },
    onError: () => {
      toast.error('Failed to update feature flag')
      qc.invalidateQueries({ queryKey: ['feature-flags'] })
    },
    onSettled: () => setPending(null),
  })

  const createMut = useMutation({
    mutationFn: () =>
      featureFlagsApi.create({
        name: newName.trim().toLowerCase().replace(/\s+/g, '_'),
        description: newDescription.trim() || undefined,
        is_enabled: newEnabled,
      }),
    onSuccess: () => {
      toast.success('Feature flag created')
      qc.invalidateQueries({ queryKey: ['feature-flags'] })
      setAddOpen(false)
      setNewName('')
      setNewDescription('')
      setNewEnabled(true)
    },
    onError: (err: Error) => toast.error(err.message || 'Failed to create feature flag'),
  })

  const handleCreate = () => {
    const name = newName.trim().toLowerCase().replace(/\s+/g, '_')
    if (!name) {
      toast.error('Feature key is required')
      return
    }
    if (!/^[a-z][a-z0-9_]*$/.test(name)) {
      toast.error('Use lowercase letters, numbers, and underscores (start with a letter)')
      return
    }
    createMut.mutate()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Feature Flags"
        subtitle="Enable or disable platform features globally. Map features to subscription plans in Editions."
        actions={
          <Button icon={<Plus size={16} />} onClick={() => setAddOpen(true)}>
            Add Feature Flag
          </Button>
        }
      />

      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 px-4 py-3 text-sm text-gray-600 dark:text-gray-400 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span>Plan-specific paywall rules (which edition includes which feature) are managed separately.</span>
        <Link
          href="/app/admin/editions"
          className="inline-flex items-center gap-1 text-brand-500 hover:text-brand-400 font-medium"
        >
          Manage Editions <ExternalLink size={14} />
        </Link>
      </div>

      {isLoading ? (
        <LoadingSpinner fullPage />
      ) : (
        <div className="max-w-3xl">
          <div className="card divide-y divide-gray-100 dark:divide-gray-700">
            {sortedFlags.length === 0 && (
              <div className="p-10 text-center space-y-3">
                <p className="text-sm text-gray-500">No feature flags configured yet.</p>
                <Button icon={<Plus size={16} />} onClick={() => setAddOpen(true)}>
                  Add your first feature flag
                </Button>
              </div>
            )}
            {sortedFlags.map(flag => {
              const enabled = flagEnabled(flag)
              return (
                <div key={flag.name} className="p-4 flex items-start gap-4">
                  <Zap
                    size={18}
                    className={`flex-shrink-0 mt-0.5 ${enabled ? 'text-warning-500' : 'text-gray-400'}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">{flagLabel(flag)}</p>
                      <Badge variant={enabled ? 'success' : 'gray'}>{enabled ? 'Enabled' : 'Disabled'}</Badge>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">
                      {flagDescription(flag)}
                    </p>
                    <p className="text-xs font-mono text-gray-400 dark:text-gray-500 mt-1.5">{flag.name}</p>
                  </div>
                  <FeatureToggle
                    enabled={enabled}
                    disabled={pending === flag.name}
                    onChange={next => toggleMut.mutate({ name: flag.name, is_enabled: next })}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add Feature Flag"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button loading={createMut.isPending} onClick={handleCreate}>Create</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input
            label="Feature key"
            placeholder="e.g. custom_reports_enabled"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            hint="Lowercase identifier used in code. Letters, numbers, and underscores only."
          />
          <div>
            <label htmlFor="flag-description" className="label">Description</label>
            <textarea
              id="flag-description"
              rows={3}
              className="input-field resize-none"
              placeholder="What does this flag control?"
              value={newDescription}
              onChange={e => setNewDescription(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Enabled by default</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Turn on immediately after creating</p>
            </div>
            <FeatureToggle enabled={newEnabled} onChange={setNewEnabled} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
