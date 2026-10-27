import Link from 'next/link'
import {
  AlertTriangle, ArrowRight, ArrowUpRight, Bot, Check, Code2, Eye, FlaskConical, GitBranch,
  GitPullRequest, KeyRound, Lock, RefreshCw, Rocket, Shield, Workflow,
} from 'lucide-react'
import SiteShell from '@/components/marketing/SiteShell'
import PhaseNav from '@/components/marketing/PhaseNav'
import ValidatorLog from '@/components/marketing/ValidatorLog'
import CopyCommand from '@/components/marketing/CopyCommand'
import { AI_PROVIDERS } from '@/components/marketing/content'
import { GITHUB_URL } from '@/lib/site'

// ─── Data ─────────────────────────────────────────────────────────────────────

type Step = {
  n: string
  phase: string
  icon: React.ElementType
  title: string
  body: string
  details: string[]
  aside: { label: string; items: string[]; mono?: boolean }
}

const steps: Step[] = [
  {
    n: '01', phase: 'Setup', icon: KeyRound,
    title: 'Connect your AI provider',
    body: 'Open AI Agent → Providers and add a key for the model you want to use. ffinn tests the connection and lists the available models before you save.',
    details: [
      'Keys are encrypted before they are stored in your database',
      'Pay your provider directly, with no markup in between',
      'Switch providers or models at any time',
    ],
    aside: { label: 'Supported providers', items: [...AI_PROVIDERS] },
  },
  {
    n: '02', phase: 'Setup', icon: GitBranch,
    title: 'Connect your repository',
    body: 'Link the GitHub repository that holds your copy of ffinn from AI Agent → Setup Wizard. The agent reads it to learn your existing models, services and screens before it writes a line.',
    details: [
      'The access token is encrypted before it is stored',
      'ffinn adds the staging and release workflows and the callback secret to the repository for you',
      'Generated work lands on its own branches, named with the ai-agent/ prefix by default',
    ],
    aside: { label: 'Configured once', items: ['Repository and default branch', 'GitHub access token', 'Staging workflow (added for you)', 'Release workflow (added for you)'] },
  },
  {
    n: '03', phase: 'Generate', icon: Bot,
    title: 'Describe the feature',
    body: 'Write what you need in plain language. You do not need to know how the codebase is organised; the agent maps your request onto it.',
    details: [
      'Go as broad as “add a booking system” or as precise as you like',
      'Name the fields, relationships and business rules that matter to you',
      'The request is mapped to each layer: model, service, API and page',
    ],
    aside: {
      label: 'Example requests',
      items: [
        '“Create a Customer list with name, email and phone”',
        '“Build a product catalogue with categories and search”',
        '“Add a dashboard widget for monthly revenue”',
        '“Generate invoices with PDF export”',
      ],
    },
  },
  {
    n: '04', phase: 'Generate', icon: Code2,
    title: 'The agent reads, then writes',
    body: 'Before generating, the agent pulls in the neighbouring code your feature will touch. The result fits your project from the first draft.',
    details: [
      'Model, schema, service, API route and page are generated in one pass',
      'Services are injected with FastAPI dependencies; routes stay thin',
      'Pages use the shared API client and TypeScript types',
      'New features are wired into navigation, permissions and the API router',
    ],
    aside: {
      label: 'Files typically generated',
      mono: true,
      items: [
        'app/domain/models/booking.py',
        'app/schemas/booking_schemas.py',
        'app/services/booking_service.py',
        'app/api/bookings.py',
        'src/app/app/features/bookings/page.tsx',
      ],
    },
  },
  {
    n: '05', phase: 'Validate', icon: AlertTriangle,
    title: 'Architecture check',
    body: 'Every generated file is validated before it is committed. If something breaks the rules, the agent gets a focused correction prompt explaining each problem and tries again.',
    details: [
      'Every new domain model must be tenant-scoped',
      'Routes may not query the database or open sessions directly',
      'Services may not depend on web-layer types',
      'Protected core files are stripped from the output',
    ],
    aside: {
      label: 'Self-correction loop',
      items: ['Generate the full change', 'Validate against the rules', 'Violation found: retry with a targeted fix', 'Up to three attempts, then a clear explanation'],
    },
  },
  {
    n: '06', phase: 'Review', icon: Eye,
    title: 'Review the pull request',
    body: 'The change is committed to a new branch and opened as a pull request. Read the diff in GitHub with your normal review process, then approve, request changes or close it.',
    details: [
      'One request becomes one branch and one pull request',
      'The description summarises what was built and which files changed',
      'Security, configuration and infrastructure files are never overwritten',
    ],
    aside: { label: 'Branch naming', mono: true, items: ['ai-agent/add-booking-system', 'ai-agent/customer-list', 'ai-agent/revenue-widget'] },
  },
  {
    n: '07', phase: 'Stage', icon: FlaskConical,
    title: 'Deploy to staging',
    body: 'Trigger a staging deploy from the AI Agent dashboard. ffinn runs your GitHub Actions workflow and streams progress back to the page as it happens.',
    details: [
      'Runs the staging workflow that ffinn added to your repository in step 2',
      'Live status over WebSockets, with no page refresh',
      'Database migrations run automatically when the new version starts',
    ],
    aside: { label: 'Staging checklist', items: ['Branch deployed to staging', 'Workflow run started', 'Migrations applied', 'Staging link returned to the dashboard'] },
  },
  {
    n: '08', phase: 'Test', icon: Workflow,
    title: 'Try it, refine it',
    body: 'Use the feature in staging with realistic data. If it needs adjusting, write a follow-up request; the agent reads its earlier work and makes a focused change on top.',
    details: [
      'Run your own end-to-end checks against the staging link',
      'Follow-up requests build on the existing generated files',
      'Each change is its own small, reviewable pull request',
    ],
    aside: {
      label: 'Follow-up requests',
      items: ['“Add an optional notes field to bookings”', '“Only admins can cancel a booking”', '“Paginate the bookings list”'],
    },
  },
  {
    n: '09', phase: 'Ship', icon: Rocket,
    title: 'Release to production',
    body: 'When staging looks right, release from the dashboard. The same pipeline and the same build go to production. If something is off, revert the generation.',
    details: [
      'Production runs the release workflow added in step 2',
      'Deployment status streams back live, as it did for staging',
      'Every generation is kept with its request, files, branch, pull request and deploy history',
    ],
    aside: { label: 'Kept for every generation', items: ['The original request', 'Provider and model used', 'Files changed', 'Branch, pull request and deploy links'] },
  },
]

