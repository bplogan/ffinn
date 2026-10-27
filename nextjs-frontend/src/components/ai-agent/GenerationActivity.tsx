'use client'

import { useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import type { GenerationProgressEvent } from '@/types'

interface GenerationActivityProps {
  events: GenerationProgressEvent[]
  collapsed?: boolean
}

/** Plain-language activity feed — hides raw technical noise where possible */
function friendlyMessage(message: string): string {
  const replacements: [RegExp, string][] = [
    [/^Pipeline started/i, 'Started working on your request'],
    [/^Prompt optimized/i, 'Refined your description for better results'],
    [/^Calling .* provider/i, 'Connecting to AI…'],
    [/^Generation attempt \d+/i, 'Writing code (another attempt)'],
    [/^Validation passed/i, 'Quality check passed'],
    [/^Auto-fix applied/i, 'Fixed a small issue automatically'],
    [/^Committed to branch/i, 'Saved code to GitHub'],
    [/^Pull request #\d+ created/i, 'Opened a pull request for review'],
    [/^Staging deployment triggered/i, 'Started staging preview'],
    [/^Build passed/i, 'Tests passed'],
    [/^Deployed to staging:/i, 'Staging preview is ready:'],
    [/^Production release workflow started/i, 'Releasing to production…'],
  ]
  for (const [pattern, replacement] of replacements) {
    if (pattern.test(message)) {
      return message.replace(pattern, replacement)
    }
  }
  return message
}

export default function GenerationActivity({ events, collapsed = false }: GenerationActivityProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!collapsed) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events.length, collapsed])

  if (!events.length) return null

  const recent = collapsed ? events.slice(-3) : events

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Recent activity</h3>
      <div
        className={clsx(
          'rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50',
          collapsed ? 'p-3 max-h-32' : 'p-4 max-h-56',
          'overflow-y-auto space-y-2.5',
        )}
      >
        {recent.map((e, i) => (
          <div key={e.id ?? i} className="flex gap-3 text-sm">
            <span className="text-gray-400 flex-shrink-0 text-xs tabular-nums pt-0.5">
              {e.created_at ? new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
            </span>
            <span
              className={clsx(
                'text-gray-700 dark:text-gray-300',
                e.message.startsWith('✅') && 'text-success-700 dark:text-success-400',
                e.message.startsWith('❌') && 'text-error-700 dark:text-error-400',
              )}
            >
              {friendlyMessage(e.message.replace(/^[✅❌]\s*/, ''))}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
