import { clsx } from 'clsx'
import React from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
  label?: React.ReactNode
  hint?: string
  icon?: React.ReactNode
  /** alias for icon */
  leftIcon?: React.ReactNode
  rightElement?: React.ReactNode
}

export default function Input({ label, error, hint, icon, leftIcon, rightElement, className, id, required, ...props }: InputProps) {
  const inputId = id || (typeof label === 'string' ? label.toLowerCase().replace(/\s+/g, '-') : undefined)
  const leftEl = icon || leftIcon
  return (
    <div className="space-y-1.5">
      {label && <label htmlFor={inputId} className="label">{label}{required && <span className="text-error-500 ml-0.5">*</span>}</label>}
      <div className="relative">
        {leftEl && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute pointer-events-none">{leftEl}</span>}
        <input
          id={inputId}
          {...props}
          className={clsx(
            'input-field',
            leftEl && 'pl-10',
            rightElement && 'pr-10',
            error && 'input-error',
            className,
          )}
        />
        {rightElement && <span className="absolute right-3 top-1/2 -translate-y-1/2">{rightElement}</span>}
      </div>
      {error && <p className="text-xs text-error-600 dark:text-error-400">{error}</p>}
      {hint && !error && <p className="text-xs text-ink-mute">{hint}</p>}
    </div>
  )
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: React.ReactNode
  error?: string
  children: React.ReactNode
}
export function Select({ label, error, children, className, id, required, ...props }: SelectProps) {
  const selectId = id || (typeof label === 'string' ? label.toLowerCase().replace(/\s+/g, '-') : undefined)
  return (
    <div className="space-y-1.5">
      {label && <label htmlFor={selectId} className="label">{label}{required && <span className="text-error-500 ml-0.5">*</span>}</label>}
      <select id={selectId} {...props} className={clsx('input-field', error && 'input-error', className)}>
        {children}
      </select>
      {error && <p className="text-xs text-error-600 dark:text-error-400">{error}</p>}
    </div>
  )
}

interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode
  error?: string
  hint?: string
}
export function TextArea({ label, error, hint, className, id, required, ...props }: TextAreaProps) {
  const textareaId = id || (typeof label === 'string' ? label.toLowerCase().replace(/\s+/g, '-') : undefined)
  return (
    <div className="space-y-1.5">
      {label && <label htmlFor={textareaId} className="label">{label}{required && <span className="text-error-500 ml-0.5">*</span>}</label>}
      <textarea id={textareaId} {...props}
        className={clsx('input-field min-h-[80px] resize-y', error && 'input-error', className)} />
      {error && <p className="text-xs text-error-600 dark:text-error-400">{error}</p>}
      {hint && !error && <p className="text-xs text-ink-mute">{hint}</p>}
    </div>
  )
}