const phases = Array.from(new Set(steps.map(s => s.phase))).map(label => ({
  id: label.toLowerCase(),
  label,
  first: `step-${steps.find(s => s.phase === label)!.n}`,
}))

const iterations = [
  { icon: RefreshCw, title: 'Add a field', prompt: '“Add an optional notes field to Customer and show it on the form”', result: 'Model, schema and form updated together' },
  { icon: Shield, title: 'Tighten permissions', prompt: '“Only admins can delete a customer”', result: 'Route permission updated, role mapping seeded' },
  { icon: Code2, title: 'Add an endpoint', prompt: '“Export customers to CSV, filtered by date range”', result: 'New route, service query and streamed CSV response' },
  { icon: GitPullRequest, title: 'Connect features', prompt: '“Email new customers a welcome message”', result: 'Notification call added to the customer service' },
]

const layers = [
  { label: 'Your features', sub: 'Written by the agent from your requests: models, services, APIs and pages', tone: 'accent' },
  { label: 'Architecture check', sub: 'Every generated file is validated before it is committed', tone: 'check' },
  { label: 'ffinn core', sub: 'Auth · tenancy · roles · billing · notifications · audit', tone: 'core' },
  { label: 'Infrastructure', sub: 'PostgreSQL · SQLAlchemy · FastAPI · Next.js · Docker', tone: 'base' },
] as const

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HowItWorksPage() {
  return (
    <SiteShell active="how">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div aria-hidden className="site-grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_70%_70%_at_50%_0%,black,transparent_75%)]" />
        <div className="site-container relative pb-16 pt-14 sm:pt-20 md:pb-24">
          <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />How it works</p>
          <h1 className="mt-6 max-w-[16ch] font-display text-[clamp(2.8rem,7.4vw,6rem)] font-semibold leading-[0.95] tracking-[-0.05em] text-balance">
            From one sentence to <span className="site-serif text-accent">production.</span>
          </h1>
          <p className="site-lede mt-8 max-w-2xl md:text-[19px]">
            ffinn starts you on a solid, protected core. The build agent adds the features your business needs on top, following
            your architecture, checking its own work, and stopping for your review before anything goes live.
          </p>
          <dl className="mt-14 grid max-w-3xl grid-cols-2 gap-px overflow-hidden rounded-2xl bg-ink/10 ring-1 ring-ink/10 sm:grid-cols-4">
            {[
              ['9', 'steps from request to release'],
              ['7', 'AI provider options'],
              ['3', 'self-correction attempts'],
              ['0', 'core files the agent can write'],
            ].map(([v, l]) => (
              <div key={l} className="bg-canvas p-5">
                <dt className="sr-only">{l}</dt>
                <dd className="font-display text-[2.4rem] font-semibold leading-none tracking-[-0.04em]">{v}</dd>
                <dd className="mt-2 text-[13px] leading-snug text-ink-mute">{l}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Foundation */}
      <section aria-labelledby="foundation-title" className="border-t py-24 md:py-28">
        <div className="site-container grid items-center gap-14 lg:grid-cols-2 lg:gap-20">
          <div className="site-reveal">
            <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />The foundation</p>
            <h2 id="foundation-title" className="site-h2 mt-5">Start on a core the AI <span className="site-serif">can&apos;t touch.</span></h2>
            <p className="site-lede mt-6">
              Before the agent writes anything, ffinn already ships what every application needs and nobody wants to build twice.
              Those modules are protected: the agent can read them, but it can never change them.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-mute">
              That is intentional. Authentication, billing and permissions are the riskiest parts of any product. They stay hand-written,
              reviewed and under your version control.
            </p>
          </div>
          <div className="site-reveal space-y-2" role="list" aria-label="Layered architecture">
            {layers.map(l => (
              <div
                key={l.label}
                role="listitem"
                className={`flex items-center justify-between gap-4 rounded-2xl px-5 py-4 ${
                  l.tone === 'accent' ? 'bg-accent text-white dark:text-[#0b0c10]'
                    : l.tone === 'check' ? 'border border-dashed border-ink/25 bg-transparent'
                    : l.tone === 'core' ? 'bg-ink text-canvas'
                    : 'bg-surface ring-1 ring-ink/10'
                }`}
              >
                <div>
                  <div className="font-display text-[16px] font-semibold tracking-[-0.01em]">{l.label}</div>
                  <div className={`mt-0.5 text-[13px] ${l.tone === 'accent' || l.tone === 'core' ? 'opacity-75' : 'text-ink-mute'}`}>{l.sub}</div>
                </div>
                {l.tone === 'core' && <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-canvas/15 px-2.5 py-1 font-mono text-[11px]"><Lock size={11} /> protected</span>}
                {l.tone === 'check' && <span className="shrink-0 font-mono text-[11px] text-ink-mute">↕ validates</span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Walkthrough */}
      <section aria-labelledby="steps-title" className="border-t">
        <div className="site-container pb-6 pt-24 md:pt-28">
          <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />Step by step</p>
          <h2 id="steps-title" className="site-h2 mt-5 max-w-3xl">Nine steps. <span className="text-ink-mute">You approve the ones that matter.</span></h2>
        </div>
        <PhaseNav phases={phases} />
        <ol className="site-container py-10 md:py-16">
          {steps.map((s, i) => (
            <li
              key={s.n}
              id={`step-${s.n}`}
              data-phase={s.phase.toLowerCase()}
              className="relative grid scroll-mt-32 gap-6 py-10 md:grid-cols-[120px_1fr] md:gap-10 lg:grid-cols-[120px_1fr_320px] lg:gap-14"
            >
              {/* Rail */}
              <div className="relative">
                <div className="flex items-center gap-3 md:block">
                  <div className="font-display text-[44px] font-semibold leading-none tracking-[-0.05em] text-ink/20">{s.n}</div>
                  <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent md:mt-3">{s.phase}</div>
                </div>
                {i < steps.length - 1 && <span aria-hidden className="absolute left-[22px] top-24 hidden h-[calc(100%+2.5rem)] w-px bg-ink/10 md:block" />}
              </div>

              <div className="site-reveal">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink/[0.05] ring-1 ring-ink/10"><s.icon size={18} strokeWidth={1.75} /></span>
                  <h3 className="font-display text-[clamp(1.5rem,2.4vw,1.9rem)] font-semibold tracking-[-0.03em]">{s.title}</h3>
                </div>
                <p className="mt-4 max-w-xl text-[16px] leading-relaxed text-ink-soft">{s.body}</p>
                <ul className="mt-5 space-y-2.5">
                  {s.details.map(d => (
                    <li key={d} className="flex items-start gap-2.5 text-[14.5px] leading-relaxed text-ink-soft">
                      <Check size={15} strokeWidth={2.5} className="mt-[3px] shrink-0 text-accent" />{d}
                    </li>
                  ))}
                </ul>
              </div>

              <aside className="site-reveal self-start rounded-2xl bg-surface p-5 ring-1 ring-ink/10 md:col-start-2 lg:col-start-auto">
                <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">{s.aside.label}</p>
                <ul className={`mt-3 space-y-2 ${s.aside.mono ? 'font-mono text-[12px]' : 'text-[13.5px]'}`}>
                  {s.aside.items.map(item => (
                    <li key={item} className="flex items-start gap-2 leading-relaxed text-ink-soft">
                      <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink/30" aria-hidden />
                      <span className="min-w-0 break-words">{item}</span>
                    </li>
                  ))}
                </ul>
              </aside>
            </li>
          ))}
        </ol>
      </section>

      {/* Iteration */}
      <section aria-labelledby="iterate-title" className="border-t py-24 md:py-28">
        <div className="site-container">
          <div className="site-reveal max-w-3xl">
            <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />Iteration</p>
            <h2 id="iterate-title" className="site-h2 mt-5">Requirements change. <span className="site-serif">So do your requests.</span></h2>
            <p className="site-lede mt-6">You never regenerate from scratch. Each follow-up reads the code that is already there and applies a small, reviewable change.</p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-2">
            {iterations.map(it => (
              <div key={it.title} className="site-card site-reveal p-6">
                <div className="flex items-center gap-2.5">
                  <it.icon size={17} strokeWidth={1.75} className="text-accent" />
                  <h3 className="text-[16px] font-semibold tracking-[-0.01em]">{it.title}</h3>
                </div>
                <p className="mt-4 rounded-xl bg-ink/[0.04] px-4 py-3 font-mono text-[13px] leading-relaxed text-ink">{it.prompt}</p>
                <p className="mt-4 flex items-start gap-2 text-[14px] text-ink-mute"><ArrowRight size={14} className="mt-[3px] shrink-0" />{it.result}</p>
              </div>
            ))}
          </div>
          <ol className="site-reveal mt-10 flex flex-wrap items-center gap-2 text-[13.5px]" aria-label="Iteration loop">
            {['Request', 'Read existing code', 'Generate change', 'Check architecture', 'Pull request', 'Merge'].map((l, i, a) => (
              <li key={l} className="flex items-center gap-2">
                <span className="rounded-full bg-surface px-3.5 py-1.5 ring-1 ring-ink/10">{l}</span>
                {i < a.length - 1 && <ArrowRight size={14} className="text-ink-mute" aria-hidden />}
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Guardrails */}
      <section aria-labelledby="guard-title" className="ink-scope bg-canvas py-24 text-ink md:py-28">
        <div className="site-container grid items-center gap-14 lg:grid-cols-2 lg:gap-20">
          <div className="site-reveal">
            <p className="site-eyebrow"><span className="h-px w-6 bg-ink/30" aria-hidden />Guardrails</p>
            <h2 id="guard-title" className="site-h2 mt-5">The agent can&apos;t break <span className="site-serif text-accent">your architecture.</span></h2>
            <p className="site-lede mt-6">Rules are enforced in code, not left to the prompt. A violation triggers a targeted correction, not a broken commit.</p>
            <ul className="mt-8 space-y-4">
              {[
                ['Protected core files', 'Security, configuration, infrastructure and shared components are on a deny-list.'],
                ['Layer boundaries', 'Routes call services; services own the logic. Shortcuts are rejected.'],
                ['Tenant isolation', 'Every new model is tenant-scoped, so customer data stays separate.'],
                ['Bounded edits', 'Navigation, permissions and the API router are updated through controlled merge points only.'],
              ].map(([t, d]) => (
                <li key={t} className="flex gap-3">
                  <Check size={16} strokeWidth={2.5} className="mt-1 shrink-0 text-signal" />
                  <p className="text-[15px] leading-relaxed text-ink-mute"><span className="font-medium text-ink">{t}.</span> {d}</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="site-reveal"><ValidatorLog /></div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden">
        <div aria-hidden className="site-grid-bg pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_60%_70%_at_50%_100%,black,transparent_70%)]" />
        <div className="site-container relative py-28 text-center md:py-36">
          <h2 className="site-reveal mx-auto max-w-3xl font-display text-[clamp(2.4rem,5.6vw,4.6rem)] font-semibold leading-[0.98] tracking-[-0.05em] text-balance">
            See it build <span className="site-serif text-accent">your</span> first feature.
          </h2>
          <p className="site-lede mx-auto mt-6 max-w-xl">Free and MIT licensed. Bring your own AI key, run it on your own machine, and keep everything it writes.</p>
          <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="site-btn-primary h-12 px-7">Get started free <ArrowUpRight size={16} /></a>
            <Link href="/docs" className="site-btn-secondary h-12 px-7">Read the docs</Link>
          </div>
          <div className="mx-auto mt-8 flex max-w-[700px] justify-center"><CopyCommand className="w-full" /></div>
        </div>
      </section>
    </SiteShell>
  )
}
