import { clsx } from 'clsx'
import React from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export default function PageHeader({ title, subtitle, actions, className }: PageHeaderProps) {
  return (
    <div className={clsx('flex flex-wrap items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <h1 className="font-display text-[1.75rem] font-semibold leading-tight tracking-[-0.03em] text-ink">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-ink-mute">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}
