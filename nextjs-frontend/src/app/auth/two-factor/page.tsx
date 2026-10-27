'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { authApi, tokenStore } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import Link from 'next/link'
import { ArrowLeft, ShieldAlert, ShieldCheck } from 'lucide-react'
import { AuthHeading, AuthStatus, authLink } from '../AuthShell'

function TwoFactorInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { refreshUser } = useAuth()
  const userId = searchParams.get('userId')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [useRecovery, setUseRecovery] = useState(false)

  if (!userId) {
    return (
      <AuthStatus tone="bad" icon={<ShieldAlert size={22} />} title="Your sign-in expired">
        <p>We couldn&apos;t find the sign-in this code belongs to. Start again with your email and password.</p>
        <p><Link href="/auth/login" className={authLink}>Back to sign in</Link></p>
      </AuthStatus>
    )
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!code.trim()) {
      toast.error('Enter your verification code')
      return
    }
    setLoading(true)
    try {
      const res = await authApi.verifyTwoFactor({
        user_id: userId,
        code: code.trim(),
        is_recovery: useRecovery,
      }) as { access_token?: string }
      if (!res.access_token) throw new Error('Verification failed')
      tokenStore.set(res.access_token)
      await refreshUser()
      toast.success('Signed in successfully')
      router.replace('/app/dashboard')
    } catch {
      toast.error('Invalid verification code')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <span className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-accent/10 text-accent"><ShieldCheck size={22} /></span>
      <AuthHeading
        eyebrow="Two-step verification"
        title={useRecovery ? 'Use a recovery code' : 'Enter your code'}
        lede={useRecovery ? 'Enter one of the recovery codes you saved when you turned on two-step verification.' : 'Open your authenticator app and enter the current code for ffinn.'}
      />
      <form onSubmit={onSubmit} className="space-y-4">
        <Input
          label={useRecovery ? 'Recovery code' : 'Verification code'}
          value={code}
          onChange={e => setCode(e.target.value)}
          autoComplete="one-time-code"
          inputMode={useRecovery ? 'text' : 'numeric'}
          className="h-12 text-center font-mono text-lg tracking-[0.3em]"
          autoFocus
        />
        <Button type="submit" size="lg" className="w-full" loading={loading}>Verify</Button>
      </form>
      <button
        type="button"
        className={`mt-6 text-[14px] ${authLink}`}
        onClick={() => { setUseRecovery(v => !v); setCode('') }}
      >
        {useRecovery ? 'Use authenticator code instead' : 'Use a recovery code instead'}
      </button>
      <p className="mt-8 text-[14px]">
        <Link href="/auth/login" className="inline-flex items-center gap-1.5 text-ink-mute transition-colors hover:text-ink">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
      </p>
    </>
  )
}

export default function TwoFactorPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-mute">Loading…</p>}>
      <TwoFactorInner />
    </Suspense>
  )
}
