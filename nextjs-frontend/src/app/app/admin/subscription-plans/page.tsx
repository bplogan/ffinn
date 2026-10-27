'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { subscriptionPlansApi } from '@/lib/api'
import type { SubscriptionPlan } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import { TextArea, Select } from '@/components/ui/Input'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { Plus, Pencil, Trash2, CreditCard, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import { useForm } from 'react-hook-form'
import { AxiosError } from 'axios'

interface PlanFormData {
  name: string
  display_name: string
  description?: string
  price_monthly?: number
  price_annually?: number
  currency?: string
  sort_order?: number
  max_users?: number
  max_storage_gb?: number
  is_active?: boolean
  is_public?: boolean
  stripe_price_id_monthly?: string
  stripe_price_id_annually?: string
  paypal_plan_id_monthly?: string
  paypal_plan_id_annually?: string
}

export default function SubscriptionPlansPage() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editPlan, setEditPlan] = useState<SubscriptionPlan | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const { data: plans, isLoading } = useQuery<SubscriptionPlan[]>({ queryKey: ['subscription-plans'], queryFn: () => subscriptionPlansApi.listAll() as Promise<SubscriptionPlan[]> })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<PlanFormData>()

  const openCreate = () => { reset({ is_active: true, is_public: true, currency: 'USD', sort_order: 0 }); setEditPlan(null); setModalOpen(true) }
  const openEdit = (p: SubscriptionPlan) => {
    reset({
      name: p.name,
      display_name: p.display_name || p.displayName || '',
      description: p.description,
      price_monthly: p.price_monthly ?? p.price ?? 0,
      price_annually: p.price_annually ?? 0,
      currency: p.currency || 'USD',
      sort_order: p.sort_order ?? 0,
      max_users: p.max_users,
      max_storage_gb: p.max_storage_gb,
      is_active: p.is_active ?? p.isActive ?? true,
      is_public: p.is_public ?? true,
      stripe_price_id_monthly: p.stripe_price_id_monthly,
      stripe_price_id_annually: p.stripe_price_id_annually,
      paypal_plan_id_monthly: p.paypal_plan_id_monthly,
      paypal_plan_id_annually: p.paypal_plan_id_annually,
    })
    setEditPlan(p)
    setModalOpen(true)
  }

  const saveMut = useMutation({
    mutationFn: (d: PlanFormData) => editPlan ? subscriptionPlansApi.update(editPlan.id, d) : subscriptionPlansApi.create(d),
    onSuccess: () => { toast.success('Saved'); qc.invalidateQueries({ queryKey: ['subscription-plans'] }); setModalOpen(false) },
    onError: (err: AxiosError<{ detail?: string }>) => {
      const msg = err.response?.data?.detail || 'Save failed'
      toast.error(msg)
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => subscriptionPlansApi.delete(id),
    onSuccess: () => { toast.success('Deleted'); qc.invalidateQueries({ queryKey: ['subscription-plans'] }); setDeleteId(null) },
  })

  return (
    <div className="space-y-6">
      <PageHeader title="Subscription Plans" subtitle="Configure pricing plans for your application"
        actions={<Button icon={<Plus size={16} />} onClick={openCreate}>Add Plan</Button>} />

      {isLoading ? <LoadingSpinner fullPage /> : !plans?.length ? (
        <div className="card"><EmptyState icon={<CreditCard size={40} />} title="No plans" action={<Button icon={<Plus size={15} />} onClick={openCreate}>Add Plan</Button>} /></div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map(p => (
            <div key={p.id} className="card p-6 relative">
              {p.isDefault && <span className="absolute top-3 right-3"><Badge variant="info">Default</Badge></span>}
              <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">{p.display_name || p.displayName || p.name}</h3>
              {p.description && <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">{p.description}</p>}
              <div className="flex items-baseline gap-1 mb-4">
                <span className="text-3xl font-bold text-gray-900 dark:text-white">${p.price_monthly ?? p.price ?? 0}</span>
                <span className="text-sm text-gray-400">/month</span>
              </div>
              {p.price_annually != null && p.price_annually > 0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                  or ${p.price_annually}/year
                </div>
              )}
              {p.features && p.features.length > 0 && (
                <ul className="space-y-1.5 mb-4">
                  {p.features.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                      <Check size={13} className="text-success-500 flex-shrink-0" /> {typeof f === 'string' ? f : f.name}
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <Badge variant={(p.is_active ?? p.isActive) !== false ? 'success' : 'error'}>{(p.is_active ?? p.isActive) !== false ? 'Active' : 'Inactive'}</Badge>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEdit(p)} />
                  <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} className="hover:text-error-500" onClick={() => setDeleteId(p.id)} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editPlan ? 'Edit Plan' : 'New Plan'}
        footer={<><Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button><Button onClick={handleSubmit(d => saveMut.mutate(d))} loading={saveMut.isPending}>Save</Button></>}>
        <div className="space-y-4">
          <Input {...register('name', { required: 'Required' })} label="Plan name (internal)" placeholder="pro" error={errors.name?.message} required />
          <Input {...register('display_name', { required: 'Required' })} label="Display name" placeholder="Pro Plan" error={errors.display_name?.message} required />
          <TextArea {...register('description')} label="Description" rows={2} />
          <div className="grid grid-cols-2 gap-3">
            <Input {...register('price_monthly', { valueAsNumber: true })} label="Monthly price" type="number" step="0.01" />
            <Input {...register('price_annually', { valueAsNumber: true })} label="Annual price" type="number" step="0.01" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select {...register('currency')} label="Currency">
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </Select>
            <Input {...register('sort_order', { valueAsNumber: true })} label="Sort order" type="number" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input {...register('max_users', { valueAsNumber: true })} label="Max users" type="number" placeholder="Unlimited" />
            <Input {...register('max_storage_gb', { valueAsNumber: true })} label="Max storage (GB)" type="number" placeholder="Unlimited" />
          </div>
          <Input {...register('stripe_price_id_monthly')} label="Stripe monthly price ID" placeholder="price_..." />
          <Input {...register('stripe_price_id_annually')} label="Stripe annual price ID" placeholder="price_..." />
          <Input {...register('paypal_plan_id_monthly')} label="PayPal monthly plan ID" placeholder="P-..." />
          <Input {...register('paypal_plan_id_annually')} label="PayPal annual plan ID" placeholder="P-..." />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <input type="checkbox" id="planActive" {...register('is_active')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
              <label htmlFor="planActive" className="text-sm font-medium text-gray-700 dark:text-gray-300">Active</label>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="planPublic" {...register('is_public')} className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
              <label htmlFor="planPublic" className="text-sm font-medium text-gray-700 dark:text-gray-300">Public</label>
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog open={!!deleteId} onClose={() => setDeleteId(null)} onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending} title="Delete Plan" message="Delete this subscription plan?" confirmLabel="Delete" />
    </div>
  )
}
