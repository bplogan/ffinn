'use client'
import { useEffect, useState } from 'react'

/** Sticky phase bar for the walkthrough; highlights the phase of the step in view. */
export default function PhaseNav({ phases }: { phases: { id: string; label: string; first: string }[] }) {
  const [active, setActive] = useState<string | undefined>(phases[0]?.id)

  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>('[data-phase]'))
    const io = new IntersectionObserver(
      entries => entries.forEach(e => e.isIntersecting && setActive((e.target as HTMLElement).dataset.phase)),
      { rootMargin: '-40% 0px -55% 0px' },
    )
    els.forEach(el => io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <nav aria-label="Phases" className="sticky top-16 z-40 border-y bg-canvas/85 backdrop-blur-xl">
      <ol className="site-container flex gap-1 overflow-x-auto py-2.5 [scrollbar-width:none]">
        {phases.map((p, i) => (
          <li key={p.id} className="shrink-0">
            <a
              href={`#${p.first}`}
              aria-current={active === p.id ? 'step' : undefined}
              className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[13.5px] transition-colors ${
                active === p.id ? 'bg-ink text-canvas' : 'text-ink-mute hover:text-ink'
              }`}
            >
              <span className="font-mono text-[11px] opacity-70">{String(i + 1).padStart(2, '0')}</span>
              {p.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}
