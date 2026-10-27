import type { Metadata } from 'next'
import Link from 'next/link'
import SiteShell from '@/components/marketing/SiteShell'

export const metadata: Metadata = {
  title: 'Page not found',
  robots: { index: false, follow: true },
}

export default function NotFound() {
  return (
    <SiteShell>
      <section className="relative overflow-hidden">
        <div aria-hidden className="site-grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent_75%)]" />
        <div className="site-container relative flex min-h-[70vh] flex-col items-center justify-center py-24 text-center">
          <p className="font-mono text-[13px] text-accent">404</p>
          <h1 className="mt-4 font-display text-[clamp(2.4rem,6vw,4.4rem)] font-semibold leading-none tracking-[-0.045em]">
            Nothing <span className="site-serif">shipped</span> here.
          </h1>
          <p className="site-lede mt-5 max-w-md">The link may be old, or the page may have moved.</p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link href="/" className="site-btn-primary">Go to the homepage</Link>
            <Link href="/docs" className="site-btn-secondary">Read the docs</Link>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
