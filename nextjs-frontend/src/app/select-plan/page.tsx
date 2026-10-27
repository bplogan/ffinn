'use client'
import { Suspense, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { paywallApi } from '@/lib/api'
import type { Edition } from '@/types'
import { Check, X, Zap, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

// ── helpers ────────────────────────────────────────────────────────────────

function formatPrice(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: currency || 'USD', minimumFractionDigits: 0,
  }).format(amount)
}

function annualSavingPct(edition: Edition): number {
  if (!edition.price_monthly || !edition.price_annually) return 0
  const annual = edition.price_monthly * 12
  return Math.round(((annual - edition.price_annually) / annual) * 100)
}

// ── Plan card ──────────────────────────────────────────────────────────────

interface PlanCardProps {
  edition: Edition
  billingAnnual: boolean
  onSelect: (edition: Edition) => void
}

function PlanCard({ edition, billingAnnual, onSelect }: PlanCardProps) {
  const price = billingAnnual
    ? (edition.price_annually ? edition.price_annually / 12 : 0)
    : edition.price_monthly || 0
  const saving = annualSavingPct(edition)
  const isFeatured = !edition.is_free && edition.sort_order === 1  // first paid plan

  return (
    <div
      className={`relative flex flex-col rounded-[22px] p-6 sm:p-7 ${
        isFeatured
          ? 'ink-scope bg-surface text-ink ring-1 ring-white/10 shadow-[0_40px_80px_-40px_rgb(0_0_0/0.55)]'
          : 'site-card'
      }`}
    >
      {/* Popular badge */}
      {isFeatured && (
        <span className="absolute right-6 top-6 inline-flex items-center gap-1 rounded-full bg-accent/15 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.08em] text-accent">
          <Zap size={11} /> Most popular
        </span>
      )}

      {/* Header */}
      <div className="mb-5">
        <h2 className="font-display text-lg font-semibold tracking-[-0.015em]">{edition.display_name}</h2>
        {edition.is_trial_active && edition.trial_day_count && (
          <span className="mt-2 inline-block rounded-full bg-caution/10 px-2.5 py-0.5 text-xs font-medium text-caution ring-1 ring-caution/25">
            {edition.trial_day_count}-day free trial
          </span>
        )}
      </div>

      {/* Price */}
      <div className="mb-6">
        {edition.is_free ? (
          <div className="font-display text-[2.6rem] font-semibold leading-none tracking-[-0.04em]">Free</div>
        ) : (
          <>
            <div className="flex items-end gap-1">
              <span className="font-display text-[2.6rem] font-semibold leading-none tracking-[-0.04em]">
                {formatPrice(price, edition.currency)}
              </span>
              <span className="mb-1 text-sm text-ink-mute">/mo</span>
            </div>
            {billingAnnual && saving > 0 && (
              <p className="mt-2 text-xs text-signal">
                Billed {formatPrice(edition.price_annually, edition.currency)}/yr, saving {saving}%
              </p>
            )}
            {!billingAnnual && saving > 0 && (
              <p className="mt-2 text-xs text-ink-mute">
                Save {saving}% with annual billing
              </p>
            )}
          </>
        )}
      </div>

      {/* Features */}
      <ul className="mb-8 flex-1 space-y-2.5 border-t pt-6">
        {edition.features
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order)
          .map(f => (
            <li key={f.id} className="flex items-start gap-2.5 text-sm">
              {f.is_included
                ? <Check size={15} className="mt-0.5 shrink-0 text-signal" />
                : <X     size={15} className="mt-0.5 shrink-0 text-ink-mute/60" />
              }
              <span className={f.is_included ? 'text-ink-soft' : 'text-ink-mute line-through decoration-ink/20'}>
                {f.display_name}
                {f.feature_value && f.is_included && (
                  <span className="text-ink-mute"> · {f.feature_value}</span>
                )}
              </span>
            </li>
          ))}
      </ul>

      {/* CTA */}
      <button
        onClick={() => onSelect(edition)}
        className={`${isFeatured ? 'site-btn-primary' : 'site-btn-secondary'} w-full`}
      >
        {edition.is_free ? 'Get started free' : `Start with ${edition.display_name}`}
      </button>
    </div>
  )
}

// ── Inner page (needs Suspense for useSearchParams) ────────────────────────

function SelectPlanInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Only allow same-origin (relative) paths in `redirect` to prevent
  // open-redirect to attacker domains. Strings starting with "//" are
  // protocol-relative URLs — those are external and must be rejected too.
  const rawRedirect = searchParams.get('redirect')
  const redirect =
    rawRedirect && rawRedirect.startsWith('/') && !rawRedirect.startsWith('//')
      ? rawRedirect
      : '/auth/register'

  const [billingAnnual, setBillingAnnual] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['paywall-editions'],
    queryFn: () => paywallApi.getEditions() as Promise<{ items: Edition[] }>,
    staleTime: 60_000,
  })
  const editions = data?.items ?? []

  function handleSelect(edition: Edition) {
    const params = new URLSearchParams()
    params.set('editionId', edition.id)
    params.set('editionName', edition.display_name)
    router.push(`${redirect}?${params.toString()}`)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <LoadingSpinner />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="text-center py-24">
        <p className="mb-4 text-ink-soft">We couldn&apos;t load the plans. Refresh to try again.</p>
        <Link href="/auth/register" className="text-sm font-medium text-ink underline decoration-ink/25 underline-offset-4 hover:decoration-ink">
          Continue without selecting a plan
        </Link>
      </div>
    )
  }

  if (editions.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="mb-4 text-ink-soft">No plans are available right now.</p>
        <Link href="/auth/register" className="text-sm font-medium text-ink underline decoration-ink/25 underline-offset-4 hover:decoration-ink">
          Register without a plan
        </Link>
      </div>
    )
  }

  // Determine if any plan has an annual price to show the toggle
  const hasAnnual = editions.some(e => !e.is_free && e.price_annually > 0 && e.price_monthly > 0)

  return (
    <div>
      {/* Back link */}
      <div className="mb-10">
        <Link href="/auth/register"
          className="inline-flex items-center gap-1.5 text-sm text-ink-mute transition-colors hover:text-ink">
          <ArrowLeft size={14} /> Back to registration
        </Link>
      </div>

      {/* Heading */}
      <div className="mx-auto mb-10 max-w-2xl text-center">
        <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />Plans</p>
        <h1 className="site-h2 mt-5">Pick the plan that <span className="site-serif">fits</span></h1>
        <p className="site-lede mx-auto mt-5 max-w-lg">
          Choose an edition to start with. You can change plans at any time.
        </p>
      </div>

      {/* Billing toggle */}
      {hasAnnual && (
        <div className="flex justify-center mb-10">
          <div role="group" aria-label="Billing period" className="flex items-center rounded-full bg-surface p-1 ring-1 ring-ink/10">
            <button
              onClick={() => setBillingAnnual(false)}
              aria-pressed={!billingAnnual}
              className={`h-9 rounded-full px-5 text-sm font-medium transition-colors ${!billingAnnual ? 'bg-ink text-canvas' : 'text-ink-soft hover:text-ink'}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingAnnual(true)}
              aria-pressed={billingAnnual}
              className={`flex h-9 items-center gap-2 rounded-full px-5 text-sm font-medium transition-colors ${billingAnnual ? 'bg-ink text-canvas' : 'text-ink-soft hover:text-ink'}`}
            >
              Annual
              {editions.some(e => annualSavingPct(e) > 0) && (
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${billingAnnual ? 'bg-canvas/15' : 'bg-signal/10 text-signal'}`}>
                  Save up to {Math.max(...editions.map(annualSavingPct))}%
                </span>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Plan grid */}
      <div className={`mx-auto grid gap-5 ${
        editions.length === 1 ? 'max-w-sm' :
        editions.length === 2 ? 'max-w-3xl sm:grid-cols-2' :
        editions.length === 3 ? 'md:grid-cols-3' :
        'sm:grid-cols-2 lg:grid-cols-4'
      }`}>
        {editions
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order)
          .map(edition => (
            <PlanCard
              key={edition.id}
              edition={edition}
              billingAnnual={billingAnnual}
              onSelect={handleSelect}
            />
          ))}
      </div>
    </div>
  )
}

// ── Public export ──────────────────────────────────────────────────────────

export default function SelectPlanPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[50vh]">
        <LoadingSpinner />
      </div>
    }>
      <SelectPlanInner />
    </Suspense>
  )
}
