'use client'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tenantsApi } from '@/lib/api'
import { useRouter, useParams } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Breadcrumb from '@/components/ui/Breadcrumb'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import type { AxiosError } from 'axios'
import type { Tenant } from '@/types'

function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as AxiosError<{ message?: string; detail?: string }>)?.response?.data
  return data?.message || data?.detail || fallback
}

export default function TenantFormPage() {
  const router = useRouter()
  const params = useParams()
  const qc = useQueryClient()
  const id = params?.id as string | undefined
  const isEdit = !!id && id !== 'new'

  const { data, isLoading } = useQuery<Tenant>({ queryKey: ['tenant', id], queryFn: () => tenantsApi.get(id!) as Promise<Tenant>, enabled: isEdit })
  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ name: string; tenancyName: string; adminEmail?: string; adminPassword?: string; isActive?: boolean }>({ defaultValues: { isActive: true } })

  useEffect(() => { if (data) reset({ name: data.name, tenancyName: data.tenancyName, isActive: data.isActive !== false }) }, [data, reset])

  const mut = useMutation({
    mutationFn: (d: unknown) => isEdit ? tenantsApi.update(id!, d) : tenantsApi.create(d),
    onSuccess: () => { toast.success(isEdit ? 'Tenant updated' : 'Tenant created'); qc.invalidateQueries({ queryKey: ['tenants'] }); router.push('/app/admin/tenants') },
    onError: (e: unknown) => toast.error(apiErrorMessage(e, 'Save failed')),
  })

  if (isEdit && isLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[{ label: 'Tenants', href: '/app/admin/tenants' }, { label: isEdit ? 'Edit Tenant' : 'New Tenant' }]} />
      <PageHeader title={isEdit ? 'Edit Tenant' : 'New Tenant'} />
      <form onSubmit={handleSubmit(d => mut.mutate(d))} className="max-w-xl">
        <div className="card p-6 space-y-4">
          <Input {...register('name', { required: 'Required' })} label="Tenant name" placeholder="Acme Corp" error={errors.name?.message} />
          <Input {...register('tenancyName', { required: 'Required', pattern: { value: /^[a-z0-9-]+$/, message: 'Lowercase letters, numbers, hyphens only' } })}
            label="Tenancy name (subdomain)" placeholder="acme" error={errors.tenancyName?.message} disabled={isEdit}
            hint="Used as the URL segment. Cannot be changed after creation." />
          {!isEdit && (
            <>
              <Input {...register('adminEmail', { required: 'Admin email is required' })} label="Admin email" type="email" placeholder="admin@acme.com" hint="Initial admin account for this tenant (the person signing up)" error={errors.adminEmail?.message} />
              <Input {...register('adminPassword', { required: 'Admin password is required', minLength: { value: 8, message: 'At least 8 characters' } })} label="Admin password" type="password" placeholder="Required" autoComplete="new-password" error={errors.adminPassword?.message} />
            </>
          )}
          <div className="flex items-center gap-2">
            <input type="checkbox" id="isActive" {...register('isActive')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
            <label htmlFor="isActive" className="text-sm font-medium text-gray-700 dark:text-gray-300">Active</label>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={mut.isPending}>{isEdit ? 'Save changes' : 'Create tenant'}</Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
          </div>
        </div>
      </form>
    </div>
  )
}
