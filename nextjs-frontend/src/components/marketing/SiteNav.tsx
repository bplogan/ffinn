'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { SiGithub } from 'react-icons/si'
import { GITHUB_URL } from '@/lib/site'
import { Logo } from './Logo'
import ThemeToggle from './ThemeToggle'

const links = [
  { label: 'How it works', href: '/how-it-works', key: 'how' },
  { label: 'Features', href: '/#foundation', key: 'features' },
  { label: 'Guardrails', href: '/#guardrails', key: 'guardrails' },
  { label: 'Docs', href: '/docs', key: 'docs' },
  { label: 'FAQ', href: '/#faq', key: 'faq' },
] as const

export default function SiteNav({ active }: { active?: 'home' | 'how' | 'docs' }) {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <header
      className={`sticky top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300 ${
        scrolled || open ? 'border-b bg-canvas/80 backdrop-blur-xl backdrop-saturate-150' : 'border-b border-transparent'
      }`}
    >
      <div className="site-container flex h-16 items-center justify-between gap-6">
        <Link href="/" aria-label="ffinn home" className="shrink-0"><Logo /></Link>

        <nav aria-label="Main" className="hidden lg:block">
          <ul className="flex items-center gap-1">
            {links.map(l => (
              <li key={l.key}>
                <Link
                  href={l.href}
                  aria-current={active === l.key ? 'page' : undefined}
                  className={`rounded-full px-3.5 py-2 text-[14px] transition-colors hover:text-ink ${active === l.key ? 'text-ink' : 'text-ink-soft'}`}
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-primary hidden h-9 px-4 text-[14px] sm:inline-flex">
            <SiGithub size={15} aria-hidden /> Star on GitHub
          </a>
          <button
            type="button"
            className="grid h-9 w-9 place-items-center rounded-full text-ink hover:bg-ink/[0.06] lg:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen(v => !v)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {open && (
        <div id="mobile-menu" className="site-fade-in h-[calc(100dvh-4rem)] overflow-y-auto border-t bg-canvas lg:hidden">
          <nav aria-label="Mobile" className="site-container flex flex-col py-6">
            {links.map(l => (
              <Link
                key={l.key}
                href={l.href}
                onClick={() => setOpen(false)}
                className="border-b py-4 font-display text-2xl font-medium tracking-[-0.02em]"
              >
                {l.label}
              </Link>
            ))}
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-primary mt-8 h-12">
              <SiGithub size={16} aria-hidden /> Star on GitHub
            </a>
          </nav>
        </div>
      )}
    </header>
  )
}
