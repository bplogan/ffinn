'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { subscriptionApi, subscriptionPlansApi } from '@/lib/api'
import type { Subscription, SubscriptionPlan } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Check, CreditCard, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'next/navigation'
import { formatDistanceToNow } from 'date-fns'

export default function SubscriptionPage() {
  const qc = useQueryClient()
  const searchParams = useSearchParams()
  const [cancelOpen, setCancelOpen] = useState(false)
  const [paymentProvider, setPaymentProvider] = useState<'stripe' | 'paypal'>('stripe')

  const paypalConfirmedRef = useRef<string | null>(null)

  useEffect(() => {
    const subId = searchParams.get('subscription_id')
    if (!subId || paypalConfirmedRef.current === subId) return
    paypalConfirmedRef.current = subId
    subscriptionApi.confirmPaypal(subId)
      .then(() => { toast.success('PayPal subscription activated'); qc.invalidateQueries({ queryKey: ['my-subscription'] }) })
      .catch(() => toast.error('Could not confirm PayPal subscription'))
  }, [searchParams, qc])

  const portalMut = useMutation({
    mutationFn: () => subscriptionApi.createPortal(window.location.href) as Promise<{ portal_url?: string }>,
    onSuccess: (data) => { if (data?.portal_url) window.location.href = data.portal_url },
    onError: () => toast.error('Could not open billing portal'),
  })

  const { data: subscription, isLoading: subLoading } = useQuery<Subscription>({
    queryKey: ['my-subscription'],
    queryFn: () => subscriptionApi.getCurrent() as Promise<Subscription>,
  })
  const { data: plans = [], isLoading: plansLoading } = useQuery<SubscriptionPlan[]>({
    queryKey: ['subscription-plans'],
    queryFn: () => subscriptionPlansApi.list() as Promise<SubscriptionPlan[]>,
  })

  const upgradeMut = useMutation({
    mutationFn: async (planId: string) => {
      const result = await subscriptionApi.subscribe({
        plan_id: planId,
        billing_cycle: 'monthly',
        payment_provider: paymentProvider,
        success_url: typeof window !== 'undefined' ? window.location.href : '/',
        cancel_url: typeof window !== 'undefined' ? window.location.href : '/',
      }) as { checkout_url?: string }
      if (result?.checkout_url) window.location.href = result.checkout_url
      return result
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['my-subscription'] }) },
    onError: () => toast.error('Upgrade failed'),
  })

  const cancelMut = useMutation({
    mutationFn: () => subscriptionApi.cancel(),
    onSuccess: () => { toast.success('Subscription cancelled'); qc.invalidateQueries({ queryKey: ['my-subscription'] }); setCancelOpen(false) },
    onError: () => toast.error('Cancellation failed'),
  })

  if (subLoading || plansLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader title="Subscription" subtitle="Manage your plan and billing" />

      <div className="card p-4 flex flex-wrap items-center gap-4">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Payment method for checkout:</span>
        <div className="flex gap-2">
          <Button variant={paymentProvider === 'stripe' ? 'primary' : 'secondary'} size="sm" onClick={() => setPaymentProvider('stripe')}>Stripe</Button>
          <Button variant={paymentProvider === 'paypal' ? 'primary' : 'secondary'} size="sm" onClick={() => setPaymentProvider('paypal')}>PayPal</Button>
        </div>
      </div>

      {subscription && (
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Current plan</h2>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <p className="font-semibold text-gray-900 dark:text-white text-lg">{subscription.planName}</p>
                <Badge variant={subscription.status === 'active' ? 'success' : subscription.status === 'past_due' ? 'error' : 'gray'}>
                  {subscription.status}
                </Badge>
              </div>
              {subscription.currentPeriodEnd && (
                <p className="text-sm text-gray-500">
                  Renews {formatDistanceToNow(new Date(subscription.currentPeriodEnd), { addSuffix: true })}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" icon={<CreditCard size={15} />}
                loading={portalMut.isPending}
                onClick={() => portalMut.mutate()}>
                Billing
              </Button>
              <Button variant="danger" onClick={() => setCancelOpen(true)}>Cancel</Button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Available plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map(plan => {
            const isCurrent = subscription?.planId === plan.id
            const isPopular = plan.isPopular || plan.isRecommended
            const displayPrice = plan.price ?? plan.pricing?.monthly ?? 0
            const cycle = plan.billingCycle ?? plan.billingPeriod ?? 'mo'
            const planFeatures = plan.features ?? []
            return (
              <div key={plan.id} className={`card p-6 relative ${isPopular ? 'border-2 border-brand-500' : ''}`}>
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-500 text-white text-xs px-3 py-0.5 rounded-full font-medium">
                    Most popular
                  </div>
                )}
                <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{plan.name}</h3>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mb-1">
                  {displayPrice === 0 ? 'Free' : `$${displayPrice}`}
                  {displayPrice > 0 && <span className="text-sm font-normal text-gray-500">/{cycle}</span>}
                </p>
                {plan.description && <p className="text-sm text-gray-500 mb-4">{plan.description}</p>}
                {planFeatures.length > 0 && (
                  <ul className="space-y-2 mb-6">
                    {planFeatures.map((f, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Check size={14} className="text-success-500 flex-shrink-0" />{typeof f === 'string' ? f : f.name}
                      </li>
                    ))}
                  </ul>
                )}
                <Button className="w-full" variant={isCurrent ? 'secondary' : isPopular ? 'primary' : 'outline'}
                  disabled={isCurrent} icon={isCurrent ? undefined : <Zap size={15} />}
                  loading={upgradeMut.isPending && upgradeMut.variables === plan.id}
                  onClick={() => !isCurrent && upgradeMut.mutate(plan.id)}>
                  {isCurrent ? 'Current plan' : 'Switch to this plan'}
                </Button>
              </div>
            )
          })}
        </div>
      </div>

      <ConfirmDialog open={cancelOpen} onClose={() => setCancelOpen(false)} onConfirm={() => cancelMut.mutate()}
        loading={cancelMut.isPending} title="Cancel subscription"
        message="Your subscription will remain active until the end of the billing period, then be cancelled." confirmLabel="Yes, cancel" />
    </div>
  )
}
