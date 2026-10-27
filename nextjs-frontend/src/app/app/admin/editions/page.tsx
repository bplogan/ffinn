'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { editionsApi } from '@/lib/api'
import type { Edition } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import {
  Plus, Pencil, Trash2, Layers, Check, X, ChevronDown, ChevronRight,
  DollarSign, GripVertical,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useForm, useFieldArray, Controller } from 'react-hook-form'

// ─── Edition form ─────────────────────────────────────────────────────────────

type FeatureFormRow = {
  id?: string
  feature_name: string
  display_name: string
  feature_value: string
  is_included: boolean
  sort_order: number
}

type EditionFormData = {
  display_name: string
  is_free: boolean
  price_monthly: number
  price_annually: number
  currency: string
  sort_order: number
  is_public: boolean
  trial_day_count: string
  is_trial_active: boolean
  features: FeatureFormRow[]
}

function EditionFormModal({
  open,
  edition,
  onClose,
}: {
  open: boolean
  edition: Edition | null
  onClose: () => void
}) {
  const qc = useQueryClient()

  const { register, handleSubmit, control, watch, setValue, formState: { errors } } = useForm<EditionFormData>({
    defaultValues: edition
      ? {
          display_name: edition.display_name,
          is_free: edition.is_free,
          price_monthly: edition.price_monthly,
          price_annually: edition.price_annually,
          currency: edition.currency,
          sort_order: edition.sort_order,
          is_public: edition.is_public,
          trial_day_count: edition.trial_day_count != null ? String(edition.trial_day_count) : '',
          is_trial_active: edition.is_trial_active,
          features: edition.features.map(f => ({
            id: f.id,
            feature_name: f.feature_name,
            display_name: f.display_name,
            feature_value: f.feature_value ?? '',
            is_included: f.is_included,
            sort_order: f.sort_order,
          })),
        }
      : {
          display_name: '',
          is_free: true,
          price_monthly: 0,
          price_annually: 0,
          currency: 'USD',
          sort_order: 0,
          is_public: true,
          trial_day_count: '',
          is_trial_active: false,
          features: [],
        },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'features' })
  const isFree = watch('is_free')
  const isTrialActive = watch('is_trial_active')

  const saveMut = useMutation({
    mutationFn: async (data: EditionFormData) => {
      const payload = {
        display_name: data.display_name,
        is_free: data.is_free,
        price_monthly: data.is_free ? 0 : Number(data.price_monthly),
        price_annually: data.is_free ? 0 : Number(data.price_annually),
        currency: data.currency,
        sort_order: Number(data.sort_order),
        is_public: data.is_public,
        trial_day_count: data.trial_day_count ? Number(data.trial_day_count) : null,
        is_trial_active: data.is_trial_active,
      }
      let editionId: string
      if (edition) {
        await editionsApi.update(edition.id, payload)
        editionId = edition.id
      } else {
        const created = await editionsApi.create(payload) as Edition
        editionId = created.id
      }
      // Replace features atomically
      await editionsApi.replaceFeatures(
        editionId,
        data.features.map((f, i) => ({
          feature_name: f.feature_name || f.display_name,
          display_name: f.display_name,
          feature_value: f.feature_value || null,
          is_included: f.is_included,
          sort_order: i,
        })),
      )
    },
    onSuccess: () => {
      toast.success(edition ? 'Edition updated' : 'Edition created')
      qc.invalidateQueries({ queryKey: ['admin-editions'] })
      onClose()
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Save failed'
      toast.error(msg)
    },
  })

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={edition ? `Edit Edition — ${edition.display_name}` : 'New Edition'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit(d => saveMut.mutate(d))} loading={saveMut.isPending}>
            Save Edition
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {/* Basic info */}
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Input
              {...register('display_name', { required: 'Required' })}
              label="Edition Name"
              placeholder="e.g. Free, Pro, Enterprise"
              error={errors.display_name?.message}
            />
          </div>
          <Input
            {...register('sort_order', { valueAsNumber: true })}
            label="Sort Order"
            type="number"
            hint="Lower = appears first"
          />
          <div className="space-y-1.5">
            <label className="label">Currency</label>
            <input {...register('currency')} className="input-field" placeholder="USD" />
          </div>
        </div>

        {/* Pricing */}
        <div className="space-y-3 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
          <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Pricing</p>
          <Controller
            control={control}
            name="is_free"
            render={({ field }) => (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  role="switch"
                  aria-checked={field.value}
                  onClick={() => field.onChange(!field.value)}
                  className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${
                    field.value ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-600'
                  }`}
                >
                  <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ${field.value ? 'translate-x-4' : 'translate-x-0'}`} />
                </button>
                <span className="text-sm text-gray-700 dark:text-gray-300">Free edition (no charge)</span>
              </div>
            )}
          />
          {!isFree && (
            <div className="grid grid-cols-2 gap-3 pt-1">
              <Input
                {...register('price_monthly', { valueAsNumber: true })}
                label="Monthly Price"
                type="number"
                step="0.01"
                placeholder="29.00"
              />
              <Input
                {...register('price_annually', { valueAsNumber: true })}
                label="Annual Price"
                type="number"
                step="0.01"
                placeholder="290.00"
              />
            </div>
          )}
        </div>

        {/* Trial */}
        <div className="flex items-center gap-4 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
          <div className="flex items-center gap-2 flex-1">
            <input
              id="isTrial"
              type="checkbox"
              {...register('is_trial_active')}
              className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
            />
            <label htmlFor="isTrial" className="text-sm font-medium text-gray-700 dark:text-gray-300">Enable trial period</label>
          </div>
          {isTrialActive && (
            <div className="w-36">
              <Input
                {...register('trial_day_count')}
                label="Trial days"
                type="number"
                placeholder="14"
              />
            </div>
          )}
        </div>

        {/* Visibility */}
        <div className="flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
          <input
            id="isPublic"
            type="checkbox"
            {...register('is_public')}
            className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
          />
          <label htmlFor="isPublic" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Visible on public paywall / plan selection page
          </label>
        </div>

        {/* Features */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Features / Capabilities</p>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              icon={<Plus size={14} />}
              onClick={() =>
                append({
                  feature_name: '',
                  display_name: '',
                  feature_value: '',
                  is_included: true,
                  sort_order: fields.length,
                })
              }
            >
              Add Feature
            </Button>
          </div>
          {fields.length === 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500 py-2 text-center">
              No features yet — add some to display on the pricing page.
            </p>
          )}
          <div className="space-y-2">
            {fields.map((field, idx) => (
              <div key={field.id} className="flex items-start gap-2 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <GripVertical size={16} className="text-gray-400 mt-2.5 flex-shrink-0" />
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <input
                    {...register(`features.${idx}.display_name`, { required: true })}
                    className="input-field text-sm"
                    placeholder="Label (e.g. Unlimited users)"
                  />
                  <input
                    {...register(`features.${idx}.feature_value`)}
                    className="input-field text-sm"
                    placeholder="Value (e.g. Unlimited, 10 GB)"
                  />
                </div>
                <Controller
                  control={control}
                  name={`features.${idx}.is_included`}
                  render={({ field: f }) => (
                    <button
                      type="button"
                      onClick={() => setValue(`features.${idx}.is_included`, !f.value)}
                      className={`mt-1.5 flex-shrink-0 w-6 h-6 rounded flex items-center justify-center transition-colors ${
                        f.value
                          ? 'bg-success-100 dark:bg-success-900/30 text-success-600'
                          : 'bg-gray-200 dark:bg-gray-700 text-gray-400'
                      }`}
                      title={f.value ? 'Included' : 'Not included'}
                    >
                      {f.value ? <Check size={12} /> : <X size={12} />}
                    </button>
                  )}
                />
                <button
                  type="button"
                  onClick={() => remove(idx)}
                  className="mt-1.5 flex-shrink-0 text-gray-400 hover:text-error-500 transition-colors"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}

// ─── Tenant count badge ───────────────────────────────────────────────────────

function TenantsCountBadge({ editionId }: { editionId: string }) {
  const { data } = useQuery<{ tenant_count: number }>({
    queryKey: ['edition-tenant-count', editionId],
    queryFn: () => editionsApi.tenantCount(editionId) as Promise<{ tenant_count: number }>,
  })
  return <Badge variant="gray">{data?.tenant_count ?? '…'} tenants</Badge>
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminEditionsPage() {
  const qc = useQueryClient()
  const [editEdition, setEditEdition] = useState<Edition | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const { data, isLoading } = useQuery<{ items: Edition[]; total_count: number }>({
    queryKey: ['admin-editions'],
    queryFn: () => editionsApi.list() as Promise<{ items: Edition[]; total_count: number }>,
  })

  const editions = data?.items ?? []

  const deleteMut = useMutation({
    mutationFn: (id: string) => editionsApi.delete(id),
    onSuccess: () => {
      toast.success('Edition deleted')
      qc.invalidateQueries({ queryKey: ['admin-editions'] })
      setDeleteId(null)
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed'
      toast.error(msg)
    },
  })

  const openCreate = () => { setEditEdition(null); setModalOpen(true) }
  const openEdit = (e: Edition) => { setEditEdition(e); setModalOpen(true) }

  if (isLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6">
      <PageHeader
        title="Edition Management"
        subtitle="Define subscription tiers with features and pricing. Tenants are assigned an edition at registration."
        actions={
          <Button icon={<Plus size={16} />} onClick={openCreate}>
            New Edition
          </Button>
        }
      />

      {editions.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<Layers size={40} />}
            title="No editions configured"
            description="Create editions to define your pricing tiers and features. Enable the paywall in Settings → Registration to require plan selection during signup."
            action={<Button icon={<Plus size={15} />} onClick={openCreate}>Create First Edition</Button>}
          />
        </div>
      ) : (
        <div className="space-y-3">
          {editions.map(ed => (
            <div key={ed.id} className="card overflow-hidden">
              {/* Edition header row */}
              <div className="p-5 flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setExpandedId(prev => (prev === ed.id ? null : ed.id))}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex-shrink-0"
                >
                  {expandedId === ed.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{ed.display_name}</h3>
                    {ed.is_free && <Badge variant="success">Free</Badge>}
                    {!ed.is_public && <Badge variant="gray">Hidden</Badge>}
                    {ed.is_trial_active && ed.trial_day_count != null && (
                      <Badge variant="info">{ed.trial_day_count}-day trial</Badge>
                    )}
                    <TenantsCountBadge editionId={ed.id} />
                  </div>
                </div>

                <div className="text-right hidden sm:block">
                  {ed.is_free ? (
                    <span className="text-lg font-bold text-success-600 dark:text-success-400">Free</span>
                  ) : (
                    <div className="space-y-0.5">
                      <div className="flex items-center justify-end gap-1">
                        <DollarSign size={14} className="text-gray-400" />
                        <span className="text-lg font-bold text-gray-900 dark:text-white">
                          {Number(ed.price_monthly).toFixed(2)}
                        </span>
                        <span className="text-xs text-gray-400">/mo</span>
                      </div>
                      {ed.price_annually > 0 && (
                        <div className="text-xs text-gray-400">
                          {ed.currency} {Number(ed.price_annually).toFixed(2)}/yr
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEdit(ed)} />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    className="hover:text-error-500"
                    onClick={() => setDeleteId(ed.id)}
                  />
                </div>
              </div>

              {/* Expanded feature list */}
              {expandedId === ed.id && (
                <div className="border-t border-gray-100 dark:border-gray-700 px-5 pb-5 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">
                    Features ({ed.features.length})
                  </p>
                  {ed.features.length === 0 ? (
                    <p className="text-sm text-gray-400 dark:text-gray-500 italic">No features defined.</p>
                  ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {ed.features.map(f => (
                        <div key={f.id} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                          {f.is_included ? (
                            <Check size={14} className="text-success-500 flex-shrink-0" />
                          ) : (
                            <X size={14} className="text-gray-400 flex-shrink-0" />
                          )}
                          <span className={f.is_included ? '' : 'text-gray-400 line-through'}>
                            {f.display_name}
                            {f.feature_value && (
                              <span className="ml-1 font-medium text-brand-600 dark:text-brand-400">
                                {f.feature_value}
                              </span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<Pencil size={13} />}
                    className="mt-3"
                    onClick={() => openEdit(ed)}
                  >
                    Edit Features
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <EditionFormModal
          open={modalOpen}
          edition={editEdition}
          onClose={() => setModalOpen(false)}
        />
      )}

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending}
        title="Delete Edition"
        message="Delete this edition? Tenants assigned to it will not be reassigned automatically."
        confirmLabel="Delete"
      />
    </div>
  )
}

