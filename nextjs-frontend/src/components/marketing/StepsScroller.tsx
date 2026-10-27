'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Check, GitBranch, GitPullRequest, Lock, MessageSquareText, Rocket, Sparkles } from 'lucide-react'

/*
 * "Describe → Review → Ship". On large screens the visual is sticky and swaps as
 * each step crosses the middle of the viewport; on small screens every step
 * carries its own visual inline.
 */

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/[0.05] px-2.5 py-1 font-mono text-[11.5px] text-ink-soft">{children}</span>
}

function DescribeVisual() {
  return (
    <div className="site-card p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[13px] text-ink-mute"><MessageSquareText size={15} /> New request</div>
      <p className="mt-4 font-display text-[19px] leading-[1.5] tracking-[-0.01em] text-ink sm:text-[21px]">
        Add a <mark className="rounded bg-accent/10 px-1 text-ink">Customer</mark> list with name, email and phone.
        Only <mark className="rounded bg-accent/10 px-1 text-ink">admins</mark> can delete, and every deletion goes to the{' '}
        <mark className="rounded bg-accent/10 px-1 text-ink">audit log</mark>.
      </p>
      <div className="mt-6 flex flex-wrap gap-2">
        <Chip><Sparkles size={12} /> Claude</Chip>
        <Chip><GitBranch size={12} /> acme/portal · main</Chip>
        <Chip>scope: tenant</Chip>
      </div>
      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <span className="text-[13px] text-ink-mute">Plain English is enough. Detail helps.</span>
        <span className="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full bg-ink px-4 text-[13px] font-medium text-canvas">Build it <ArrowRight size={14} /></span>
      </div>
    </div>
  )
}

const prFiles = [
  ['domain/models/customer.py', 52, 0],
  ['services/customer_service.py', 96, 0],
  ['api/customers.py', 61, 0],
  ['features/customers/page.tsx', 118, 0],
  ['api/router.py', 2, 0],
] as const

function ReviewVisual() {
  return (
    <div className="site-card overflow-hidden">
      <div className="p-5 sm:p-6">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-signal/15 px-2.5 py-1 text-[12px] font-medium text-signal"><GitPullRequest size={13} /> Open</span>
          <span className="font-mono text-[12px] text-ink-mute">#52</span>
        </div>
        <h4 className="mt-3 font-display text-[20px] font-semibold tracking-[-0.02em]">Add customer list with admin-only delete</h4>
        <p className="mt-1 font-mono text-[12px] text-ink-mute">ai-agent/customer-list → main</p>
      </div>
      <ul className="divide-y border-y">
        {[
          ['Architecture rules', '5 of 5 files pass'],
          ['Protected files', 'None touched'],
          ['Tenant isolation', 'Every query scoped to the tenant'],
        ].map(([k, v]) => (
          <li key={k} className="flex items-center gap-3 px-5 py-2.5 text-[13.5px] sm:px-6">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-signal text-canvas"><Check size={12} strokeWidth={3} /></span>
            <span className="text-ink">{k}</span>
            <span className="ml-auto text-ink-mute">{v}</span>
          </li>
        ))}
      </ul>
      <ul className="space-y-1 p-3 font-mono text-[12px] sm:p-4">
        {prFiles.map(([f, add]) => (
          <li key={f} className="flex items-center justify-between rounded-md px-2 py-1 hover:bg-ink/[0.03]">
            <span className="truncate text-ink-soft">{f}</span>
            <span className="text-signal">+{add}</span>
          </li>
        ))}
      </ul>
      <div className="flex gap-2 border-t p-4 sm:px-6">
        <span className="inline-flex h-9 items-center rounded-full bg-ink px-4 text-[13px] font-medium text-canvas">Approve</span>
        <span className="inline-flex h-9 items-center rounded-full px-4 text-[13px] text-ink-soft ring-1 ring-ink/15">Ask for changes</span>
      </div>
    </div>
  )
}

