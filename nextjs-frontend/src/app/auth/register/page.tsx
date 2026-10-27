'use client'
import { Suspense, useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { authApi, settingsApi } from '@/lib/api'
import Link from 'next/link'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { Mail, Lock, User, Layers, Eye, EyeOff } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthHeading, authLink } from '../AuthShell'

const schema = z.object({
  firstName: z.string().min(1, 'First name is required'),
  lastName:  z.string().min(1, 'Last name is required'),
  email:     z.string().email('Valid email required'),
  password:  z.string().min(8, 'At least 8 characters'),
  confirm:   z.string(),
}).refine(d => d.password === d.confirm, { message: 'Passwords do not match', path: ['confirm'] })
type FormData = z.infer<typeof schema>

function RegisterInner() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const editionId    = searchParams.get('editionId')
  const editionName  = searchParams.get('editionName')

  const [loading, setLoading]         = useState(false)
  const [checkingPaywall, setChecking] = useState(true)
  const [showPw, setShowPw]           = useState(false)

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })
  const password = watch('password') || ''

  // Check paywall setting on mount; redirect if enabled and no edition chosen
  useEffect(() => {
    let cancelled = false
    settingsApi.getPublic().then((settings: { key: string; value: string | null }[]) => {
      if (cancelled) return
      const paywallEnabled = settings.find(s => s.key === 'registration.paywall_enabled')?.value === 'true'
      if (paywallEnabled && !editionId) {
        router.replace('/select-plan?redirect=/auth/register')
      }
    }).catch(() => {
      // If we can't load settings, allow registration to proceed
    }).finally(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [editionId, router])

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      await authApi.register({
        firstName:  data.firstName,
        lastName:   data.lastName,
        email:      data.email,
        password:   data.password,
        ...(editionId ? { edition_id: editionId } : {}),
      })
      toast.success('Account created! Please check your email to confirm.')
      router.push('/auth/login')
    } catch (err: unknown) {
      const msg = (err as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Registration failed'
      toast.error(msg)
    } finally { setLoading(false) }
  }

  if (checkingPaywall) {
    return <Spinner />
  }

  return (
    <>
      <AuthHeading
        eyebrow="Create account"
        title={<>Start building with <span className="site-serif">ffinn</span></>}
        lede="Set up your account, then describe the first thing your business needs."
      />

      {/* Selected plan */}
      {editionName && (
        <div className="mb-6 flex items-center justify-between gap-3 rounded-xl bg-accent/[0.07] px-3.5 py-3 text-sm ring-1 ring-accent/20">
          <div className="flex items-center gap-2.5 text-ink-soft">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent/15 text-accent"><Layers size={14} /></span>
            <span>Plan <span className="font-medium text-ink">{editionName}</span></span>
          </div>
          <Link href="/select-plan?redirect=/auth/register" className="text-[13px] text-ink-mute transition-colors hover:text-ink">
            Change
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-3">
          <Input {...register('firstName')} label="First name" placeholder="Ada" icon={<User size={15} />} error={errors.firstName?.message} autoComplete="given-name" autoFocus />
          <Input {...register('lastName')}  label="Last name"  placeholder="Lovelace" error={errors.lastName?.message} autoComplete="family-name" />
        </div>
        <Input {...register('email')} label="Work email" type="email" placeholder="you@company.com" icon={<Mail size={15} />} error={errors.email?.message} autoComplete="email" />
        <div>
          <Input
            {...register('password')}
            label="Password"
            type={showPw ? 'text' : 'password'}
            placeholder="At least 8 characters"
            icon={<Lock size={15} />}
            error={errors.password?.message}
            autoComplete="new-password"
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
          {!errors.password && <PasswordMeter length={password.length} />}
        </div>
        <Input {...register('confirm')} label="Confirm password" type={showPw ? 'text' : 'password'} placeholder="Type it again" error={errors.confirm?.message} autoComplete="new-password" />
        <Button type="submit" loading={loading} size="lg" className="w-full">Create account</Button>
      </form>

      <p className="mt-8 text-[14px] text-ink-mute">
        Already have an account?{' '}
        <Link href="/auth/login" className={authLink}>Sign in</Link>
      </p>
    </>
  )
}

/**
 * Length hint only. The server applies the full password policy (configurable digit, case and
 * symbol rules) and its message comes back in the error toast.
 */
function PasswordMeter({ length }: { length: number }) {
  const filled = length === 0 ? 0 : length < 8 ? 1 : length < 12 ? 2 : length < 16 ? 3 : 4
  const color = filled <= 1 ? 'bg-caution' : 'bg-signal'
  return (
    <div className="mt-2 flex items-center gap-3" aria-hidden>
      <div className="flex flex-1 gap-1">
        {[1, 2, 3, 4].map(i => (
          <span key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= filled ? color : 'bg-ink/10'}`} />
        ))}
      </div>
      <span className="w-24 text-right font-mono text-[11px] text-ink-mute">
        {length === 0 ? '8+ characters' : length < 8 ? `${8 - length} more` : 'length ok'}
      </span>
    </div>
  )
}

function Spinner() {
  return <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-2 border-ink/15 border-t-accent" /></div>
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <RegisterInner />
    </Suspense>
  )
}
