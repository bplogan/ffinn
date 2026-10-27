'use client'
import { Suspense, useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth, type TenantChoice } from '@/contexts/AuthContext'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { Mail, Lock, Eye, EyeOff, Building2, ChevronDown, ChevronRight, ArrowLeft, Loader2 } from 'lucide-react'
import { authApi, settingsApi, tokenStore } from '@/lib/api'
import type { SsoProvider } from '@/types'
import { AuthHeading, authLink } from '../AuthShell'

const schema = z.object({
  usernameOrEmail: z.string().min(1, 'Email or username is required'),
  password:        z.string().min(1, 'Password is required'),
  tenantName:      z.string().optional(),
})
type FormData = z.infer<typeof schema>

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-mute">Loading…</p>}>
      <LoginPageContent />
    </Suspense>
  )
}

function LoginPageContent() {
  const { login, refreshUser } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [registrationAllowed, setRegistrationAllowed] = useState<boolean | null>(null)
  const [ssoProviders, setSsoProviders] = useState<SsoProvider[]>([])
  const [ssoLoading, setSsoLoading] = useState(false)
  // The API finds your organization from your email, so the field is only needed for SSO.
  const [orgOpen, setOrgOpen] = useState(() => !!searchParams.get('tenant'))
  // Set when the same sign-in exists in several organizations; the form then asks which one.
  const [tenantChoices, setTenantChoices] = useState<TenantChoice[] | null>(null)
  const [choosing, setChoosing] = useState<string | null>(null)

  const { register, handleSubmit, watch, getValues, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { tenantName: searchParams.get('tenant') || '' },
  })
  const tenantName = watch('tenantName')

  useEffect(() => {
    let cancelled = false
    settingsApi.getPublic()
      .then(rows => {
        if (cancelled) return
        const row = rows.find(r => r.key === 'registration.allow_user_registration')
        setRegistrationAllowed(row ? row.value === 'true' : true)
      })
      .catch(() => { if (!cancelled) setRegistrationAllowed(true) })
    return () => { cancelled = true }
  }, [])

  // Handle SSO exchange code or errors in query string
  useEffect(() => {
    const ssoCode = searchParams.get('sso_code')
    const legacyToken = searchParams.get('sso_token')
    const error = searchParams.get('error')
    if (error) {
      toast.error(decodeURIComponent(error))
      return
    }
    if (!ssoCode && !legacyToken) return

    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        if (ssoCode) {
          const res = await authApi.ssoExchange(ssoCode) as { access_token?: string }
          if (!res.access_token) throw new Error('SSO exchange failed')
          tokenStore.set(res.access_token)
        } else if (legacyToken) {
          tokenStore.set(legacyToken)
        }
        await refreshUser()
        if (!cancelled) {
          toast.success('Signed in with SSO')
          router.replace('/app/dashboard')
        }
      } catch {
        if (!cancelled) toast.error('SSO sign-in failed')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [searchParams, refreshUser, router])

  // Load SSO providers when tenant name is provided
  useEffect(() => {
    const name = tenantName?.trim()
    if (!name) {
      setSsoProviders([])
      return
    }
    let cancelled = false
    setSsoLoading(true)
    authApi.getTenantSsoProviders(name)
      .then(res => { if (!cancelled) setSsoProviders(res.providers || []) })
      .catch(() => { if (!cancelled) setSsoProviders([]) })
      .finally(() => { if (!cancelled) setSsoLoading(false) })
    return () => { cancelled = true }
  }, [tenantName])

  const signIn = async (data: FormData, tenant?: string) => {
    try {
      const res = await login(data.usernameOrEmail, data.password, tenant || data.tenantName?.trim() || undefined)
      if (res.requiresTwoFactor && res.userId) {
        router.push(`/auth/two-factor?userId=${encodeURIComponent(res.userId)}`)
        return
      }
      if (res.tenants) { setTenantChoices(res.tenants); return }
      toast.success('Welcome back!')
      router.push('/app/dashboard')
    } catch (err: unknown) {
      const msg = (err as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Invalid credentials'
      toast.error(msg)
    }
  }

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try { await signIn(data) } finally { setLoading(false) }
  }

  const chooseTenant = async (name: string) => {
    setChoosing(name)
    try { await signIn(getValues(), name) } finally { setChoosing(null) }
  }

  const startSso = (configId: string) => {
    window.location.href = authApi.ssoLogin(configId, `${window.location.origin}/auth/login`)
  }

  if (tenantChoices) {
    return (
      <>
        <AuthHeading
          eyebrow="Sign in"
          title={<>Choose an <span className="site-serif">organization</span></>}
          lede={<><span className="font-medium text-ink">{getValues('usernameOrEmail')}</span> has an account in more than one organization. Which one do you want to open?</>}
        />
        <ul className="space-y-2">
          {tenantChoices.map(t => (
            <li key={t.name}>
              <button
                type="button"
                onClick={() => chooseTenant(t.name)}
                disabled={!!choosing}
                className="group flex w-full items-center gap-3 rounded-2xl bg-surface px-4 py-3.5 text-left ring-1 ring-ink/10 transition-[box-shadow,opacity] hover:ring-ink/25 disabled:opacity-60"
              >
                <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-xl bg-accent/10 font-display text-[13px] font-semibold text-accent">
                  {t.name.trim().charAt(0).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1 truncate text-[15px] font-medium">{t.name}</span>
                {choosing === t.name
                  ? <Loader2 size={16} className="animate-spin text-ink-mute" />
                  : <ChevronRight size={16} className="text-ink-mute transition-transform group-hover:translate-x-0.5 group-hover:text-ink" />}
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-8 text-[14px]">
          <button
            type="button"
            onClick={() => setTenantChoices(null)}
            className="inline-flex items-center gap-1.5 text-ink-mute transition-colors hover:text-ink"
          >
            <ArrowLeft size={14} /> Use a different account
          </button>
        </p>
      </>
    )
  }

  return (
    <>
      <AuthHeading
        eyebrow="Sign in"
        title={<>Welcome <span className="site-serif">back</span></>}
        lede="Sign in to your ffinn workspace."
      />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          {...register('usernameOrEmail')}
          label="Email or username"
          placeholder="you@company.com"
          icon={<Mail size={15} />}
          error={errors.usernameOrEmail?.message}
          autoComplete="username"
          autoFocus
        />
        <Input
          {...register('password')}
          label={
            <span className="flex items-center justify-between">
              Password
              <Link href="/auth/forgot-password" className="text-[13px] font-normal text-ink-mute transition-colors hover:text-ink">
                Forgot password?
              </Link>
            </span>
          }
          id="password"
          aria-label="Password"
          type={showPw ? 'text' : 'password'}
          placeholder="••••••••"
          icon={<Lock size={15} />}
          error={errors.password?.message}
          autoComplete="current-password"
          rightElement={
            <button
              type="button"
              onClick={() => setShowPw(v => !v)}
              aria-label={showPw ? 'Hide password' : 'Show password'}
              className="grid h-7 w-7 place-items-center rounded-full text-ink-mute transition-colors hover:bg-ink/[0.06] hover:text-ink"
            >
              {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          }
        />

        <div className="rounded-xl border border-dashed border-ink/15">
          <button
            type="button"
            onClick={() => setOrgOpen(o => !o)}
            aria-expanded={orgOpen}
            aria-controls="org-signin"
            className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-[13px] text-ink-soft transition-colors hover:text-ink"
          >
            <Building2 size={15} className="text-ink-mute" />
            <span className="flex-1">Signing in with your organization&apos;s SSO?</span>
            <ChevronDown size={15} className={`text-ink-mute transition-transform ${orgOpen ? 'rotate-180' : ''}`} />
          </button>
          {orgOpen && (
            <div id="org-signin" className="site-fade-in border-t border-dashed border-ink/15 px-3.5 pb-3.5 pt-3">
              <Input
                {...register('tenantName')}
                label="Organization"
                placeholder="Your organization name"
                error={errors.tenantName?.message}
                autoComplete="organization"
                hint="Shows your organization's single sign-on options. Password sign-in finds your organization from your email."
              />
              {tenantName?.trim() && (
                <div className="mt-3 space-y-2">
                  {ssoLoading ? (
                    <p className="text-[13px] text-ink-mute">Looking up sign-on options…</p>
                  ) : ssoProviders.length === 0 ? (
                    <p className="text-[13px] text-ink-mute">No single sign-on is set up for this organization.</p>
                  ) : (
                    ssoProviders.map(p => (
                      <Button
                        key={p.id}
                        type="button"
                        variant="secondary"
                        className="w-full"
                        onClick={() => startSso(p.id)}
                      >
                        Continue with {p.provider_name}
                      </Button>
                    ))
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <Button type="submit" loading={loading} size="lg" className="w-full">Sign in</Button>
      </form>

      {registrationAllowed && (
        <p className="mt-8 text-[14px] text-ink-mute">
          New to ffinn?{' '}
          <Link href="/auth/register" className={authLink}>Create an account</Link>
        </p>
      )}
    </>
  )
}