function ShipVisual() {
  const envs = [
    { name: 'Branch', detail: 'ai-agent/customer-list', state: 'Merged' },
    { name: 'Staging', detail: 'staging.acme.app', state: 'Verified' },
    { name: 'Production', detail: 'acme.app', state: 'Ready' },
  ]
  return (
    <div className="site-card p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[13px] text-ink-mute"><Rocket size={15} /> Releases</div>
      <ol className="mt-5 grid grid-cols-3 gap-2">
        {envs.map((e, i) => (
          <li key={e.name} className={`rounded-xl p-3 ring-1 ${i === 2 ? 'bg-accent/[0.07] ring-accent/30' : 'ring-ink/10'}`}>
            <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink">
              <span className={`h-1.5 w-1.5 rounded-full ${i === 2 ? 'site-live-dot bg-accent' : 'bg-signal'}`} />{e.name}
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-ink-mute">{e.detail}</div>
            <div className={`mt-3 text-[12px] ${i === 2 ? 'text-accent' : 'text-signal'}`}>{e.state}</div>
          </li>
        ))}
      </ol>
      <div className="mt-4 space-y-1.5 rounded-xl bg-ink/[0.035] p-4 font-mono text-[12px] leading-5 text-ink-soft">
        <div><span className="text-ink-mute">▸</span> GitHub Actions workflow started</div>
        <div><span className="text-ink-mute">▸</span> Database migrations applied</div>
        <div><span className="text-ink-mute">▸</span> Health check passed</div>
        <div className="text-signal">✓ Staging verified by you</div>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-mute"><Lock size={13} /> Production waits for you</span>
        <span className="inline-flex h-9 items-center gap-1.5 rounded-full bg-accent px-4 text-[13px] font-medium text-white dark:text-[#0b0c10]">Promote</span>
      </div>
    </div>
  )
}

const steps = [
  {
    n: '01',
    title: 'Describe it',
    body: 'Write the feature the way you would brief a developer. ffinn reads your codebase first, so it knows the models, services and screens it is building next to.',
    points: ['Plain-English requests', 'Uses the AI model you choose', 'Follow-ups refine earlier work'],
    Visual: DescribeVisual,
  },
  {
    n: '02',
    title: 'Review it',
    body: 'Every request becomes one branch and one pull request in your repository, already checked against the architecture rules. Read the diff, approve it, or ask for changes.',
    points: ['One feature, one pull request', 'Architecture checked before commit', 'Protected core never touched'],
    Visual: ReviewVisual,
  },
  {
    n: '03',
    title: 'Ship it',
    body: 'Deploy to staging from the dashboard and watch the build stream in live. Try it with real data. When it is right, promote it to production. Changed your mind? Revert.',
    points: ['Staging before production', 'Live deploy status', 'One-click revert'],
    Visual: ShipVisual,
  },
]

export default function StepsScroller() {
  const [active, setActive] = useState(0)
  const refs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const io = new IntersectionObserver(
      entries => entries.forEach(e => e.isIntersecting && setActive(Number((e.target as HTMLElement).dataset.i))),
      { rootMargin: '-45% 0px -45% 0px' },
    )
    refs.current.forEach(el => el && io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <div className="grid gap-12 lg:grid-cols-[1fr_1.05fr] lg:gap-20">
      <div>
        {steps.map((s, i) => (
          <div
            key={s.n}
            ref={el => { refs.current[i] = el }}
            data-i={i}
            className={`flex flex-col justify-center py-10 transition-opacity duration-500 lg:min-h-[78vh] lg:py-0 ${active === i ? 'lg:opacity-100' : 'lg:opacity-30'}`}
          >
            <div className="font-mono text-[13px] text-accent">{s.n}</div>
            <h3 className="mt-3 font-display text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-none tracking-[-0.035em]">{s.title}</h3>
            <p className="site-lede mt-5 max-w-md">{s.body}</p>
            <ul className="mt-6 space-y-2">
              {s.points.map(p => (
                <li key={p} className="flex items-center gap-2.5 text-[15px] text-ink-soft">
                  <Check size={15} className="text-accent" strokeWidth={2.5} />{p}
                </li>
              ))}
            </ul>
            <div className="mt-10 lg:hidden"><s.Visual /></div>
          </div>
        ))}
      </div>

      <div className="hidden lg:block">
        <div className="sticky top-[calc(50vh-290px)] h-[580px]">
          <div className="flex items-center gap-1.5" aria-hidden>
            {steps.map((s, i) => (
              <span
                key={s.n}
                className={`rounded-full px-3 py-1 font-mono text-[12px] transition-colors duration-300 ${active === i ? 'bg-ink text-canvas' : 'text-ink-mute'}`}
              >
                {s.n} {s.title.split(' ')[0]}
              </span>
            ))}
          </div>
          <div className="relative mt-4 h-[520px]">
            {steps.map((s, i) => (
              // Outgoing card fades fast, incoming waits a beat, so the two never blend
              <div
                key={s.n}
                aria-hidden={active !== i}
                className={`absolute inset-0 flex items-center transition-[opacity,transform] ease-[cubic-bezier(0.2,0.7,0.2,1)] ${
                  active === i
                    ? 'translate-y-0 scale-100 opacity-100 delay-150 duration-700'
                    : `${i < active ? '-translate-y-6' : 'translate-y-6'} pointer-events-none scale-[0.98] opacity-0 duration-200`
                }`}
              >
                <div className="w-full"><s.Visual /></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
