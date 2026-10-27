import Link from 'next/link'
import {
  ArrowRight, ArrowUpRight, Building2, Check, FileText, GitFork, KeyRound, Layers, Lock,
  Paperclip, RefreshCw, Scale, Send, Server, ShieldCheck, Star, UserCheck,
} from 'lucide-react'
import { GITHUB_URL } from '@/lib/site'
import SiteShell from './SiteShell'
import AgentConsole from './AgentConsole'
import CopyCommand from './CopyCommand'
import ProviderStrip from './ProviderStrip'
import StepsScroller from './StepsScroller'
import ValidatorLog from './ValidatorLog'
import { FAQ } from './content'

// ─── Small building blocks ────────────────────────────────────────────────────

function SectionHead({ eyebrow, title, lede, center = false, id }: { eyebrow: string; title: React.ReactNode; lede?: React.ReactNode; center?: boolean; id?: string }) {
  return (
    <div className={`site-reveal ${center ? 'mx-auto text-center' : ''} max-w-3xl`}>
      <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />{eyebrow}</p>
      <h2 id={id} className="site-h2 mt-5">{title}</h2>
      {lede && <p className={`site-lede mt-6 max-w-2xl ${center ? 'mx-auto' : ''}`}>{lede}</p>}
    </div>
  )
}

/** Paragraph whose words darken as it scrolls through the viewport (static where unsupported). */
function InkStatement({ parts }: { parts: { text: string; serif?: boolean }[] }) {
  return (
    <p className="font-display text-[clamp(1.65rem,3.4vw,2.85rem)] font-medium leading-[1.18] tracking-[-0.03em] text-balance">
      {parts.map((p, i) => (
        <span key={i} className={p.serif ? 'site-serif text-[1.08em]' : undefined}>
          {p.text.split(' ').map((w, j) => (
            <span key={j} className="site-ink-word">{w} </span>
          ))}
        </span>
      ))}
    </p>
  )
}

function BentoCard({ title, body, className = '', children, tags }: { title: string; body: string; className?: string; children?: React.ReactNode; tags?: string[] }) {
  return (
    <div className={`site-card site-reveal flex flex-col overflow-hidden ${className}`}>
      {children && <div className="relative flex-1 border-b bg-ink/[0.018] p-5 sm:p-6">{children}</div>}
      <div className="p-5 sm:p-6">
        <h3 className="font-display text-[17px] font-semibold tracking-[-0.015em]">{title}</h3>
        <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-mute">{body}</p>
        {tags && (
          <ul className="mt-4 flex flex-wrap gap-1.5">
            {tags.map(t => <li key={t} className="rounded-full px-2.5 py-1 font-mono text-[11.5px] text-ink-soft ring-1 ring-ink/10">{t}</li>)}
          </ul>
        )}
      </div>
    </div>
  )
}

// ─── Bento visuals ────────────────────────────────────────────────────────────

