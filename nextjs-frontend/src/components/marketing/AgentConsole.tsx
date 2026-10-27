'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Check, CornerDownLeft, Loader2, TriangleAlert } from 'lucide-react'

/*
 * Hero mock-up of the build agent: a request is typed, then the pipeline runs
 * read → plan → generate → check → PR → staging and stops at production, waiting
 * for a human. Everything is derived from one elapsed-time value so the loop is
 * easy to tune; reduced-motion users get the finished state with no animation.
 */

const PROMPT =
  'Let customers book appointments online. They pick a service, a date and an open time slot. Email staff about each new booking and give admins a calendar view.'

const TYPE_MS = 18
const TYPED_AT = PROMPT.length * TYPE_MS + 300
const LOOP_MS = TYPED_AT + 13_500

type Status = 'pending' | 'running' | 'issue' | 'done' | 'waiting'
type Step = { title: string; start: number; end: number; running: string; done: string; issue?: [number, number, string] }

const STEPS: Step[] = [
  { title: 'Read your codebase', start: 200, end: 1300, running: 'Loading models, services and routes…', done: '42 files in context' },
  { title: 'Plan the change', start: 1300, end: 2300, running: 'Mapping the request to each layer…', done: 'Model · service · API · page' },
  { title: 'Write the code', start: 2300, end: 4300, running: 'Generating files…', done: '6 files · +410 lines' },
  { title: 'Check architecture', start: 4300, end: 6000, running: 'Validating against the rules…', done: '6 of 6 files pass · 1 fixed', issue: [5000, 5700, 'Route queries the database directly, fixing'] },
  { title: 'Open pull request', start: 6000, end: 6900, running: 'Committing to a new branch…', done: '#48 · ai-agent/online-booking' },
  { title: 'Deploy to staging', start: 6900, end: 8800, running: 'Running your workflow…', done: 'Live at staging.acme.app' },
]
const PROD_AT = TYPED_AT + 8800

const FILES = [
  ['domain/models/', 'booking.py', 58],
  ['services/', 'booking_service.py', 121],
  ['schemas/', 'booking_schemas.py', 44],
  ['api/', 'bookings.py', 76],
  ['features/bookings/', 'page.tsx', 109],
  ['api/', 'router.py', 2],
] as const

function statusOf(step: Step, t: number): Status {
  const s = step.start + TYPED_AT
  const e = step.end + TYPED_AT
  if (t < s) return 'pending'
  if (t >= e) return 'done'
  if (step.issue && t >= step.issue[0] + TYPED_AT && t < step.issue[1] + TYPED_AT) return 'issue'
  return 'running'
}

function Marker({ status }: { status: Status }) {
  const base = 'relative z-10 grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full transition-colors duration-300'
  if (status === 'done') return <span className={`${base} bg-signal text-canvas`}><Check size={13} strokeWidth={3} /></span>
  if (status === 'running') return <span className={`${base} bg-canvas text-accent ring-1 ring-accent/50`}><Loader2 size={13} className="animate-spin motion-reduce:animate-none" /></span>
  if (status === 'issue') return <span className={`${base} bg-caution text-canvas`}><TriangleAlert size={12} strokeWidth={2.5} /></span>
  if (status === 'waiting') return <span className={`${base} site-live-dot bg-accent text-canvas`}><span className="h-1.5 w-1.5 rounded-full bg-canvas" /></span>
  return <span className={`${base} bg-canvas ring-1 ring-ink/15`} />
}

