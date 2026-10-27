'use client'
import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { CLONE_COMMAND } from './content'

/** One-line install command with a copy button. */
export default function CopyCommand({ className = '' }: { className?: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(CLONE_COMMAND)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      // Clipboard can be blocked (insecure origin, permissions); the command stays selectable.
    }
  }

  return (
    <div className={`group flex max-w-full items-center gap-1 rounded-full bg-surface py-1 pl-4 pr-1 ring-1 ring-ink/10 ${className}`}>
      <code className="min-w-0 flex-1 overflow-x-auto text-left whitespace-nowrap font-mono text-[12.5px] text-ink-soft [scrollbar-width:none]">
        <span className="select-none text-ink-mute">$ </span>{CLONE_COMMAND}
      </code>
      <button
        type="button"
        onClick={copy}
        className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-soft transition-colors hover:bg-ink/[0.07] hover:text-ink"
        aria-label={copied ? 'Copied' : 'Copy install command'}
      >
        {copied ? <Check size={15} className="text-signal" /> : <Copy size={15} />}
      </button>
      <span className="sr-only" aria-live="polite">{copied ? 'Command copied to clipboard' : ''}</span>
    </div>
  )
}
