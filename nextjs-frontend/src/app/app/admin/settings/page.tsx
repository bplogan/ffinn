'use client'
import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Save, Send, Globe, Users, Shield, Mail, CreditCard, HardDrive,
} from 'lucide-react'
import toast from 'react-hot-toast'

// ─── Types ───────────────────────────────────────────────────────────────────

type SettingRow = {
  key: string
  value?: string | null
  is_encrypted?: boolean
  isEncrypted?: boolean
}

type TabId = 'general' | 'registration' | 'security' | 'smtp' | 'payments' | 'storage'

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'general',      label: 'General',      icon: <Globe      size={14} /> },
  { id: 'registration', label: 'Registration',  icon: <Users      size={14} /> },
  { id: 'security',     label: 'Security',      icon: <Shield     size={14} /> },
  { id: 'smtp',         label: 'Email (SMTP)',  icon: <Mail       size={14} /> },
  { id: 'payments',     label: 'Payments',      icon: <CreditCard size={14} /> },
  { id: 'storage',      label: 'Storage',       icon: <HardDrive  size={14} /> },
]

const TAB_KEYS: Record<TabId, string[]> = {
  general: ['general.app_name', 'general.app_url', 'general.support_email'],
  registration: [
    'registration.allow_user_registration',
    'registration.allow_tenant_registration',
    'registration.new_users_active_by_default',
    'registration.require_email_confirmation',
    'registration.restricted_email_domains_enabled',
    'registration.allowed_email_domains',
    'registration.paywall_enabled',
  ],
  security: [
    'security.password_min_length',
    'security.password_require_digit',
    'security.password_require_lowercase',
    'security.password_require_uppercase',
    'security.password_require_special',
    'security.lockout_enabled',
    'security.lockout_max_attempts',
    'security.lockout_duration_seconds',
    'security.two_factor_enabled',
    'security.jwt_access_minutes',
    'security.jwt_refresh_days',
  ],
  smtp: [
    'smtp.from_address', 'smtp.from_name',
    'smtp.host', 'smtp.port', 'smtp.use_ssl', 'smtp.use_auth',
    'smtp.username', 'smtp.password',
  ],
  payments: [
    'payments.stripe_enabled', 'payments.stripe_publishable_key',
    'payments.stripe_secret_key', 'payments.stripe_webhook_secret',
    'payments.paypal_enabled', 'payments.paypal_mode',
    'payments.paypal_client_id', 'payments.paypal_client_secret',
    'payments.paypal_webhook_id',
  ],
  storage: [
    'storage.backend',
    'storage.azure_connection_string', 'storage.azure_container',
    'storage.s3_bucket', 'storage.aws_region',
    'storage.aws_access_key_id', 'storage.aws_secret_access_key',
  ],
}

// ─── Small helpers ────────────────────────────────────────────────────────────

