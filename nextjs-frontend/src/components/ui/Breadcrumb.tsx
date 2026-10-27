import Link from 'next/link'
import { ChevronRight, Home } from 'lucide-react'

interface Crumb { label: string; href?: string }

export default function Breadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-ink-mute">
      <Link href="/app/dashboard" className="hover:text-ink transition-colors">
        <Home size={14} />
      </Link>
      {crumbs.map((c, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <ChevronRight size={13} />
          {c.href && i < crumbs.length - 1
            ? <Link href={c.href} className="hover:text-ink transition-colors">{c.label}</Link>
            : <span className="text-ink font-medium">{c.label}</span>
          }
        </span>
      ))}
    </nav>
  )
}
