'use client'

import { clsx } from 'clsx'
import { CheckCircle2, Loader2, Circle, AlertCircle } from 'lucide-react'
import HelpPopover from '@/components/ui/HelpPopover'
import {
  USER_PHASES,
  FAILED_STATUSES,
  getPhaseIndex,
  getUserStatusDescription,
} from '@/lib/generationStatus'
import { PIPELINE_HELP } from '@/lib/generationHelp'

interface GenerationPipelineProps {
  status: string
}

export default function GenerationPipeline({ status }: GenerationPipelineProps) {
  const currentIdx = getPhaseIndex(status)
  const failed = FAILED_STATUSES.includes(status as (typeof FAILED_STATUSES)[number])
  const released = status === 'Released'
  const description = getUserStatusDescription(status)

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
        <HelpPopover label="Help: progress steps" title={PIPELINE_HELP.title} align="right">
          {PIPELINE_HELP.body.map(line => (
            <p key={line}>{line}</p>
          ))}
        </HelpPopover>
      </div>

      <div className="flex flex-wrap gap-1.5 items-center">
        {USER_PHASES.map((phase, i) => {
          const phaseIdx = USER_PHASES.indexOf(phase)
          const done = released || currentIdx > phaseIdx
          const active = currentIdx === phaseIdx && !failed && !released
          const isFailed = failed && currentIdx === phaseIdx

          return (
            <div key={phase.key} className="flex items-center gap-1">
              <div
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                  done && 'bg-success-100 dark:bg-success-900/30 text-success-700 dark:text-success-400',
                  active && 'bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400 ring-2 ring-brand-300 dark:ring-brand-700',
                  isFailed && 'bg-error-100 dark:bg-error-900/30 text-error-700 dark:text-error-400',
                  !done && !active && !isFailed && 'bg-gray-100 dark:bg-gray-800 text-gray-400',
                )}
              >
                {done && <CheckCircle2 size={12} />}
                {active && <Loader2 size={12} className="animate-spin" />}
                {isFailed && <AlertCircle size={12} />}
                {!done && !active && !isFailed && <Circle size={12} />}
                {phase.label}
              </div>
              {i < USER_PHASES.length - 1 && (
                <div className={clsx('w-3 h-0.5', done ? 'bg-success-400' : 'bg-gray-200 dark:bg-gray-700')} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