function SectionHeader({ title, desc }: { title: string; desc?: string }) {
  return (
    <div className="mb-5">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
      {desc && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{desc}</p>}
    </div>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{children}</p>
}

// ─── Settings context (lets field components live at module level) ────────────

type SettingsCtxType = {
  vals: Record<string, string>
  rows?: SettingRow[]
  set: (key: string, v: string) => void
  encrypted: (key: string) => boolean
  get: (key: string, def?: string) => string
  getBool: (key: string, def?: boolean) => boolean
  setBool: (key: string, v: boolean) => void
}

const SettingsContext = React.createContext<SettingsCtxType>({} as SettingsCtxType)

// ─── Field components (module-level so React never remounts them on re-render) ─

function Toggle({ id, label, desc }: { id: string; label: string; desc?: string }) {
  const { getBool, setBool } = React.useContext(SettingsContext)
  return (
    <div className="flex items-start justify-between py-3.5">
      <div className="flex-1 min-w-0 pr-4">
        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{label}</p>
        {desc && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{desc}</p>}
      </div>
      <button
        type="button"
        onClick={() => setBool(id, !getBool(id))}
        role="switch"
        aria-checked={getBool(id)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 ${
          getBool(id) ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-600'
        }`}
      >
        <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ${getBool(id) ? 'translate-x-4' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

function TextField({ id, label, placeholder, hint, type = 'text' }: {
  id: string; label: string; placeholder?: string; hint?: string; type?: string
}) {
  const { vals, set, encrypted } = React.useContext(SettingsContext)
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        type={encrypted(id) ? 'password' : type}
        className="input-field"
        value={vals[id] ?? ''}
        onChange={e => set(id, e.target.value)}
        placeholder={encrypted(id) ? '••••••••' : placeholder}
      />
      {hint && <Hint>{hint}</Hint>}
    </div>
  )
}

function PasswordField({ id, label, placeholder, hint }: {
  id: string; label: string; placeholder?: string; hint?: string
}) {
  const { vals, set } = React.useContext(SettingsContext)
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        type="password"
        className="input-field"
        value={vals[id] ?? ''}
        onChange={e => set(id, e.target.value)}
        placeholder={placeholder ?? '••••••••'}
      />
      {hint && <Hint>{hint}</Hint>}
    </div>
  )
}

function NumberField({ id, label, hint, min, max }: {
  id: string; label: string; hint?: string; min?: number; max?: number
}) {
  const { vals, set } = React.useContext(SettingsContext)
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        className="input-field"
        value={vals[id] ?? ''}
        onChange={e => set(id, e.target.value)}
      />
      {hint && <Hint>{hint}</Hint>}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminSettingsPage() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabId>('general')
  const [vals, setVals]           = useState<Record<string, string>>({})
  const [testTo, setTestTo]       = useState('')
  const [touched, setTouched]     = useState<Set<string>>(new Set())

  const { data: rows, isLoading } = useQuery<SettingRow[]>({
    queryKey: ['admin-settings'],
    queryFn:  () => settingsApi.getAll() as Promise<SettingRow[]>,
  })

  useEffect(() => {
    if (!rows) return
    setVals(prev => {
      const base: Record<string, string> = {}
      rows.forEach(r => { base[r.key] = r.value ?? '' })
      return { ...base, ...prev }
    })
  }, [rows])

  const encrypted = (key: string) => {
    const r = rows?.find(r => r.key === key)
    return !!(r?.is_encrypted || r?.isEncrypted)
  }

  const get     = (key: string, def = '')    => vals[key] ?? def
  const getBool = (key: string, def = false) => (vals[key] ?? (def ? 'true' : 'false')) === 'true'

  const set = (key: string, v: string) => {
    setVals(prev => ({ ...prev, [key]: v }))
    setTouched(prev => new Set([...prev, key]))
  }
  const setBool = (key: string, v: boolean) => set(key, v ? 'true' : 'false')

  const hasDirty = (tabId: TabId) => TAB_KEYS[tabId].some(k => touched.has(k))

  const saveMut = useMutation({
    mutationFn: (keys: string[]) =>
      settingsApi.update({ settings: keys.map(k => ({ key: k, value: vals[k] ?? '' })) }) as Promise<unknown>,
    onSuccess: (_d, keys) => {
      toast.success('Settings saved')
      setTouched(prev => { const n = new Set(prev); keys.forEach(k => n.delete(k)); return n })
      qc.invalidateQueries({ queryKey: ['admin-settings'] })
    },
    onError: () => toast.error('Save failed'),
  })

  const testMut = useMutation({
    mutationFn: (to: string) => settingsApi.testEmail(to) as Promise<unknown>,
    onSuccess: () => toast.success('Test email sent successfully'),
    onError:   () => toast.error('Failed to send test email — check SMTP settings'),
  })

  const saveTab = () => {
    const keys = TAB_KEYS[activeTab].filter(k => touched.has(k))
    if (!keys.length) {
      toast.error('No changes to save')
      return
    }
    saveMut.mutate(keys)
  }

  if (isLoading) return <LoadingSpinner fullPage />

  const ctxValue: SettingsCtxType = { vals, rows, set, encrypted, get, getBool, setBool }

  return (
    <SettingsContext.Provider value={ctxValue}>
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Configure application-wide settings for this instance" />

      {/* Tab bar */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex gap-0 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300'
              }`}
            >
              {tab.icon}
              {tab.label}
              {hasDirty(tab.id) && (
                <span className="ml-1 h-1.5 w-1.5 rounded-full bg-warning-400 inline-block" title="Unsaved changes" />
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="max-w-3xl space-y-4">

        {/* ── General ──────────────────────────────────────────────────── */}
        {activeTab === 'general' && (
          <div className="card p-6 space-y-5">
            <SectionHeader
              title="Application"
              desc="Basic identity and URL configuration for this ffinn instance."
            />
            <TextField id="general.app_name" label="Application Name" placeholder="ffinn"
              hint="Appears in email headers, page titles, and notifications." />
            <TextField id="general.app_url" label="Application URL" placeholder="https://yourapp.com"
              hint="Base URL used in email confirmation links and redirects." />
            <TextField id="general.support_email" label="Support Email" placeholder="support@yourapp.com"
              hint="Shown in error messages and user-facing emails." />
          </div>
        )}

        {/* ── Registration ─────────────────────────────────────────────── */}
        {activeTab === 'registration' && (
          <>
            <div className="card p-6">
              <SectionHeader title="Form-Based Registration" />
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                <Toggle
                  id="registration.allow_user_registration"
                  label="Allow users to register to an existing tenant"
                  desc="If disabled, new user accounts can only be created by an admin."
                />
                <Toggle
                  id="registration.allow_tenant_registration"
                  label="Allow new tenants to self-register"
                  desc="If disabled, new tenants can only be created by an admin using the tenant management page."
                />
                <Toggle
                  id="registration.new_users_active_by_default"
                  label="New registered tenants are active by default"
                  desc="If you disable this, new tenants will not be active (and cannot login) until admin manually activates the account."
                />
                <Toggle
                  id="registration.require_email_confirmation"
                  label="Email confirmation required for login"
                  desc="Users must confirm their email address before they can log in."
                />
                <Toggle
                  id="registration.paywall_enabled"
                  label="Require edition selection during tenant registration"
                  desc="When enabled, new tenants must choose a pricing edition before they can complete registration. Create editions under Platform Setup → Editions."
                />
              </div>
            </div>

            <div className="card p-6 space-y-4">
              <SectionHeader title="Email Domain Restrictions" />
              <Toggle
                id="registration.restricted_email_domains_enabled"
                label="Restrict registrations by email domain"
                desc="Only allow sign-ups from the email domains listed below."
              />
              {getBool('registration.restricted_email_domains_enabled') && (
                <TextField
                  id="registration.allowed_email_domains"
                  label="Allowed Email Domains"
                  placeholder="example.com, company.org"
                  hint="Comma-separated list of allowed domains."
                />
              )}
            </div>
          </>
        )}

        {/* ── Security ─────────────────────────────────────────────────── */}
        {activeTab === 'security' && (
          <>
            <div className="card p-6">
              <SectionHeader title="Password Complexity" desc="Rules enforced when users create or change their password." />
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                <Toggle id="security.password_require_digit"     label="Require digit" />
                <Toggle id="security.password_require_lowercase" label="Require lowercase letter" />
                <Toggle id="security.password_require_uppercase" label="Require uppercase letter" />
                <Toggle id="security.password_require_special"   label="Require non-alphanumeric character" />
              </div>
              <div className="mt-5 max-w-xs">
                <NumberField id="security.password_min_length" label="Required minimum length" min={4} max={128} />
              </div>
            </div>

            <div className="card p-6 space-y-4">
              <SectionHeader title="User Lock Out" />
              <Toggle
                id="security.lockout_enabled"
                label="Enable user account locking on failed login attempts"
              />
              {getBool('security.lockout_enabled', true) && (
                <div className="grid grid-cols-2 gap-4 pt-1">
                  <NumberField
                    id="security.lockout_max_attempts"
                    label="Maximum number of failed attempts before lock"
                    min={1} max={20}
                  />
                  <NumberField
                    id="security.lockout_duration_seconds"
                    label="Account locking duration (seconds)"
                    min={30}
                    hint="300 = 5 minutes"
                  />
                </div>
              )}
            </div>

            <div className="card p-6">
              <SectionHeader title="Two Factor Login" />
              <Toggle
                id="security.two_factor_enabled"
                label="Enable two-factor user login"
                desc="Allow users to enrol TOTP-based 2FA from their account settings."
              />
            </div>

            <div className="card p-6">
              <SectionHeader title="Session &amp; Token Expiry" desc="Controls how long issued tokens remain valid." />
              <div className="grid grid-cols-2 gap-4">
                <NumberField id="security.jwt_access_minutes" label="Access token expiry (minutes)" min={5}
                  hint="Typical: 60–120 minutes." />
                <NumberField id="security.jwt_refresh_days" label="Refresh token expiry (days)" min={1}
                  hint="Typical: 7–30 days." />
              </div>
            </div>
          </>
        )}

        {/* ── Email (SMTP) ──────────────────────────────────────────────── */}
        {activeTab === 'smtp' && (
          <>
            <div className="card p-6 space-y-5">
              <SectionHeader title="Sender Identity" />
              <div className="grid grid-cols-2 gap-4">
                <TextField id="smtp.from_address" label="Default from (sender) email address" placeholder="noreply@yourapp.com" />
                <TextField id="smtp.from_name"    label="Default from (sender) display name"  placeholder="ffinn" />
              </div>
            </div>

            <div className="card p-6 space-y-5">
              <SectionHeader title="SMTP Server" />
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <TextField id="smtp.host" label="SMTP host" placeholder="smtp-pulse.com" />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="smtp.port" className="label">SMTP port</label>
                  <select
                    id="smtp.port"
                    className="input-field"
                    value={get('smtp.port', '587')}
                    onChange={e => set('smtp.port', e.target.value)}
                  >
                    <option value="25">25</option>
                    <option value="465">465 (SSL)</option>
                    <option value="587">587 (TLS)</option>
                    <option value="2525">2525</option>
                  </select>
                </div>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                <Toggle id="smtp.use_ssl"  label="Use SSL" desc="Recommended. Required for port 465; use STARTTLS for 587." />
                <Toggle id="smtp.use_auth" label="Use Authentication" desc="Provide SMTP credentials below." />
              </div>
              {getBool('smtp.use_auth', true) && (
                <div className="grid grid-cols-2 gap-4 pt-1">
                  <TextField id="smtp.username" label="User name" placeholder="user@example.com" />
                  <PasswordField id="smtp.password" label="Password" hint="Stored encrypted." />
                </div>
              )}
            </div>

            <div className="card p-6 space-y-4">
              <SectionHeader
                title="Test Email Settings"
                desc="Save your SMTP settings first, then send a test message to verify delivery."
              />
              <div className="flex gap-3 items-end">
                <div className="flex-1">
                  <Input
                    label="Send test email to"
                    type="email"
                    placeholder="your@email.com"
                    value={testTo}
                    onChange={e => setTestTo(e.target.value)}
                  />
                </div>
                <Button
                  variant="secondary"
                  icon={<Send size={14} />}
                  loading={testMut.isPending}
                  disabled={!testTo}
                  onClick={() => testMut.mutate(testTo)}
                >
                  Send Test Email
                </Button>
              </div>
            </div>
          </>
        )}

        {/* ── Payments ──────────────────────────────────────────────────── */}
        {activeTab === 'payments' && (
          <>
            <div className="card p-6 space-y-5">
              <SectionHeader title="Stripe" desc="Enable Stripe to allow subscription billing and payment processing." />
              <Toggle id="payments.stripe_enabled" label="Stripe enabled" />
              {getBool('payments.stripe_enabled', true) && (
                <>
                  <TextField id="payments.stripe_publishable_key" label="Publishable Key" placeholder="pk_live_…"
                    hint="Safe to expose to the browser." />
                  <PasswordField id="payments.stripe_secret_key" label="Secret Key"
                    placeholder="sk_live_… (encrypted)" hint="Keep this secret — never expose to the browser." />
                  <PasswordField id="payments.stripe_webhook_secret" label="Webhook Secret"
                    placeholder="whsec_… (encrypted)"
                    hint="Found in Stripe Dashboard → Webhooks → your endpoint." />
                </>
              )}
            </div>

            <div className="card p-6 space-y-5">
              <SectionHeader title="PayPal" desc="Configure PayPal as an alternative payment method." />
              <Toggle id="payments.paypal_enabled" label="PayPal enabled" />
              {getBool('payments.paypal_enabled') && (
                <>
                  <div className="space-y-1.5">
                    <label htmlFor="payments.paypal_mode" className="label">PayPal Mode</label>
                    <select id="payments.paypal_mode" className="input-field"
                      value={get('payments.paypal_mode', 'sandbox')}
                      onChange={e => set('payments.paypal_mode', e.target.value)}>
                      <option value="sandbox">Sandbox (testing)</option>
                      <option value="live">Live (production)</option>
                    </select>
                  </div>
                  <TextField id="payments.paypal_client_id" label="Client ID" placeholder="AaBbCc…" />
                  <PasswordField id="payments.paypal_client_secret" label="Client Secret" placeholder="(encrypted)" />
                  <TextField id="payments.paypal_webhook_id" label="Webhook ID" placeholder="WH-…" hint="From PayPal Developer → Webhooks after creating the listener." />
                </>
              )}
            </div>
          </>
        )}

        {/* ── Storage ───────────────────────────────────────────────────── */}
        {activeTab === 'storage' && (
          <>
            <div className="card p-6 space-y-5">
              <SectionHeader title="File Storage Backend" desc="Choose where uploaded files (logos, attachments) are stored." />
              <div className="space-y-1.5">
                <label htmlFor="storage.backend" className="label">Storage Backend</label>
                <select id="storage.backend" className="input-field"
                  value={get('storage.backend', 'local')}
                  onChange={e => set('storage.backend', e.target.value)}>
                  <option value="local">Local filesystem</option>
                  <option value="azure">Azure Blob Storage</option>
                  <option value="s3">Amazon S3</option>
                </select>
              </div>
            </div>

            {get('storage.backend', 'local') === 'azure' && (
              <div className="card p-6 space-y-5">
                <SectionHeader title="Azure Blob Storage" />
                <PasswordField id="storage.azure_connection_string" label="Connection String"
                  placeholder="DefaultEndpointsProtocol=https;… (encrypted)"
                  hint="Found in Azure Portal → Storage Account → Access keys." />
                <TextField id="storage.azure_container" label="Container Name" placeholder="uploads" />
              </div>
            )}

            {get('storage.backend', 'local') === 's3' && (
              <div className="card p-6 space-y-5">
                <SectionHeader title="Amazon S3" />
                <div className="grid grid-cols-2 gap-4">
                  <TextField id="storage.s3_bucket"  label="Bucket Name" placeholder="my-bucket" />
                  <TextField id="storage.aws_region" label="AWS Region"  placeholder="us-east-1" />
                </div>
                <PasswordField id="storage.aws_access_key_id"     label="Access Key ID"     placeholder="AKIA… (encrypted)" />
                <PasswordField id="storage.aws_secret_access_key" label="Secret Access Key" placeholder="(encrypted)" />
              </div>
            )}
          </>
        )}

        {/* Save row */}
        <div className="flex justify-end pt-2">
          <Button
            icon={<Save size={15} />}
            loading={saveMut.isPending}
            onClick={saveTab}
          >
            Save all
          </Button>
        </div>

      </div>
    </div>
    </SettingsContext.Provider>
  )
}
