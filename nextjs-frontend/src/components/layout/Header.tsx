'use client'
import { Menu, Bell, Search, LogOut, Eye, User, Settings, CreditCard } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Link from 'next/link'
import { Fragment, useEffect, useState } from 'react'
import GenerationInProgressIndicator from '@/components/ai-agent/GenerationInProgressIndicator'
import Button from '@/components/ui/Button'
import ThemeToggle from '@/components/marketing/ThemeToggle'

interface HeaderProps { onMenuClick: () => void }

/** "/app/admin/team-invitations" → ["Admin", "Team invitations"], for the header trail. */
function trail(pathname: string) {
  return pathname
    .replace(/^\/app\/?/, '')
    .split('/')
    .filter(seg => seg && !/^[0-9a-f-]{8,}$/i.test(seg))
    .slice(0, 2)
    .map(seg => {
      const words = seg.replace(/-/g, ' ')
      return seg === 'ai-agent' ? 'AI agent' : words.charAt(0).toUpperCase() + words.slice(1)
    })
}

export default function Header({ onMenuClick }: HeaderProps) {
  const pathname = usePathname()
  const { user, isHost, isImpersonating, endImpersonation } = useAuth()
  const [userOpen, setUserOpen] = useState(false)
  const [endingImpersonation, setEndingImpersonation] = useState(false)
  const crumbs = trail(pathname)

  useEffect(() => {
    if (!userOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setUserOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [userOpen])

  const handleEndImpersonation = async () => {
    setEndingImpersonation(true)
    setUserOpen(false)
    try {
      await endImpersonation()
    } finally {
      setEndingImpersonation(false)
    }
  }

  const menuItem = 'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-ink-soft transition-colors hover:bg-ink/[0.05] hover:text-ink'

  return (
    <>
      {isImpersonating && (
        <div className="ink-scope sticky top-0 z-20 bg-canvas text-ink">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-2.5 md:px-8">
            <div className="flex items-start sm:items-center gap-2.5 min-w-0 text-sm text-ink-soft">
              <span className="mt-0.5 sm:mt-0 grid h-7 w-7 flex-shrink-0 place-items-center rounded-lg bg-caution/15 text-caution">
                <Eye size={14} />
              </span>
              <p className="leading-snug">
                Viewing as{' '}
                <span className="font-medium text-ink">
                  {user?.fullName || user?.userName}
                </span>
                {user?.impersonatorUserName ? (
                  <span className="text-ink-mute">
                    {' '}
                    · signed in by {user.impersonatorUserName}
                  </span>
                ) : null}
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              loading={endingImpersonation}
              onClick={handleEndImpersonation}
              className="flex-shrink-0"
            >
              Back to my account
            </Button>
          </div>
        </div>
      )}

      <header className="sticky top-0 z-10 flex h-16 items-center gap-3 border-b bg-canvas/80 px-4 backdrop-blur-xl backdrop-saturate-150 md:px-8">
        {/* Mobile menu */}
        <button onClick={onMenuClick} aria-label="Open menu" className="lg:hidden -ml-1 grid h-9 w-9 place-items-center rounded-full text-ink-soft hover:bg-ink/[0.06] hover:text-ink">
          <Menu size={20} />
        </button>

        {/* Where you are */}
        <nav aria-label="Location" className="hidden min-w-0 items-center gap-2 font-mono text-[11.5px] uppercase tracking-[0.12em] text-ink-mute sm:flex">
          {crumbs.map((c, i) => (
            <Fragment key={i}>
              {i > 0 && <span aria-hidden className="text-ink/20">/</span>}
              <span className={`truncate ${i === crumbs.length - 1 ? 'text-ink-soft' : ''}`}>{c}</span>
            </Fragment>
          ))}
        </nav>

        <div className="flex-1" />

        {/* Search (placeholder until search ships) */}
        <div className="hidden md:flex w-full max-w-[260px] items-center gap-2 rounded-full bg-surface px-3.5 h-9 text-ink-mute ring-1 ring-ink/10">
          <Search size={15} />
          <span className="text-[13px]">Quick search…</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-0.5">
          <ThemeToggle />

          {/* Code generation in progress — host only */}
          {isHost && <GenerationInProgressIndicator />}

          {/* Notifications */}
          <Link href="/app/settings" aria-label="Notification settings" title="Settings" className="grid h-9 w-9 place-items-center rounded-full text-ink-soft transition-colors hover:bg-ink/[0.06] hover:text-ink">
            <Bell size={17} strokeWidth={1.75} />
          </Link>

          {/* User avatar */}
          <div className="relative ml-1.5">
            <button
              onClick={() => setUserOpen(o => !o)}
              aria-label="Account menu"
              aria-expanded={userOpen}
              aria-haspopup="menu"
              className="grid h-9 w-9 place-items-center rounded-full bg-accent/10 font-display text-[13px] font-semibold text-accent ring-1 ring-accent/20 transition-[box-shadow] hover:ring-accent/40"
            >
              {(user?.firstName?.[0] || user?.userName?.[0] || 'U').toUpperCase()}
            </button>

            {userOpen && (
              <Fragment>
                <div className="fixed inset-0 z-10" onClick={() => setUserOpen(false)} />
                <div role="menu" className="site-fade-in absolute right-0 z-20 mt-2 w-60 rounded-2xl bg-surface p-1.5 ring-1 ring-ink/10 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.35)]">
                  <div className="px-2.5 pb-2.5 pt-2 border-b mb-1.5">
                    <p className="truncate text-sm font-medium text-ink">{user?.fullName || user?.userName}</p>
                    <p className="truncate text-xs text-ink-mute">{user?.email}</p>
                    {isImpersonating && (
                      <p className="mt-1.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-caution">Impersonating</p>
                    )}
                  </div>
                  {isImpersonating && (
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleEndImpersonation}
                      disabled={endingImpersonation}
                      className={`${menuItem} w-full text-left text-caution hover:text-caution`}
                    >
                      <LogOut size={15} />
                      {endingImpersonation ? 'Returning…' : 'Back to my account'}
                    </button>
                  )}
                  <Link href="/app/profile" role="menuitem" onClick={() => setUserOpen(false)} className={menuItem}>
                    <User size={15} className="text-ink-mute" /> Profile
                  </Link>
                  <Link href="/app/settings" role="menuitem" onClick={() => setUserOpen(false)} className={menuItem}>
                    <Settings size={15} className="text-ink-mute" /> Settings
                  </Link>
                  <Link href="/app/subscription" role="menuitem" onClick={() => setUserOpen(false)} className={menuItem}>
                    <CreditCard size={15} className="text-ink-mute" /> Subscription
                  </Link>
                </div>
              </Fragment>
            )}
          </div>
        </div>
      </header>
    </>
  )
}
