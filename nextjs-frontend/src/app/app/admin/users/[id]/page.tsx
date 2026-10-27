'use client'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '@/lib/api'
import { useRouter, useParams } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Breadcrumb from '@/components/ui/Breadcrumb'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import type { UserListItem } from '@/types'
import Link from 'next/link'
import { Shield, ShieldCheck } from 'lucide-react'

const schema = z.object({
  firstName: z.string().min(1, 'Required'),
  lastName:  z.string().min(1, 'Required'),
  email:     z.string().email(),
  userName:  z.string().optional(),
  password:  z.string().optional(),
  isActive:  z.boolean().optional(),
})
type FormData = z.infer<typeof schema>

export default function UserFormPage() {
  const router = useRouter()
  const params = useParams()
  const qc = useQueryClient()
  const id = params?.id as string | undefined
  const isEdit = !!id && id !== 'new'

  const { data: user, isLoading } = useQuery<UserListItem>({
    queryKey: ['user', id],
    queryFn: () => usersApi.get(id!) as Promise<UserListItem>,
    enabled: isEdit,
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { isActive: true },
  })

  useEffect(() => {
    if (user) reset({ firstName: user.firstName, lastName: user.lastName, email: user.email, userName: user.userName, isActive: user.isActive !== false })
  }, [user, reset])

  const mutation = useMutation({
    mutationFn: (data: FormData) => isEdit ? usersApi.update(id!, data) : usersApi.create(data),
    onSuccess: () => {
      toast.success(isEdit ? 'User updated' : 'User created')
      qc.invalidateQueries({ queryKey: ['users'] })
      router.push('/app/admin/users')
    },
    onError: (err: unknown) => {
      const msg = (err as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Save failed'
      toast.error(msg)
    },
  })

  if (isEdit && isLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[{ label: 'Users', href: '/app/admin/users' }, { label: isEdit ? 'Edit User' : 'New User' }]} />
      <PageHeader
        title={isEdit ? 'Edit User' : 'New User'}
        subtitle={isEdit ? `Editing ${user?.fullName || user?.userName}` : 'Create a new user account'}
      />

      <form onSubmit={handleSubmit(d => mutation.mutate(d))} className="max-w-2xl">
        <div className="card p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input {...register('firstName')} label="First name" error={errors.firstName?.message} />
            <Input {...register('lastName')}  label="Last name"  error={errors.lastName?.message} />
          </div>
          <Input {...register('email')}    label="Email"    type="email" error={errors.email?.message} />
          <Input {...register('userName')} label="Username" placeholder="Optional — inferred from email" />
          {!isEdit && (
            <Input {...register('password')} label="Password" type="password" placeholder="Leave blank to auto-generate" />
          )}
          <div className="flex items-center gap-2">
            <input type="checkbox" id="isActive" {...register('isActive')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
            <label htmlFor="isActive" className="text-sm font-medium text-gray-700 dark:text-gray-300">Active</label>
          </div>

          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={mutation.isPending}>{isEdit ? 'Save changes' : 'Create user'}</Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
          </div>
        </div>
      </form>

      {isEdit && (
        <div className="max-w-2xl">
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Access Control</h3>
            <div className="flex gap-3">
              <Link href={`/app/admin/users/${id}/roles`}>
                <Button variant="secondary" icon={<Shield size={15} />}>Manage Roles</Button>
              </Link>
              <Link href={`/app/admin/users/${id}/permissions`}>
                <Button variant="secondary" icon={<ShieldCheck size={15} />}>Manage Permissions</Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
