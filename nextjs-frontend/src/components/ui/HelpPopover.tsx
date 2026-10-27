'use client'

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { HelpCircle } from 'lucide-react'
import { clsx } from 'clsx'

interface HelpPopoverProps {
  /** Accessible name for the trigger button */
  label: string
  title: string
  children: ReactNode
  size?: number
  className?: string
  align?: 'left' | 'right'
}

export default function HelpPopover({
  label,
  title,
  children,
  size = 16,
  className,
  align = 'right',
}: HelpPopoverProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className={clsx('relative inline-flex', className)}>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(v => !v)}
        className="p-1 rounded-md text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <HelpCircle size={size} />
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label={title}
          className={clsx(
            'absolute top-full mt-2 z-30 w-72 rounded-xl border border-gray-200 dark:border-gray-700',
            'bg-white dark:bg-gray-800 shadow-lg p-4 text-sm',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          <p className="font-semibold text-gray-900 dark:text-white mb-2">{title}</p>
          <div className="text-gray-600 dark:text-gray-300 space-y-2 leading-relaxed">{children}</div>
        </div>
      )}
    </div>
  )
}