function TenantsVisual() {
  const tenants = [
    { n: 'Acme Dental', i: 'AD', plan: 'Pro', c: 'bg-[#e8f0ff] text-[#2747d8] dark:bg-[#1c2550] dark:text-[#9db0ff]' },
    { n: 'Northwind Legal', i: 'NL', plan: 'Business', c: 'bg-[#e9f7ee] text-[#17663a] dark:bg-[#123221] dark:text-[#7fdca4]' },
    { n: 'Bluebird Studio', i: 'BS', plan: 'Starter', c: 'bg-[#fff1e6] text-[#a4470d] dark:bg-[#3a2212] dark:text-[#ffb27a]' },
  ]
  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-2xl bg-surface p-2 ring-1 ring-ink/10 shadow-[0_16px_40px_-20px_rgb(0_0_0/0.25)]">
        <div className="px-3 pb-2 pt-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">Switch workspace</div>
        {tenants.map((t, idx) => (
          <div key={t.n} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 ${idx === 0 ? 'bg-ink/[0.05]' : ''}`}>
            <span className={`grid h-8 w-8 place-items-center rounded-lg font-display text-[12px] font-semibold ${t.c}`}>{t.i}</span>
            <span className="text-[14px] font-medium">{t.n}</span>
            <span className="ml-auto rounded-full px-2 py-0.5 font-mono text-[11px] text-ink-mute ring-1 ring-ink/10">{t.plan}</span>
            {idx === 0 && <Check size={15} className="text-accent" />}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-center gap-2 font-mono text-[11.5px] text-ink-mute">
        <Lock size={12} /> data, branding and billing isolated per tenant
      </div>
    </div>
  )
}

function IdentityVisual() {
  return (
    <div className="mx-auto max-w-[260px] text-center">
      <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">Two-factor code</div>
      <div className="mt-3 flex justify-center gap-1.5">
        {['4', '8', '2', '9', '1', ''].map((d, i) => (
          <span key={i} className={`grid h-11 w-9 place-items-center rounded-lg bg-surface font-mono text-lg ring-1 ${i === 5 ? 'ring-2 ring-accent' : 'ring-ink/10'}`}>
            {d || <span className="site-caret h-5 w-[2px] bg-accent" />}
          </span>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-1.5 text-[12.5px]">
        <span className="rounded-lg bg-surface py-2 ring-1 ring-ink/10">Single sign-on</span>
        <span className="rounded-lg bg-surface py-2 ring-1 ring-ink/10">Invite a team</span>
      </div>
    </div>
  )
}

function PermissionsVisual() {
  const rows = [['customers.view', [1, 1, 1]], ['customers.edit', [1, 1, 0]], ['customers.delete', [1, 0, 0]]] as const
  return (
    <table className="w-full font-mono text-[11.5px]">
      <thead>
        <tr className="text-ink-mute"><th className="pb-2 text-left font-normal">permission</th>{['Admin', 'Staff', 'Viewer'].map(r => <th key={r} className="pb-2 font-normal">{r}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map(([p, v]) => (
          <tr key={p} className="border-t border-ink/[0.07]">
            <td className="py-2 text-ink-soft">{p}</td>
            {v.map((on, i) => (
              <td key={i} className="py-2 text-center">
                {on ? <span className="inline-grid h-4 w-4 place-items-center rounded bg-accent text-white dark:text-[#0b0c10]"><Check size={10} strokeWidth={3.5} /></span> : <span className="inline-block h-4 w-4 rounded ring-1 ring-ink/15" />}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BillingVisual() {
  return (
    <div className="space-y-1.5">
      {[['Starter', '$0', false], ['Pro', '$29', true], ['Business', '$99', false]].map(([n, p, on]) => (
        <div key={n as string} className={`flex items-center justify-between rounded-xl px-3.5 py-2.5 text-[13.5px] ${on ? 'bg-surface ring-2 ring-accent' : 'bg-surface ring-1 ring-ink/10'}`}>
          <span className="font-medium">{n}</span>
          <span className="font-mono text-ink-soft">{p}<span className="text-ink-mute">/mo</span></span>
        </div>
      ))}
      <div className="flex gap-1.5 pt-1.5 font-mono text-[11px] text-ink-mute">
        <span className="rounded-md bg-ink/[0.06] px-1.5 py-0.5">Stripe</span>
        <span className="rounded-md bg-ink/[0.06] px-1.5 py-0.5">PayPal</span>
        <span className="rounded-md bg-ink/[0.06] px-1.5 py-0.5">feature paywall</span>
      </div>
    </div>
  )
}

function AuditVisual() {
  const rows = [
    ['09:41', 'maria', 'deleted customer #1182'],
    ['09:38', 'sam', 'invited jo@acme.co'],
    ['09:12', 'sam', 'changed role → Staff'],
    ['08:57', 'maria', 'enabled 2FA'],
  ]
  return (
    <ul className="space-y-1 font-mono text-[11.5px]">
      {rows.map(([t, who, what]) => (
        <li key={t} className="flex gap-2.5 rounded-md px-1.5 py-1">
          <span className="text-ink-mute">{t}</span>
          <span className="text-accent">{who}</span>
          <span className="truncate text-ink-soft">{what}</span>
        </li>
      ))}
    </ul>
  )
}

// ─── Assistants mock ──────────────────────────────────────────────────────────

function AssistantMock() {
  return (
    <div aria-hidden className="site-card grid overflow-hidden sm:grid-cols-[180px_1fr]">
      <div className="hidden border-r bg-ink/[0.02] p-3 sm:block">
        <div className="px-2 pb-2 pt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">Assistants</div>
        {[['Support triage', false], ['Contracts helper', true], ['Sales follow-ups', false], ['HR policies', false]].map(([n, on]) => (
          <div key={n as string} className={`rounded-lg px-2.5 py-2 text-[13px] ${on ? 'bg-surface font-medium text-ink ring-1 ring-ink/10' : 'text-ink-mute'}`}>{n}</div>
        ))}
        <div className="mt-2 rounded-lg border border-dashed px-2.5 py-2 text-[13px] text-ink-mute">+ New assistant</div>
      </div>
      <div className="flex min-h-[380px] flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-[14px] font-medium">Contracts helper</span>
          <span className="rounded-full bg-ink/[0.06] px-2 py-0.5 font-mono text-[11px] text-ink-mute">gemini</span>
        </div>
        <div className="flex-1 space-y-4 p-4 text-[13.5px] leading-relaxed">
          <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-canvas">
            Compare this agreement with our standard terms. What is different?
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-canvas/15 px-2 py-1 font-mono text-[11px]"><FileText size={12} /> acme-msa.pdf</div>
          </div>
          <div className="max-w-[92%] text-ink-soft">
            <p className="text-ink">Three clauses differ from your standard terms:</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              <li>Liability is capped at 6 months of fees (yours: 12).</li>
              <li>Payment is due in 60 days (yours: 30).</li>
              <li>There is no termination for convenience.</li>
            </ol>
            <div className="site-shimmer mt-3 h-3 w-2/3 rounded-full" />
          </div>
        </div>
        <div className="m-3 flex items-center gap-2 rounded-xl bg-ink/[0.04] px-3 py-2.5 text-[13px] text-ink-mute ring-1 ring-ink/10">
          <Paperclip size={15} /> Ask a follow-up…
          <span className="ml-auto grid h-7 w-7 place-items-center rounded-full bg-ink text-canvas"><Send size={13} /></span>
        </div>
      </div>
    </div>
  )
}

// ─── Comparison ───────────────────────────────────────────────────────────────

type Cell = 'yes' | 'no' | 'varies' | 'na' | string
const comparison: [string, Cell, Cell, Cell][] = [
  ['Sign-in, teams, roles and billing built in', 'yes', 'yes', 'varies'],
  ['Multi-tenant from day one', 'yes', 'varies', 'no'],
  ['AI builds new features for you', 'yes', 'no', 'yes'],
  ['Every AI change reviewed as a pull request', 'yes', 'na', 'varies'],
  ['Guardrails that keep AI out of core code', 'yes', 'na', 'no'],
  ['You own and host all of the code', 'yes', 'yes', 'varies'],
  ['Use any AI model with your own key', 'yes', 'na', 'no'],
  ['Price', 'Free, MIT', 'Paid licence', 'Monthly plan'],
]

function CompareCell({ v, primary }: { v: Cell; primary?: boolean }) {
  if (v === 'yes') return <span className={`inline-grid h-6 w-6 place-items-center rounded-full ${primary ? 'bg-accent text-white dark:text-[#0b0c10]' : 'bg-ink/[0.08] text-ink'}`}><Check size={13} strokeWidth={3} /><span className="sr-only">Yes</span></span>
  if (v === 'no') return <span className="text-ink-mute" aria-label="No">—</span>
  if (v === 'na') return <span className="text-[13px] text-ink-mute">n/a</span>
  if (v === 'varies') return <span className="text-[13px] text-ink-mute">Varies</span>
  return <span className={`text-[14px] ${primary ? 'font-semibold text-ink' : 'text-ink-soft'}`}>{v}</span>
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <SiteShell active="home">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div aria-hidden className="site-grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,black,transparent_75%)]" />
        <div aria-hidden className="pointer-events-none absolute left-1/2 top-[52%] h-[520px] w-[min(1100px,120vw)] -translate-x-1/2 rounded-[100%] bg-accent/[0.16] blur-[110px] dark:bg-accent/[0.12]" />

        <div className="site-container relative pb-20 pt-12 sm:pt-20 md:pb-28">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-2.5 rounded-full bg-surface py-1 pl-1 pr-3.5 text-[13px] text-ink-soft ring-1 ring-ink/10 transition hover:ring-ink/25"
          >
            <span className="rounded-full bg-ink px-2.5 py-0.5 font-mono text-[11px] font-medium text-canvas">MIT</span>
            Free and open source. Bring your own AI.
            <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
          </a>

          <h1 className="mt-8 max-w-[15ch] font-display text-[clamp(2.9rem,8vw,6.6rem)] font-semibold leading-[0.94] tracking-[-0.055em] text-balance">
            Describe what your business needs.{' '}
            <span className="site-serif text-accent">ffinn&nbsp;ships&nbsp;it.</span>
          </h1>

          <div className="mt-10 grid gap-8 md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:gap-14">
            <p className="site-lede max-w-xl md:text-[19px]">
              ffinn is a free, open-source foundation for business software. Sign-in, teams, roles, billing and admin are already
              built. On top sits an AI agent that turns plain-English requests into reviewed pull requests, staging deploys and
              production releases, on your cloud and with your AI keys.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row md:flex-col md:items-stretch lg:flex-row">
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-primary h-12 px-6">
                Get started free <ArrowRight size={16} />
              </a>
              <Link href="/how-it-works" className="site-btn-secondary h-12 px-6">See how it works</Link>
            </div>
          </div>

          <div className="relative mt-14 md:mt-20">
            <AgentConsole />
          </div>

          <div className="mt-8 flex flex-col items-center gap-3 text-center">
            <CopyCommand className="w-full max-w-[700px]" />
            <p className="text-[13px] text-ink-mute">One command for a working app on your machine. All you need is Git and Docker.</p>
          </div>
        </div>
      </section>

      {/* Providers */}
      <section aria-labelledby="providers-title" className="border-y bg-surface/60 py-10">
        <div className="site-container">
          <p id="providers-title" className="mb-6 text-center text-[13px] text-ink-mute">Works with the AI you already pay for, or models you run yourself</p>
          <ProviderStrip />
        </div>
      </section>

      {/* Statement */}
      <section className="site-container py-28 md:py-40">
        <div className="mx-auto max-w-5xl">
          <InkStatement
            parts={[
              { text: 'Every business app starts by rebuilding the same things: sign-in, teams, roles, billing, an admin console. Months go by before a customer sees what makes you different.' },
              { text: 'ffinn hands you that foundation on day one,', serif: true },
              { text: 'then builds the rest with you, one reviewed change at a time.' },
            ]}
          />
        </div>
      </section>

      {/* How it works */}
      <section id="how" aria-labelledby="how-title" className="scroll-mt-20 border-t py-24 md:py-32">
        <div className="site-container">
          <SectionHead
            id="how-title"
            eyebrow="How it works"
            title={<>From one sentence to production, <span className="text-ink-mute">with you signing off at every step.</span></>}
          />
          <div className="mt-8 lg:mt-0">
            <StepsScroller />
          </div>
          <div className="mt-12 lg:mt-4">
            <Link href="/how-it-works" className="group inline-flex items-center gap-2 text-[15px] font-medium text-ink">
              The full nine-step walkthrough <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      </section>

      {/* Foundation */}
      <section id="foundation" aria-labelledby="foundation-title" className="scroll-mt-20 border-t py-24 md:py-32">
        <div className="site-container">
          <SectionHead
            id="foundation-title"
            eyebrow="Already built"
            title={<>The parts every app needs, <span className="site-serif">done properly.</span></>}
            lede="These are the pieces that take months to get right and are dangerous to get wrong. In ffinn they are hand-written, tested, and protected from the AI agent, so new features always build on solid ground."
          />
          <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-6">
            <BentoCard className="lg:col-span-4" title="Multi-tenancy" body="Serve many customers from one deployment. Each tenant gets isolated data, its own branding and its own subscription.">
              <TenantsVisual />
            </BentoCard>
            <BentoCard className="lg:col-span-2" title="Identity" body="JWT sessions with refresh tokens, two-factor sign-in, single sign-on and team invitations.">
              <IdentityVisual />
            </BentoCard>
            <BentoCard className="lg:col-span-2" title="Roles and permissions" body="Fine-grained permissions grouped into roles, plus delegation and admin impersonation for support.">
              <PermissionsVisual />
            </BentoCard>
            <BentoCard className="lg:col-span-2" title="Billing and paywall" body="Plans and editions with Stripe or PayPal. Gate any feature by plan without writing billing code.">
              <BillingVisual />
            </BentoCard>
            <BentoCard className="md:col-span-2 lg:col-span-2" title="Audit trail" body="Who did what, and when, recorded for every sensitive action and searchable by admins.">
              <AuditVisual />
            </BentoCard>
            <BentoCard className="lg:col-span-3" title="Notifications" body="One service for every channel, configured per tenant." tags={['Email', 'SMS', 'Push', 'In-app', 'WebSockets']} />
            <BentoCard className="lg:col-span-3" title="Admin console" body="Everything your operations team needs on day one, without building a back office." tags={['Users', 'Roles', 'Tenants', 'Plans', 'Feature flags', 'Settings']} />
          </div>
        </div>
      </section>

      {/* Guardrails */}
      <section id="guardrails" aria-labelledby="guardrails-title" className="ink-scope scroll-mt-16 bg-canvas py-24 text-ink md:py-32">
        <div className="site-container grid items-center gap-14 lg:grid-cols-[1fr_1.05fr] lg:gap-20">
          <div>
            <SectionHead
              id="guardrails-title"
              eyebrow="Guardrails"
              title={<>AI that can&apos;t break <span className="site-serif text-accent">what already works.</span></>}
              lede="Generating code is easy. Trusting it is the hard part. ffinn checks every file against your architecture before anything is committed, and a person approves every release."
            />
            <ul className="mt-10 grid gap-x-8 gap-y-7 sm:grid-cols-2">
              {[
                { icon: Lock, t: 'Protected core', d: 'Security, configuration, infrastructure and shared components are off-limits. The agent cannot write to them.' },
                { icon: Layers, t: 'Layer rules', d: 'Routes call services and services own the logic. Shortcuts are caught before they reach your repository.' },
                { icon: Building2, t: 'Tenant-scoped data', d: 'Every new model carries a tenant ID, so one customer never sees another’s records.' },
                { icon: RefreshCw, t: 'Self-correcting', d: 'Violations go back to the model with a targeted fix. Up to three tries, then a clear explanation instead of a broken commit.' },
              ].map(({ icon: Icon, t, d }) => (
                <li key={t} className="site-reveal">
                  <Icon size={19} strokeWidth={1.75} className="text-accent" aria-hidden />
                  <h3 className="mt-3 text-[16px] font-semibold tracking-[-0.01em]">{t}</h3>
                  <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-mute">{d}</p>
                </li>
              ))}
            </ul>
            <div className="mt-10 flex items-center gap-3 rounded-2xl bg-ink/[0.05] p-4 ring-1 ring-ink/10">
              <UserCheck size={20} className="shrink-0 text-signal" aria-hidden />
              <p className="text-[14.5px] text-ink-soft"><span className="font-medium text-ink">You stay accountable.</span> Nothing reaches production without a pull request you have reviewed and a release you have approved.</p>
            </div>
          </div>
          <div className="site-reveal">
            <ValidatorLog />
          </div>
        </div>
      </section>

      {/* Assistants */}
      <section aria-labelledby="assistants-title" className="py-24 md:py-32">
        <div className="site-container grid items-center gap-14 lg:grid-cols-[1.1fr_1fr] lg:gap-20">
          <div className="site-reveal order-2 lg:order-1">
            <AssistantMock />
          </div>
          <div className="order-1 lg:order-2">
            <SectionHead
              id="assistants-title"
              eyebrow="AI assistants"
              title={<>Assistants for the rest of <span className="site-serif">your team.</span></>}
              lede="The same app can host chat assistants for everyday work, each with its own instructions, model and files. Think of the big chat apps, but inside your product and under your permissions."
            />
            <ul className="mt-8 grid gap-3 sm:grid-cols-2">
              {['As many assistants as you need', 'Upload documents and images', 'Streaming replies, saved history', 'A different model for each one'].map(p => (
                <li key={p} className="flex items-start gap-2.5 text-[15px] text-ink-soft">
                  <Check size={16} className="mt-[3px] shrink-0 text-accent" strokeWidth={2.5} />{p}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Ownership */}
      <section id="open-source" aria-labelledby="own-title" className="scroll-mt-20 border-t py-24 md:py-32">
        <div className="site-container">
          <SectionHead
            id="own-title"
            eyebrow="No lock-in"
            title={<>Yours. Every line, every key, <span className="site-serif">every server.</span></>}
            center
          />
          <div className="mt-14 grid gap-4 md:grid-cols-3">
            {[
              { icon: Scale, k: 'Your code', t: 'MIT licensed, top to bottom.', d: 'Read every line, change anything, sell what you build. No paid tier and no feature held back.' },
              { icon: KeyRound, k: 'Your keys', t: 'Pay your AI provider directly.', d: 'Connect OpenAI, Claude, Gemini, Azure OpenAI, GitHub Models, Ollama or any compatible server. Keys are encrypted at rest.' },
              { icon: Server, k: 'Your cloud', t: 'Runs anywhere Docker runs.', d: 'Docker Compose locally, GitHub Actions for staging and production, and a reference AWS setup that runs ffinn.ca.' },
            ].map(({ icon: Icon, k, t, d }) => (
              <div key={k} className="site-card site-reveal p-6 sm:p-7">
                <div className="flex items-center justify-between">
                  <span className="site-eyebrow">{k}</span>
                  <Icon size={19} strokeWidth={1.75} className="text-ink-mute" aria-hidden />
                </div>
                <h3 className="mt-10 font-display text-[22px] font-semibold leading-tight tracking-[-0.025em]">{t}</h3>
                <p className="mt-3 text-[14.5px] leading-relaxed text-ink-mute">{d}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-secondary"><Star size={16} /> Star the repository</a>
            <a href={`${GITHUB_URL}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noopener noreferrer" className="site-btn-secondary"><GitFork size={16} /> Contributing guide</a>
            <a href={`${GITHUB_URL}/blob/main/SECURITY.md`} target="_blank" rel="noopener noreferrer" className="site-btn-secondary"><ShieldCheck size={16} /> Security policy</a>
          </div>
        </div>
      </section>

      {/* Comparison */}
      <section aria-labelledby="compare-title" className="border-t py-24 md:py-32">
        <div className="site-container">
          <SectionHead id="compare-title" eyebrow="Compare" title={<>The foundation of a starter kit. <span className="text-ink-mute">The speed of an AI builder.</span></>} />
          <div className="site-card site-reveal mt-12 overflow-x-auto">
            <table className="w-full min-w-[680px] text-left">
              <caption className="sr-only">ffinn compared with paid starter kits and hosted AI app builders</caption>
              <thead>
                <tr className="border-b">
                  <th scope="col" className="w-[44%] px-6 py-5 font-normal" />
                  <th scope="col" className="bg-accent/[0.06] px-6 py-5 text-center">
                    <span className="font-display text-[17px] font-semibold tracking-[-0.02em]">ffinn</span>
                  </th>
                  <th scope="col" className="px-6 py-5 text-center text-[14px] font-medium text-ink-soft">Paid starter kits</th>
                  <th scope="col" className="px-6 py-5 text-center text-[14px] font-medium text-ink-soft">Hosted AI app builders</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map(([label, a, b, c]) => (
                  <tr key={label} className="border-b last:border-b-0">
                    <th scope="row" className="px-6 py-4 text-[14.5px] font-normal text-ink">{label}</th>
                    <td className="bg-accent/[0.06] px-6 py-4 text-center"><CompareCell v={a} primary /></td>
                    <td className="px-6 py-4 text-center"><CompareCell v={b} /></td>
                    <td className="px-6 py-4 text-center"><CompareCell v={c} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-[13px] text-ink-mute">Typical of each category. Individual products vary.</p>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" aria-labelledby="faq-title" className="scroll-mt-20 border-t py-24 md:py-32">
        <div className="site-container grid gap-12 lg:grid-cols-[1fr_1.6fr] lg:gap-20">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHead id="faq-title" eyebrow="FAQ" title="Questions, answered." lede={<>Something missing? <a className="text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-ink" href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer">Ask on GitHub</a> or email <a className="text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-ink" href="mailto:info@ffinn.ca">info@ffinn.ca</a>.</>} />
          </div>
          <div className="divide-y border-y">
            {FAQ.map((f, i) => (
              <details key={f.q} className="group py-1" open={i === 0}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-5 text-[17px] font-medium tracking-[-0.01em] [&::-webkit-details-marker]:hidden">
                  {f.q}
                  <span className="relative grid h-7 w-7 shrink-0 place-items-center rounded-full ring-1 ring-ink/15 transition-transform duration-300 group-open:rotate-45" aria-hidden>
                    <span className="absolute h-px w-3 bg-ink" /><span className="absolute h-3 w-px bg-ink" />
                  </span>
                </summary>
                <p className="max-w-2xl pb-6 pr-10 text-[15.5px] leading-relaxed text-ink-soft">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative overflow-hidden border-t">
        <div aria-hidden className="site-grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_60%_70%_at_50%_100%,black,transparent_70%)]" />
        <div className="site-container relative py-28 text-center md:py-40">
          <h2 className="site-reveal mx-auto max-w-4xl font-display text-[clamp(2.5rem,6.4vw,5.4rem)] font-semibold leading-[0.98] tracking-[-0.05em] text-balance">
            Your next feature is <span className="site-serif text-accent">one sentence</span> away.
          </h2>
          <p className="site-lede mx-auto mt-6 max-w-xl">Clone it, run it, and describe the first thing your business needs. It is free, today and always.</p>
          <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-primary h-12 px-7">Get started free <ArrowUpRight size={16} /></a>
            <Link href="/docs" className="site-btn-secondary h-12 px-7">Read the docs</Link>
          </div>
          <div className="mx-auto mt-8 flex max-w-[700px] justify-center">
            <CopyCommand className="w-full" />
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
