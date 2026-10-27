'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { authApi } from '@/lib/api'
import Link from 'next/link'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { Mail, ArrowLeft, MailCheck } from 'lucide-react'
import { AuthHeading, AuthStatus, authLink } from '../AuthShell'

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<{ email: string }>()

  const onSubmit = async (data: { email: string }) => {
    setLoading(true)
    try {
      await authApi.forgotPassword(data)
      setSent(true)
    } catch {
      toast.error('Failed to send reset email')
    } finally { setLoading(false) }
  }

  if (sent) return (
    <AuthStatus tone="ok" icon={<MailCheck size={22} />} title="Check your email">
      <p>If an account matches that address, a password reset link is on its way. It can take a minute to arrive.</p>
      <p><Link href="/auth/login" className={authLink}>Back to sign in</Link></p>
    </AuthStatus>
  )

  return (
    <>
      <AuthHeading eyebrow="Password reset" title="Forgot your password?" lede="Enter the email on your account and we'll send you a link to set a new one." />
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input {...register('email', { required: 'Email is required' })} label="Email" type="email" placeholder="you@company.com" icon={<Mail size={15} />} error={errors.email?.message} autoComplete="email" autoFocus />
        <Button type="submit" loading={loading} size="lg" className="w-full">Send reset link</Button>
      </form>
      <p className="mt-8 text-[14px]">
        <Link href="/auth/login" className="inline-flex items-center gap-1.5 text-ink-mute transition-colors hover:text-ink">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
      </p>
    </>
  )
}
