'use client'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { Users, Building2, CreditCard, Bot, TrendingUp, TrendingDown, Activity, ArrowRight, ArrowUpRight, UserPlus } from 'lucide-react'
import type { DashboardStats, ActivityItem } from '@/types'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { format, formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'

interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  trend?: number
}

function StatCard({ label, value, icon, trend }: StatCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0 pt-2 font-mono text-[11px] uppercase leading-4 tracking-[0.1em] text-ink-mute">{label}</span>
        {/* Hidden where the cards get narrow (phones, and lg beside the sidebar) so labels never collide */}
        <span className="hidden sm:grid lg:hidden xl:grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-ink/[0.05] text-ink-soft">{icon}</span>
      </div>
      <p className="mt-4 font-display text-[2.1rem] font-semibold leading-none tracking-[-0.04em] text-ink tabular-nums">{value?.toLocaleString()}</p>
      {trend !== undefined && (
        <p className={clsx('mt-3 inline-flex items-center gap-1 text-xs font-medium', trend >= 0 ? 'text-signal' : 'text-error-600 dark:text-error-400')}>
          {trend >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {trend >= 0 ? '+' : ''}{trend}% <span className="font-normal text-ink-mute">from last month</span>
        </p>
      )}
    </div>
  )
}

function SectionCard({ title, icon, children, className }: { title: string; icon?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={clsx('card overflow-hidden', className)}>
      <h2 className="flex items-center gap-2 border-b px-5 py-4 font-display text-[15px] font-semibold tracking-[-0.01em] text-ink">
        {icon && <span className="text-ink-mute">{icon}</span>}
        {title}
      </h2>
      {children}
    </section>
  )
}

