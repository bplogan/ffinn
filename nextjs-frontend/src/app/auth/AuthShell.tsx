'use client'
import { useAuth } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, Check, GitPullRequest, KeyRound, Scale } from 'lucide-react'
import { Logo } from '@/components/marketing/Logo'
import ThemeToggle from '@/components/marketing/ThemeToggle'

/**
 * Chrome for sign-in, registration and plan selection, on the public site's design
 * system. The default layout is a form column beside a product panel; `wide` drops the
 * panel for full-width content such as the plan picker.
 */
export default function AuthShell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  useEffect(() => {
    // Plan selection stays reachable when signed in; account screens send you to the portal.
    if (!wide && !isLoading && isAuthenticated) router.replace('/app/dashboard')
  }, [wide, isAuthenticated, isLoading, router])

  return (
    <div className="site min-h-screen antialiased">
      <div className={wide ? '' : 'lg:grid lg:min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]'}>
        <div className="flex min-h-screen flex-col">
          <header className={`flex h-16 items-center justify-between gap-4 ${wide ? 'site-container' : 'px-5 sm:px-8'}`}>
            <Link href="/" aria-label="ffinn home"><Logo /></Link>
            <div className="flex items-center gap-1">
              <Link href="/" className="hidden items-center gap-1.5 rounded-full px-3.5 py-2 text-[14px] text-ink-soft transition-colors hover:text-ink sm:inline-flex">
                <ArrowLeft size={14} aria-hidden /> Back to site
              </Link>
              <ThemeToggle />
            </div>
          </header>

          <main id="main" className={`flex flex-1 ${wide ? 'site-container py-10 sm:py-14' : 'items-center justify-center px-5 py-10 sm:px-8'}`}>
            <div className={`site-fade-in w-full ${wide ? '' : 'max-w-[400px]'}`}>{children}</div>
          </main>

          <footer className={`flex flex-wrap items-center justify-between gap-3 pb-6 text-[12.5px] text-ink-mute ${wide ? 'site-container' : 'px-5 sm:px-8'}`}>
            <p>© {new Date().getFullYear()} ffinn contributors · MIT License</p>
            <nav aria-label="Help" className="flex gap-4">
              <Link href="/docs" className="transition-colors hover:text-ink">Docs</Link>
              <Link href="/how-it-works" className="transition-colors hover:text-ink">How it works</Link>
              <a href="mailto:info@ffinn.ca" className="transition-colors hover:text-ink">Contact</a>
            </nav>
          </footer>
        </div>

        {!wide && <ProductPanel />}
      </div>
    </div>
  )
}

const RUN = [
  { text: 'Read your codebase', sub: '42 files in context' },
  { text: 'Plan the change', sub: 'model · service · API · page' },
  { text: 'Write the code', sub: '6 files · +410 lines' },
  { text: 'Check architecture', sub: '6 of 6 files pass' },
  { text: 'Open pull request', sub: '#48 · ai-agent/online-booking' },
]

const POINTS = [
  { icon: GitPullRequest, text: 'Every change arrives as a pull request. Nothing merges without you.' },
  { icon: KeyRound, text: 'AI provider keys are encrypted before they are stored.' },
  { icon: Scale, text: 'Free and open source under the MIT License.' },
]

/** Dark product panel beside the form: the same build run the home page shows, at rest. */
function ProductPanel() {
  return (
    <aside aria-hidden className="relative hidden p-3 lg:block">
      <div className="ink-scope relative flex h-full min-h-[640px] flex-col overflow-hidden rounded-[28px] bg-canvas text-ink">
        <div className="site-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_75%_60%_at_60%_35%,black,transparent)]" />
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-accent/25 blur-[110px]" />

        <div className="relative flex flex-1 flex-col justify-between gap-12 p-10 xl:p-14">
          <div>
            <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" />Describe · review · ship</p>
            <p className="mt-6 max-w-md font-display text-[clamp(2rem,3vw,2.75rem)] font-semibold leading-[1.04] tracking-[-0.035em] text-balance">
              Describe what your business needs. <span className="site-serif text-accent">ffinn&nbsp;ships&nbsp;it.</span>
            </p>
          </div>

          <div className="max-w-md rounded-[20px] bg-surface/90 ring-1 ring-white/10 shadow-[0_40px_80px_-40px_rgb(0_0_0/0.7)] backdrop-blur">
            <div className="flex items-center justify-between border-b px-5 py-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">
              <span>Build agent</span>
              <span className="inline-flex items-center gap-1.5 normal-case tracking-normal text-accent">
                <span className="site-live-dot h-1.5 w-1.5 rounded-full bg-accent" />waiting for review
              </span>
            </div>
            <ol className="space-y-3 p-5">
              {RUN.map(step => (
                <li key={step.text} className="flex items-center gap-3">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-signal text-canvas"><Check size={12} strokeWidth={3} /></span>
                  <span className="text-[14px] font-medium">{step.text}</span>
                  <span className="ml-auto truncate font-mono text-[11.5px] text-ink-mute">{step.sub}</span>
                </li>
              ))}
            </ol>
          </div>

          <ul className="space-y-3.5">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-[14px] leading-relaxed text-ink-soft">
                <Icon size={16} className="mt-[3px] shrink-0 text-ink-mute" />
                {text}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  )
}

/** Page heading for the auth screens: mono eyebrow, display title, optional lede. */
export function AuthHeading({ eyebrow, title, lede }: { eyebrow: string; title: React.ReactNode; lede?: React.ReactNode }) {
  return (
    <div className="mb-8">
      <p className="site-eyebrow">{eyebrow}</p>
      <h1 className="mt-3 font-display text-[2.1rem] font-semibold leading-[1.05] tracking-[-0.035em] text-balance">{title}</h1>
      {lede && <p className="mt-3 text-[15px] leading-relaxed text-ink-soft text-pretty">{lede}</p>}
    </div>
  )
}

/** Result screen (email sent, confirmed, failed) with a round status icon. */
export function AuthStatus({ tone, icon, title, children }: { tone: 'ok' | 'bad' | 'info'; icon: React.ReactNode; title: string; children?: React.ReactNode }) {
  const ring = { ok: 'bg-signal/10 text-signal', bad: 'bg-error-500/10 text-error-600 dark:text-error-400', info: 'bg-accent/10 text-accent' }[tone]
  return (
    <div>
      <span className={`grid h-12 w-12 place-items-center rounded-2xl ${ring}`}>{icon}</span>
      <h1 className="mt-6 font-display text-[1.9rem] font-semibold leading-[1.08] tracking-[-0.035em]">{title}</h1>
      <div className="mt-3 space-y-6 text-[15px] leading-relaxed text-ink-soft">{children}</div>
    </div>
  )
}

/** Inline text link in the auth screens. */
export const authLink = 'font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink'
