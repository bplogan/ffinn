'use client'

import { Fragment, useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { Zap, Loader2, ChevronRight } from 'lucide-react'
import { aiGenerationsApi } from '@/lib/api'
import type { AIGeneration, PagedResult } from '@/types'
import {
  isInProgressStatus,
  getUserStatusLabel,
} from '@/lib/generationStatus'
import { clsx } from 'clsx'

export default function GenerationInProgressIndicator() {
  const [open, setOpen] = useState(false)

  const { data } = useQuery({
    queryKey: ['ai-generations-in-progress'],
    queryFn: () =>
      aiGenerationsApi.list({ page: 1, page_size: 20 }) as Promise<PagedResult<AIGeneration>>,
    refetchInterval: 8000,
  })

  const inProgress = (data?.items ?? []).filter(g => isInProgressStatus(g.status))
  const count = inProgress.length

  if (count === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={clsx(
          'relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-colors',
          'text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20',
          open && 'bg-brand-50 dark:bg-brand-900/20',
        )}
        title={`${count} code generation${count === 1 ? '' : 's'} in progress`}
      >
        <Loader2 size={16} className="animate-spin" />
        <span className="hidden sm:inline text-sm font-medium">
          {count === 1 ? 'Generating' : `${count} generating`}
        </span>
        <span className="flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-brand-500 text-white text-[10px] font-bold">
          {count}
        </span>
      </button>

      {open && (
        <Fragment>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 w-72 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg py-1 z-20">
            <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-700 flex items-center gap-2">
              <Zap size={14} className="text-brand-500" />
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                Code generation{count === 1 ? '' : 's'} in progress
              </p>
            </div>
            <ul className="max-h-64 overflow-y-auto py-1">
              {inProgress.map(gen => (
                <li key={gen.id}>
                  <Link
                    href={`/app/ai-agent/run?gen=${gen.id}`}
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-2 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors group"
                  >
                    <Loader2 size={14} className="animate-spin text-brand-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {gen.feature_name ?? 'Untitled feature'}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {getUserStatusLabel(gen.status)}
                      </p>
                    </div>
                    <ChevronRight size={14} className="text-gray-400 group-hover:text-brand-500 flex-shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
            <div className="px-3 py-2 border-t border-gray-100 dark:border-gray-700">
              <Link
                href="/app/ai-agent/run"
                onClick={() => setOpen(false)}
                className="text-xs text-brand-600 dark:text-brand-400 hover:underline"
              >
                Open generate page
              </Link>
            </div>
          </div>
        </Fragment>
      )}
    </div>
  )
}
