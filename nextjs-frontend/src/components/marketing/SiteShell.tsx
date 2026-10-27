import Link from 'next/link'
import { GITHUB_URL } from '@/lib/site'
import SiteNav from './SiteNav'
import { Logo } from './Logo'

/** Wraps every public page: theme tokens, skip link, nav and footer. */
export default function SiteShell({ children, active }: { children: React.ReactNode; active?: 'home' | 'how' | 'docs' }) {
  return (
    <div className="site min-h-screen antialiased">
      <a href="#main" className="sr-only-focusable fixed left-4 top-4 z-[60] rounded-full bg-ink px-4 py-2 text-sm text-canvas">
        Skip to content
      </a>
      <SiteNav active={active} />
      <main id="main">{children}</main>
      <SiteFooter />
    </div>
  )
}

const footerColumns = [
  {
    title: 'Product',
    links: [
      { label: 'How it works', href: '/how-it-works' },
      { label: 'Features', href: '/#foundation' },
      { label: 'Guardrails', href: '/#guardrails' },
      { label: 'Documentation', href: '/docs' },
      { label: 'Sign in', href: '/auth/login' },
    ],
  },
  {
    title: 'Open source',
    links: [
      { label: 'GitHub', href: GITHUB_URL, external: true },
      { label: 'Contributing', href: `${GITHUB_URL}/blob/main/CONTRIBUTING.md`, external: true },
      { label: 'Issues & ideas', href: `${GITHUB_URL}/issues`, external: true },
      { label: 'Security', href: `${GITHUB_URL}/blob/main/SECURITY.md`, external: true },
      { label: 'MIT License', href: `${GITHUB_URL}/blob/main/LICENSE`, external: true },
    ],
  },
]

function SiteFooter() {
  return (
    <footer className="relative overflow-hidden border-t">
      <div className="site-container pt-16 pb-10">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="max-w-xs">
            <Link href="/" aria-label="ffinn home"><Logo /></Link>
            <p className="mt-4 text-sm leading-relaxed text-ink-mute">
              The free, open-source foundation for business software, with an AI agent that builds what you describe.
            </p>
          </div>
          {footerColumns.map(col => (
            <nav key={col.title} aria-label={col.title}>
              <h2 className="site-eyebrow">{col.title}</h2>
              <ul className="mt-4 space-y-2.5">
                {col.links.map(l => (
                  <li key={l.label}>
                    {'external' in l && l.external ? (
                      <a href={l.href} target="_blank" rel="noopener noreferrer" className="text-sm text-ink-soft transition-colors hover:text-ink">{l.label}</a>
                    ) : (
                      <Link href={l.href} className="text-sm text-ink-soft transition-colors hover:text-ink">{l.label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
          <div>
            <h2 className="site-eyebrow">Contact</h2>
            <ul className="mt-4 space-y-2.5">
              <li><a href="mailto:info@ffinn.ca" className="text-sm text-ink-soft transition-colors hover:text-ink">info@ffinn.ca</a></li>
            </ul>
          </div>
        </div>
        <div className="mt-16 flex flex-col gap-3 border-t pt-6 text-[13px] text-ink-mute sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} ffinn contributors. Free and open source under the MIT License.</p>
          <p className="font-mono text-[12px]">FastAPI · Next.js · PostgreSQL</p>
        </div>
      </div>
      {/* Oversized wordmark, clipped by the footer edge */}
      <div aria-hidden className="pointer-events-none select-none site-container translate-y-[22%]">
        <div className="font-display text-[clamp(6rem,26vw,22rem)] font-semibold leading-[0.8] tracking-[-0.07em] text-ink/[0.06]">ffinn</div>
      </div>
    </footer>
  )
}
