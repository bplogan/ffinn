'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Users, Shield, Building2, Settings, FileText, CreditCard,
  Bot, Zap, History, Globe, GitBranch, Cloud, ChevronDown,
  LogOut, Sparkles, Mail, KeyRound, X, Play, Layers, MessageSquare,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Logo } from '@/components/marketing/Logo'

interface NavItem {
  label:      string
  href?:      string
  icon:       React.ReactNode
  children?:  NavItem[]
  permission?: string
  highlight?: boolean
}

const AI_AGENT_NAV: NavItem = {
  label: 'AI Agent', icon: <Bot size={18} />, highlight: true, permission: 'AIAgent.Use',
  children: [
    { label: 'Overview',       href: '/app/ai-agent',                  icon: <Sparkles size={16} /> },
    { label: 'Agents',         href: '/app/ai-agent/agents',           icon: <Bot size={16} /> },
    { label: 'Generate Code',  href: '/app/ai-agent/run',              icon: <Play size={16} /> },
    { label: 'Providers',      href: '/app/ai-agent/providers',        icon: <Zap size={16} /> },
    { label: 'History',        href: '/app/ai-agent/history',          icon: <History size={16} /> },
    { label: 'Domains',        href: '/app/ai-agent/domains',          icon: <Globe size={16} /> },
    { label: 'Source Control', href: '/app/ai-agent/source-control',   icon: <GitBranch size={16} /> },
  ],
}

// AI-generated tenant feature nav items — DO NOT REMOVE THIS COMMENT
const FEATURE_NAV: NavItem[] = [
  { label: 'Projects', href: '/app/features/projects', icon: <LayoutDashboard size={18} /> },
]

// AI-generated host feature nav items — DO NOT REMOVE THIS COMMENT
const HOST_FEATURE_NAV: NavItem[] = []

// Navigation for the HOST (platform owner — no tenant context). Each admin area
// names a permission so host-level sign-ups only see what they were granted.
const HOST_NAV: NavItem[] = [
  { label: 'Dashboard',  href: '/app/dashboard', icon: <LayoutDashboard size={18} /> },
  ...HOST_FEATURE_NAV,
  { label: 'Tenants',    href: '/app/admin/tenants', icon: <Building2 size={18} />, permission: 'Tenant.Manage' },
  {
    label: 'User Management', icon: <Users size={18} />, permission: 'User.ManageRoles',
    children: [
      { label: 'Users',        href: '/app/admin/users',  icon: <Users size={16} /> },
      { label: 'Roles',        href: '/app/admin/roles',  icon: <Shield size={16} /> },
    ],
  },
  {
    label: 'Platform Setup', icon: <Shield size={18} />, permission: 'System.ManageSettings',
    children: [
      { label: 'Subscr. Plans', href: '/app/admin/subscription-plans', icon: <CreditCard size={16} /> },
      { label: 'Editions',      href: '/app/admin/editions',           icon: <Layers size={16} /> },
      { label: 'Feature Flags', href: '/app/admin/paywall',            icon: <Zap size={16} /> },
      { label: 'Notifications', href: '/app/admin/notifications',      icon: <MessageSquare size={16} /> },
      { label: 'SSO',           href: '/app/admin/sso',                icon: <KeyRound size={16} /> },
      { label: 'Audit Logs',    href: '/app/admin/audit-logs',         icon: <FileText size={16} /> },
      { label: 'Settings',      href: '/app/admin/settings',           icon: <Settings size={16} /> },
    ],
  },
  AI_AGENT_NAV,
  { label: 'Cloud Setup', href: '/app/cloud-setup', icon: <Cloud size={18} />, permission: 'CloudSetup.View' },
]

// Navigation for TENANT users (admins and regular users)
const TENANT_NAV: NavItem[] = [
  { label: 'Dashboard', href: '/app/dashboard', icon: <LayoutDashboard size={18} /> },
  ...FEATURE_NAV,
  {
    label: 'Administration', icon: <Shield size={18} />,
    children: [
      { label: 'Users',        href: '/app/admin/users',            icon: <Users size={16} /> },
      { label: 'Roles',        href: '/app/admin/roles',            icon: <Shield size={16} /> },
      { label: 'Audit Logs',   href: '/app/admin/audit-logs',       icon: <FileText size={16} /> },
      { label: 'Team Invites', href: '/app/admin/team-invitations', icon: <Mail size={16} /> },
      { label: 'Notifications', href: '/app/admin/notifications', icon: <MessageSquare size={16} /> },
      { label: 'SSO',          href: '/app/admin/sso',              icon: <KeyRound size={16} /> },
      { label: 'Settings',     href: '/app/admin/settings',         icon: <Settings size={16} /> },
    ],
  },
  { label: 'Subscription', href: '/app/subscription', icon: <CreditCard size={18} /> },
  { label: 'Settings',     href: '/app/settings',     icon: <Settings size={18} /> },
]

function initials(name?: string | null) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] || 'U') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

