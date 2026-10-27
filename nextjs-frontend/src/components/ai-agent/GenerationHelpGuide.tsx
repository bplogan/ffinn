'use client'

import { Lightbulb } from 'lucide-react'
import { getGenerationGuide } from '@/lib/generationHelp'

interface GenerationHelpGuideProps {
  status: string
}

export default function GenerationHelpGuide({ status }: GenerationHelpGuideProps) {
  const guide = getGenerationGuide(status)

  return (
    <div className="rounded-xl border border-brand-200 dark:border-brand-800/50 bg-brand-50/80 dark:bg-brand-900/20 p-4">
      <div className="flex gap-3">
        <Lightbulb size={20} className="text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
        <div className="min-w-0 space-y-2">
          <div>
            <p className="text-sm font-semibold text-brand-900 dark:text-brand-100">{guide.title}</p>
            <p className="text-sm text-brand-800/90 dark:text-brand-200/90 mt-1">{guide.summary}</p>
          </div>
          {guide.steps.length > 0 && (
            <ol className="text-sm text-brand-800/80 dark:text-brand-200/80 space-y-1.5 list-decimal list-inside marker:font-medium">
              {guide.steps.map((step, i) => (
                <li key={i} className="leading-relaxed">
                  <StepText text={step} />
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  )
}

/** Renders **bold** markers in help copy without markdown dependency. */
function StepText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={i} className="font-semibold text-brand-900 dark:text-brand-100">
              {part.slice(2, -2)}
            </strong>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
