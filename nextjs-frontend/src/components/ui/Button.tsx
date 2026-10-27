import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'
import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}

export default function Button({
  variant = 'primary', size = 'md', loading, icon, children, className, disabled, ...props
}: ButtonProps) {
  const base = 'inline-flex items-center justify-center gap-2 font-medium rounded-full transition-[transform,background-color,box-shadow,color] duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100'
  const variants = {
    primary:   'bg-ink text-canvas hover:bg-ink/85',
    secondary: 'bg-surface text-ink ring-1 ring-ink/15 hover:ring-ink/30',
    danger:    'bg-error-600 text-white hover:bg-error-700',
    ghost:     'text-ink-soft hover:bg-ink/[0.06] hover:text-ink',
    outline:   'text-accent ring-1 ring-accent/40 hover:bg-accent/10',
  }
  const sizes = { sm: 'h-8 px-3.5 text-xs', md: 'h-10 px-5 text-sm', lg: 'h-12 px-6 text-[15px]' }

  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={clsx(base, variants[variant], sizes[size], className)}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}
