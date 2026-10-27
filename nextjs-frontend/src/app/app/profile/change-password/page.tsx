'use client'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Save } from 'lucide-react'
import toast from 'react-hot-toast'
import { useRouter } from 'next/navigation'

const schema = z.object({
  currentPassword: z.string().min(1, 'Current password required'),
  newPassword: z.string().min(8, 'Minimum 8 characters'),
  confirmPassword: z.string().min(1, 'Confirm your password'),
}).refine(d => d.newPassword === d.confirmPassword, { message: 'Passwords do not match', path: ['confirmPassword'] })

type Form = z.infer<typeof schema>

export default function ChangePasswordPage() {
  const router = useRouter()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) })

  const mutation = useMutation({
    mutationFn: (d: Form) => authApi.changePassword({ currentPassword: d.currentPassword, newPassword: d.newPassword }),
    onSuccess: () => { toast.success('Password changed successfully'); reset(); router.push('/app/profile') },
    onError: (e: unknown) => toast.error((e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? 'Failed to change password'),
  })

  return (
    <div className="space-y-4 max-w-md">
      <Breadcrumb crumbs={[{ label: 'Profile', href: '/app/profile' }, { label: 'Change Password' }]} />
      <PageHeader title="Change Password" subtitle="Update your account password" />

      <div className="card p-6">
        <form onSubmit={handleSubmit(d => mutation.mutate(d))} className="space-y-4">
          <Input {...register('currentPassword')} type="password" label="Current password" autoComplete="current-password" error={errors.currentPassword?.message} />
          <Input {...register('newPassword')} type="password" label="New password" autoComplete="new-password" error={errors.newPassword?.message} />
          <Input {...register('confirmPassword')} type="password" label="Confirm new password" autoComplete="new-password" error={errors.confirmPassword?.message} />

          <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
            <p className="font-medium mb-1">Password requirements</p>
            <ul className="list-disc pl-4 space-y-0.5">
              <li>Minimum 8 characters</li>
              <li>Mix of letters, numbers, and symbols recommended</li>
            </ul>
          </div>

          <Button type="submit" icon={<Save size={15} />} loading={mutation.isPending}>Update password</Button>
        </form>
      </div>
    </div>
  )
}
