/** Terminal-style output of the architecture check, with one self-corrected violation. */

type Line = { mark: string; tone: 'ok' | 'bad' | 'warn' | 'info' | 'dim'; text: string; sub?: string }

const lines: Line[] = [
  { mark: '›', tone: 'dim', text: 'ffinn check ai-agent/online-booking' },
  { mark: '✓', tone: 'ok', text: 'models/booking.py', sub: 'tenant-scoped · SQLAlchemy 2.0 Mapped[]' },
  { mark: '✓', tone: 'ok', text: 'services/booking_service.py', sub: 'no web-layer imports' },
  { mark: '✓', tone: 'ok', text: 'schemas/booking_schemas.py', sub: 'Pydantic v2' },
  { mark: '✗', tone: 'bad', text: 'api/bookings.py', sub: 'direct database query in route' },
  { mark: '↻', tone: 'warn', text: 'Sending a targeted fix to the model', sub: 'attempt 2 of 3' },
  { mark: '✓', tone: 'ok', text: 'api/bookings.py', sub: 'logic moved to BookingService' },
  { mark: '✓', tone: 'ok', text: '6 of 6 files pass', sub: '0 protected files touched' },
  { mark: '→', tone: 'info', text: 'Pull request #48 opened for your review' },
]

const tone = {
  ok: 'text-signal',
  bad: 'text-[#ff6b6b]',
  warn: 'text-caution',
  info: 'text-accent',
  dim: 'text-ink-mute',
}

export default function ValidatorLog() {
  return (
    <div className="ink-scope overflow-hidden rounded-[20px] bg-surface text-ink ring-1 ring-white/10 shadow-[0_40px_80px_-40px_rgb(0_0_0/0.6)]">
      <div className="flex items-center justify-between border-b px-5 py-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">
        <span>Architecture check</span>
        <span className="inline-flex items-center gap-1.5 normal-case tracking-normal text-signal"><span className="h-1.5 w-1.5 rounded-full bg-signal" />passed</span>
      </div>
      <ol className="space-y-[3px] p-5 font-mono text-[12.5px] leading-6">
        {lines.map((l, i) => (
          <li key={i} className={`site-reveal flex gap-3 ${l.tone === 'warn' ? '-mx-2 rounded-md bg-caution/10 px-2' : ''}`}>
            <span className={`w-3 shrink-0 text-center ${tone[l.tone]}`} aria-hidden>{l.mark}</span>
            <span className="min-w-0">
              <span className={l.tone === 'dim' ? 'text-ink-mute' : 'text-ink'}>{l.text}</span>
              {l.sub && <span className={l.tone === 'bad' ? 'text-[#ff6b6b]' : 'text-ink-mute'}> · {l.sub}</span>}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
