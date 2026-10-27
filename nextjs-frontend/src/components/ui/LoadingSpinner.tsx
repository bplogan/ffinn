import { Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

interface LoadingSpinnerProps { size?: 'sm' | 'md' | 'lg'; className?: string; label?: string; fullPage?: boolean }

export default function LoadingSpinner({ size = 'md', className, label, fullPage }: LoadingSpinnerProps) {
  const sizes = { sm: 16, md: 24, lg: 36 }
  const spinner = <Loader2 size={sizes[size]} className={clsx('animate-spin motion-reduce:animate-none text-accent', className)} />
  if (fullPage) return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
      {spinner}
      {label && <p className="text-sm text-ink-mute">{label}</p>}
    </div>
  )
  return (
    <div className="flex items-center justify-center gap-2">
      {spinner}
      {label && <span className="text-sm text-ink-mute">{label}</span>}
    </div>
  )
}