function NavLink({ item, depth = 0, onNavigate }: { item: NavItem; depth?: number; onNavigate?: () => void }) {
  const pathname = usePathname()
  const { hasPermission } = useAuth()
  const [open, setOpen] = useState(() => item.children?.some(c => c.href && pathname.startsWith(c.href)) ?? false)

  if (item.permission && !hasPermission(item.permission)) return null

  if (item.children) {
    const isActive = item.children.some(c => c.href && pathname.startsWith(c.href))
    const isHighlight = depth === 0 && item.highlight
    return (
      <div>
        <button
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
          className={clsx(
            'group w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors',
            isActive ? 'text-ink' : 'text-ink-soft hover:bg-ink/[0.05] hover:text-ink',
          )}
        >
          {isHighlight ? (
            <span className="-ml-0.5 grid h-6 w-6 flex-shrink-0 place-items-center rounded-lg bg-accent text-white shadow-[0_4px_12px_-4px_rgb(var(--accent)/0.6)] dark:text-canvas">
              <Bot size={13} />
            </span>
          ) : (
            <span className={clsx('flex-shrink-0', isActive ? 'text-ink' : 'text-ink-mute group-hover:text-ink')}>{item.icon}</span>
          )}
          <span className="flex-1 text-left">{item.label}</span>
          {isHighlight && (
            <span className="rounded-full bg-accent/10 px-1.5 py-px font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-accent">AI</span>
          )}
          <ChevronDown size={14} className={clsx('text-ink-mute transition-transform duration-200', !open && '-rotate-90')} />
        </button>
        {open && (
          <div className="ml-[21px] mt-0.5 mb-1 space-y-px border-l pl-2.5">
            {item.children.map(c => <NavLink key={c.label} item={c} depth={depth + 1} onNavigate={onNavigate} />)}
          </div>
        )}
      </div>
    )
  }

  const isActive = item.href ? pathname === item.href || ( pathname.startsWith(item.href + '/') ) : false

  return (
    <Link
      href={item.href!}
      onClick={onNavigate}
      aria-current={isActive ? 'page' : undefined}
      className={clsx(
        'group relative flex items-center gap-3 rounded-xl px-3 font-medium transition-colors',
        depth > 0 ? 'py-1.5 text-[13.5px]' : 'py-2 text-sm',
        isActive
          ? 'bg-ink/[0.07] text-ink'
          : 'text-ink-soft hover:bg-ink/[0.05] hover:text-ink',
      )}
    >
      {isActive && depth > 0 && <span aria-hidden className="absolute -left-[11px] top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-accent" />}
      <span className={clsx('flex-shrink-0', isActive ? 'text-ink' : 'text-ink-mute group-hover:text-ink')}>{item.icon}</span>
      {item.label}
    </Link>
  )
}

interface SidebarProps { open: boolean; onClose: () => void }

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { user, logout, isHost, hasRole } = useAuth()
  const nav = isHost
    ? HOST_NAV
    : TENANT_NAV.filter(item => item.label !== 'Administration' || hasRole('Admin'))
  const name = user?.fullName || user?.userName

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <>
      {/* Mobile overlay */}
      {open && <div className="fixed inset-0 z-20 bg-black/40 backdrop-blur-[2px] lg:hidden" onClick={onClose} />}

      <aside
        aria-label="Portal"
        className={clsx(
          'fixed inset-y-0 left-0 z-30 flex flex-col w-[264px] bg-surface border-r transition-transform duration-300',
          'lg:translate-x-0 lg:static lg:z-auto',
          open ? 'translate-x-0 shadow-[0_0_60px_-10px_rgb(0_0_0/0.35)] lg:shadow-none' : '-translate-x-full',
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5">
          <Link href="/app/dashboard" onClick={onClose} aria-label="ffinn dashboard" className="flex items-center gap-2.5">
            <Logo />
            {isHost && hasRole('Admin') && (
              <span className="rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-ink-mute ring-1 ring-ink/15">Host</span>
            )}
          </Link>
          <button onClick={onClose} aria-label="Close menu" className="lg:hidden grid h-8 w-8 place-items-center rounded-full text-ink-mute hover:bg-ink/[0.06] hover:text-ink">
            <X size={18} />
          </button>
        </div>

        {/* Which organization is open: people can belong to several */}
        {!isHost && user?.tenantName && (
          <div className="mx-3 mb-2 flex items-center gap-2.5 rounded-xl bg-ink/[0.035] px-2.5 py-2 ring-1 ring-ink/[0.06]">
            <span aria-hidden className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-lg bg-accent/10 font-display text-[12px] font-semibold text-accent">
              {user.tenantName.trim().charAt(0).toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-mute">Organization</span>
              <span className="block truncate text-[13.5px] font-medium text-ink" title={user.tenantName}>{user.tenantName}</span>
            </span>
          </div>
        )}

        {/* Nav */}
        <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 pb-4 pt-2 space-y-px">
          <p className="px-3 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-mute">
            {isHost ? 'Platform' : 'Workspace'}
          </p>
          {nav.map(item => <NavLink key={item.label} item={item} onNavigate={onClose} />)}
        </nav>

        {/* User info */}
        <div className="border-t p-3">
          <div className="flex items-center gap-1 rounded-xl">
            <Link href="/app/profile" onClick={onClose} className="flex flex-1 min-w-0 items-center gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-ink/[0.05]">
              <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-accent/10 font-display text-[12px] font-semibold text-accent">
                {initials(name)}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{name}</span>
                <span className="block truncate text-xs text-ink-mute">{user?.email}</span>
              </span>
            </Link>
            <button
              onClick={logout}
              aria-label="Sign out"
              title="Sign out"
              className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-full text-ink-mute transition-colors hover:bg-error-500/10 hover:text-error-600 dark:hover:text-error-400"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
