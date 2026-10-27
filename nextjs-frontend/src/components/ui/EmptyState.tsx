import React from 'react'
import { clsx } from 'clsx'

export default function EmptyState({
  icon, title, description, action, className,
}: { icon?: React.ReactNode; title: string; description?: string; action?: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('flex flex-col items-center justify-center py-16 text-center', className)}>
      {icon && <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-ink/[0.05] text-ink-mute">{icon}</div>}
      <h3 className="font-display text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
      {description && <p className="mt-1.5 text-sm text-ink-mute max-w-sm text-pretty">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