export default function DashboardPage() {
  const { user, isHost, hasRole } = useAuth()
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({ queryKey: ['dashboard-stats'], queryFn: () => dashboardApi.stats() as Promise<DashboardStats> })
  const { data: activity, isLoading: actLoading } = useQuery<ActivityItem[]>({ queryKey: ['dashboard-activity'], queryFn: () => dashboardApi.activity() as Promise<ActivityItem[]> })

  const quickActions = [
    ...(isHost
      ? [
          { href: '/app/admin/users/new', label: 'Add a user', hint: 'Create an account on the platform', icon: <Users size={16} /> },
          { href: '/app/admin/tenants/new', label: 'Create a tenant', hint: 'Set up a new customer workspace', icon: <Building2 size={16} /> },
          { href: '/app/ai-agent/builder', label: 'Build an AI agent', hint: 'Configure a new assistant', icon: <Bot size={16} /> },
        ]
      : [
          ...(hasRole('Admin')
            ? [
                { href: '/app/admin/users/new', label: 'Add a user', hint: 'Create an account in this workspace', icon: <Users size={16} /> },
                { href: '/app/admin/team-invitations', label: 'Invite a teammate', hint: 'Send an email invitation', icon: <UserPlus size={16} /> },
              ]
            : []),
        ]),
  ]

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11.5px] uppercase tracking-[0.14em] text-ink-mute">{format(new Date(), 'EEEE, d MMMM')}</p>
          <h1 className="mt-2 font-display text-[clamp(1.9rem,3.2vw,2.6rem)] font-semibold leading-[1.05] tracking-[-0.035em] text-ink">
            Welcome back, <span className="site-serif">{user?.firstName || user?.userName}</span>
          </h1>
          <p className="mt-2 text-[15px] text-ink-mute">
            {user?.tenantName ? <>You&apos;re working in <span className="text-ink-soft">{user.tenantName}</span>. </> : null}
            Here&apos;s what&apos;s happening today.
          </p>
        </div>
      </header>

      {/* Stats */}
      {statsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-5">
              <div className="site-shimmer h-3 rounded-full bg-ink/[0.06] w-1/2" />
              <div className="site-shimmer mt-5 h-8 rounded-lg bg-ink/[0.06] w-2/3" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Users"          value={stats?.totalUsers ?? 0}         icon={<Users size={16} />}      trend={stats?.userGrowth} />
          <StatCard label="Tenants"        value={stats?.totalTenants ?? 0}        icon={<Building2 size={16} />} />
          <StatCard label="Subscriptions"  value={stats?.activeSubscriptions ?? 0} icon={<CreditCard size={16} />} />
          <StatCard label="AI generations" value={stats?.aiGenerations ?? 0}       icon={<Bot size={16} />} />
        </div>
      )}

      {/* Build agent prompt — host only, matching the agent's nav visibility */}
      {isHost && (
        <section className="ink-scope relative overflow-hidden rounded-[22px] bg-canvas text-ink">
          <div aria-hidden className="site-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_60%_90%_at_85%_20%,black,transparent)]" />
          <div aria-hidden className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-accent/25 blur-[90px]" />
          <div className="relative flex flex-col gap-6 p-6 sm:p-8 md:flex-row md:items-center md:justify-between">
            <div className="max-w-xl">
              <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />Build agent</p>
              <h2 className="mt-3 font-display text-[1.6rem] font-semibold leading-[1.1] tracking-[-0.03em] text-balance">
                Describe what your business needs next. <span className="site-serif text-accent">ffinn&nbsp;ships&nbsp;it.</span>
              </h2>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-soft">
                The agent writes the change, checks it against your architecture and opens a pull request for you to review.
              </p>
            </div>
            <div className="flex flex-shrink-0 flex-wrap gap-2">
              <Link href="/app/ai-agent/run" className="site-btn-primary">Start a build <ArrowRight size={16} /></Link>
              <Link href="/app/ai-agent/history" className="site-btn-secondary">History</Link>
            </div>
          </div>
        </section>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <SectionCard title="Recent activity" icon={<Activity size={16} />} className="lg:col-span-2">
          <div className="p-2">
            {actLoading ? (
              <div className="py-10"><LoadingSpinner /></div>
            ) : activity && activity.length > 0 ? (
              <ul>
                {activity.slice(0, 8).map((item, i) => (
                  <li key={item.id || i} className="flex items-start gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-ink/[0.025]">
                    <span className="mt-0.5 grid h-7 w-7 flex-shrink-0 place-items-center rounded-full bg-ink/[0.06] font-display text-[11px] font-semibold text-ink-soft">
                      {(item.userName?.[0] || 'U').toUpperCase()}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-ink-soft">
                        <span className="font-medium text-ink">{item.userName}</span>{' '}
                        {item.action} {item.resource && <span className="font-mono text-[12.5px] text-accent">{item.resource}</span>}
                      </p>
                    </div>
                    {item.createdAt && (
                      <time dateTime={item.createdAt} className="flex-shrink-0 pt-0.5 font-mono text-[11px] text-ink-mute">
                        {formatDistanceToNow(new Date(item.createdAt), { addSuffix: true })}
                      </time>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <span className="grid h-11 w-11 place-items-center rounded-2xl bg-ink/[0.05] text-ink-mute"><Activity size={18} /></span>
                <p className="mt-3 text-sm font-medium text-ink">No activity yet</p>
                <p className="mt-1 text-sm text-ink-mute">Sign-ins, changes and builds will show up here.</p>
              </div>
            )}
          </div>
        </SectionCard>

        {/* Quick Actions */}
        <SectionCard title="Quick actions">
          <div className="p-2">
            {quickActions.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-ink-mute">No quick actions for your role.</p>
            ) : (
              quickActions.map(a => (
                <Link key={a.href} href={a.href}
                  className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-ink/[0.04]">
                  <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-xl bg-ink/[0.05] text-ink-soft transition-colors group-hover:bg-accent/10 group-hover:text-accent">{a.icon}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink">{a.label}</span>
                    <span className="block truncate text-xs text-ink-mute">{a.hint}</span>
                  </span>
                  <ArrowUpRight size={16} className="text-ink-mute transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ink" />
                </Link>
              ))
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
