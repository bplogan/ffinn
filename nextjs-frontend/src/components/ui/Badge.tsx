import { clsx } from 'clsx'

export type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'gray'

export default function Badge({ variant = 'gray', children, className }: { variant?: BadgeVariant; children: React.ReactNode; className?: string }) {
  const variants: Record<BadgeVariant, string> = {
    success: 'bg-success-50 text-success-700 ring-1 ring-success-600/15 dark:bg-success-900/20 dark:text-success-400 dark:ring-success-400/20',
    error:   'bg-error-50 text-error-700 ring-1 ring-error-600/15 dark:bg-error-900/20 dark:text-error-400 dark:ring-error-400/20',
    warning: 'bg-warning-50 text-warning-700 ring-1 ring-warning-600/15 dark:bg-warning-900/20 dark:text-warning-400 dark:ring-warning-400/20',
    info:    'bg-accent/10 text-accent ring-1 ring-accent/20',
    gray:    'bg-ink/[0.06] text-ink-soft ring-1 ring-ink/10',
  }
  return (
    <span className={clsx('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', variants[variant], className)}>
      {children}
    </span>
  )
}
