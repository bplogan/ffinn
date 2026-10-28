'use client'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { clsx } from 'clsx'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
  footer?: React.ReactNode
}

export default function Modal({ open, onClose, title, children, size = 'md', footer }: ModalProps) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  const sizes = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }

  // Rendered into <body> so the page around it can't shift the overlay
  // (a parent's space-y-* margin used to leave a gap at the top). The `.site`
  // wrapper brings the theme tokens along; it has no size, so it paints nothing.
  return createPortal(
    <div className="site">
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <div className={clsx('relative w-full bg-surface text-ink rounded-[22px] ring-1 ring-ink/10 shadow-[0_30px_80px_-30px_rgb(0_0_0/0.5)] flex flex-col max-h-[90vh]', sizes[size])}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-display text-base font-semibold tracking-[-0.01em] text-ink">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-full text-ink-mute hover:bg-ink/[0.06] hover:text-ink transition-colors">
            <X size={16} />
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
        {/* Footer */}
        {footer && (
          <div className="px-6 py-4 border-t flex justify-end gap-3">{footer}</div>
        )}
      </div>
    </div>
    </div>,
    document.body,
  )
}