export default function AgentConsole() {
  const [t, setT] = useState(0)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setT(PROD_AT + 1)
      return
    }
    let visible = true
    let last = performance.now()
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting }, { threshold: 0.15 })
    if (root.current) io.observe(root.current)
    const id = window.setInterval(() => {
      const now = performance.now()
      const dt = Math.min(now - last, 100)
      last = now
      if (!visible || document.hidden) return
      setT(prev => (prev + dt) % LOOP_MS)
    }, 32)
    return () => { window.clearInterval(id); io.disconnect() }
  }, [])

  const typed = PROMPT.slice(0, Math.floor(t / TYPE_MS))
  const typing = t < TYPED_AT
  const awaiting = t >= PROD_AT
  const genStart = STEPS[2].start + TYPED_AT
  const filesShown = t < genStart ? 0 : Math.min(FILES.length, Math.floor((t - genStart) / 280) + 1)

  return (
    <div ref={root} className="ink-scope relative">
      {/* Accessible summary of what the animation shows */}
      <p className="sr-only">
        Example: a request for online booking is typed into ffinn. The agent reads the codebase, plans the change, writes six files,
        fixes one architecture issue, opens pull request 48, deploys to staging, and then waits for a person to approve the production release.
      </p>

      <div aria-hidden className="overflow-hidden rounded-[20px] bg-canvas text-ink ring-1 ring-white/10 shadow-[0_0_0_1px_rgb(0_0_0/0.5),0_40px_100px_-30px_rgb(0_0_0/0.55),0_20px_40px_-20px_rgb(54_65_245/0.25)]">
        {/* Title bar */}
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-2.5 text-[13px]">
            <span className="grid h-6 w-6 place-items-center rounded-md bg-ink/10 font-display text-[12px] font-semibold">f</span>
            <span className="truncate text-ink-mute">acme-portal <span className="px-1 text-ink/25">/</span> <span className="text-ink">Build agent</span></span>
          </div>
          <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] ${awaiting ? 'bg-accent/15 text-accent' : 'bg-ink/[0.07] text-ink-soft'}`}>
            {awaiting ? <><span className="site-live-dot h-1.5 w-1.5 rounded-full bg-accent" />Awaiting approval</> : typing ? 'Drafting request' : <><Loader2 size={11} className="animate-spin motion-reduce:animate-none" />Building</>}
          </span>
        </div>

        <div className="grid md:grid-cols-[1.05fr_1fr]">
          {/* Request + changes */}
          <div className="border-b p-4 sm:p-5 md:border-b-0 md:border-r">
            <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">
              <span>Request</span><span className="normal-case tracking-normal">you · now</span>
            </div>
            <div className="mt-3 min-h-[118px] rounded-xl bg-surface p-3.5 text-[14px] leading-[1.6] text-ink ring-1 ring-ink/10 sm:min-h-[104px]">
              {typed}
              {typing && <span className="site-caret ml-px inline-block h-[1.05em] w-[2px] translate-y-[3px] bg-accent" />}
              {!typing && (
                <div className="site-fade-in mt-3 flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-ink-mute">
                  <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">model: claude</span>
                  <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">repo: acme/portal</span>
                  <span className="ml-auto inline-flex items-center gap-1 text-ink-soft">sent <CornerDownLeft size={11} /></span>
                </div>
              )}
            </div>

            <div className="mt-5 hidden sm:block">
              <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">
                <span>Changes</span>
                <span className="normal-case tracking-normal text-signal">{filesShown ? `+${FILES.slice(0, filesShown).reduce((n, f) => n + f[2], 0)}` : ''}</span>
              </div>
              <ul className="mt-2.5 space-y-1 font-mono text-[12.5px]">
                {FILES.map(([dir, name, add], i) => (
                  <li
                    key={dir + name}
                    className={`flex items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 transition-all duration-300 ${i < filesShown ? 'bg-ink/[0.035] opacity-100' : 'translate-y-1 opacity-0'}`}
                  >
                    <span className="truncate"><span className="text-ink-mute">{dir}</span>{name}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="hidden gap-[2px] lg:flex">
                        {Array.from({ length: 5 }, (_, b) => (
                          <span key={b} className={`h-2 w-2 rounded-[2px] ${b < Math.max(1, Math.round(add / 25)) ? 'bg-signal/80' : 'bg-ink/10'}`} />
                        ))}
                      </span>
                      <span className="w-9 text-right text-signal">+{add}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Pipeline */}
          <div className="p-4 sm:p-5">
            <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">Pipeline</div>
            <ol className="relative mt-3">
              <span className="absolute bottom-3 left-[10.5px] top-3 w-px bg-ink/10" />
              {STEPS.map(step => {
                const st = statusOf(step, t)
                return (
                  <li key={step.title} className="relative flex gap-3 py-[7px]">
                    <Marker status={st} />
                    <div className="min-w-0 pt-px">
                      <div className={`text-[14px] leading-5 transition-colors ${st === 'pending' ? 'text-ink-mute' : 'text-ink'}`}>{step.title}</div>
                      <div className={`truncate font-mono text-[11.5px] leading-5 ${st === 'issue' ? 'text-caution' : 'text-ink-mute'}`}>
                        {st === 'pending' ? ' ' : st === 'issue' ? step.issue![2] : st === 'running' ? step.running : step.done}
                      </div>
                    </div>
                  </li>
                )
              })}
              <li className="relative flex gap-3 py-[7px]">
                <Marker status={awaiting ? 'waiting' : 'pending'} />
                <div className="min-w-0 flex-1 pt-px">
                  <div className={`text-[14px] leading-5 ${awaiting ? 'text-ink' : 'text-ink-mute'}`}>Release to production</div>
                  <div className="font-mono text-[11.5px] leading-5 text-ink-mute">{awaiting ? 'Waiting for your approval' : ' '}</div>
                  <div className={`mt-2.5 flex flex-wrap gap-2 transition-all duration-500 ${awaiting ? 'opacity-100' : 'pointer-events-none translate-y-1 opacity-0'}`}>
                    <span className="inline-flex h-8 items-center gap-1.5 rounded-full bg-accent px-3.5 text-[13px] font-medium text-[#0b0c10]">
                      Promote to production <ArrowUpRight size={14} />
                    </span>
                    <span className="inline-flex h-8 items-center rounded-full px-3 text-[13px] text-ink-soft ring-1 ring-ink/15">Open staging</span>
                  </div>
                </div>
              </li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}
