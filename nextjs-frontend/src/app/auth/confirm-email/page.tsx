'use client'
import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { MailCheck, MailX } from 'lucide-react'
import { AuthStatus, authLink } from '../AuthShell'
import Link from 'next/link'
import { Suspense } from 'react'

function ConfirmEmailContent() {
  const params = useSearchParams()
  const router = useRouter()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')

  useEffect(() => {
    const token = params.get('token')
    const email = params.get('email') || params.get('userId')
    if (!token) { setStatus('error'); return }
    authApi.confirmEmail({ token, email })
      .then(() => { setStatus('success'); setTimeout(() => router.push('/auth/login'), 3000) })
      .catch(() => setStatus('error'))
  }, [params, router])

  if (status === 'loading') return <LoadingSpinner label="Confirming your email…" />
  if (status === 'success') return (
    <AuthStatus tone="ok" icon={<MailCheck size={22} />} title="Email confirmed">
      <p>Your account is ready. Taking you to sign in…</p>
      <p><Link href="/auth/login" className={authLink}>Sign in now</Link></p>
    </AuthStatus>
  )
  return (
    <AuthStatus tone="bad" icon={<MailX size={22} />} title="We couldn't confirm your email">
      <p>The link may be incomplete or expired. Open the newest confirmation email and try its link again.</p>
      <p><Link href="/auth/login" className={authLink}>Back to sign in</Link></p>
    </AuthStatus>
  )
}

export default function ConfirmEmailPage() {
  return <Suspense><ConfirmEmailContent /></Suspense>
}
