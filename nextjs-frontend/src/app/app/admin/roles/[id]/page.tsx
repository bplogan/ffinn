'use client'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rolesApi } from '@/lib/api'
import { useRouter, useParams } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { TextArea } from '@/components/ui/Input'
import Breadcrumb from '@/components/ui/Breadcrumb'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import type { Role } from '@/types'

export default function RoleFormPage() {
  const router = useRouter()
  const params = useParams()
  const qc = useQueryClient()
  const id = params?.id as string | undefined
  const isEdit = !!id && id !== 'new'

  const { data: role, isLoading } = useQuery<Role>({ queryKey: ['role', id], queryFn: () => rolesApi.get(id!) as Promise<Role>, enabled: isEdit })
  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ name: string; displayName?: string; description?: string; isDefault?: boolean }>()

  useEffect(() => { if (role) reset({ name: role.name, displayName: role.displayName, description: role.description, isDefault: role.isDefault }) }, [role, reset])

  const mut = useMutation({
    mutationFn: (d: unknown) => isEdit ? rolesApi.update(id!, d) : rolesApi.create(d),
    onSuccess: () => { toast.success(isEdit ? 'Role updated' : 'Role created'); qc.invalidateQueries({ queryKey: ['roles'] }); router.push('/app/admin/roles') },
    onError: () => toast.error('Save failed'),
  })

  if (isEdit && isLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[{ label: 'Roles', href: '/app/admin/roles' }, { label: isEdit ? 'Edit Role' : 'New Role' }]} />
      <PageHeader title={isEdit ? 'Edit Role' : 'New Role'} />
      <form onSubmit={handleSubmit(d => mut.mutate(d))} className="max-w-xl">
        <div className="card p-6 space-y-4">
          <Input {...register('name', { required: 'Required' })} label="Role name" placeholder="e.g. Manager" error={errors.name?.message} disabled={role?.isStatic} />
          <Input {...register('displayName')} label="Display name" placeholder="e.g. Manager" />
          <TextArea {...register('description')} label="Description" rows={3} />
          <div className="flex items-center gap-2">
            <input type="checkbox" id="isDefault" {...register('isDefault')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
            <label htmlFor="isDefault" className="text-sm font-medium text-gray-700 dark:text-gray-300">Default role for new users</label>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={mut.isPending}>{isEdit ? 'Save changes' : 'Create role'}</Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
          </div>
        </div>
      </form>
    </div>
  )
}
