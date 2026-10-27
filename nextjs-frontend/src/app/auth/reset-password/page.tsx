'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams, useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'
import { ArrowLeft, Lock } from 'lucide-react'
import Link from 'next/link'
import { AuthHeading } from '../AuthShell'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Suspense } from 'react'

const schema = z.object({
  password: z.string().min(8, 'At least 8 characters'),
  confirm:  z.string(),
}).refine(d => d.password === d.confirm, { message: 'Passwords do not match', path: ['confirm'] })
type FormData = z.infer<typeof schema>

function ResetPasswordForm() {
  const router = useRouter()
  const params = useSearchParams()
  const [loading, setLoading] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      await authApi.resetPassword({ token: params.get('token'), email: params.get('email'), newPassword: data.password })
      toast.success('Password reset successfully')
      router.push('/auth/login')
    } catch { toast.error('Reset failed — link may have expired') }
    finally { setLoading(false) }
  }

  return (
    <>
      <AuthHeading eyebrow="Password reset" title="Choose a new password" lede="Use at least 8 characters. You'll sign in with it next." />
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input {...register('password')} label="New password"      type="password" placeholder="At least 8 characters" icon={<Lock size={15} />} error={errors.password?.message} autoComplete="new-password" autoFocus />
        <Input {...register('confirm')}  label="Confirm password"  type="password" placeholder="Type it again" error={errors.confirm?.message} autoComplete="new-password" />
        <Button type="submit" loading={loading} size="lg" className="w-full">Set new password</Button>
      </form>
      <p className="mt-8 text-[14px]">
        <Link href="/auth/login" className="inline-flex items-center gap-1.5 text-ink-mute transition-colors hover:text-ink">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
      </p>
    </>
  )
}

export default function ResetPasswordPage() {
  return <Suspense><ResetPasswordForm /></Suspense>
}
