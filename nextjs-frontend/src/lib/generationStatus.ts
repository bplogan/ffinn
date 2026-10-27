/**
 * User-facing generation status helpers.
 * Backend statuses stay granular; the UI groups them into plain-language phases.
 */

export const TERMINAL_STATUSES = ['Ready', 'Released', 'Failed', 'Cancelled', 'Reverted'] as const

export const SUCCESS_STATUSES = ['Ready', 'Released', 'Staging'] as const

export const FAILED_STATUSES = ['Failed', 'Cancelled', 'Reverted'] as const

/** Backend statuses that mean work is still running */
export const IN_PROGRESS_STATUSES = [
  'Queued',
  'Analyzing',
  'Generating',
  'Validating',
  'AutoFixing',
  'Committing',
  'CreatingPr',
  'Building',
  'Releasing',
] as const

export type UserPhase = {
  key: string
  label: string
  description: string
  statuses: readonly string[]
}

/** Simplified pipeline shown on the generate page */
export const USER_PHASES: UserPhase[] = [
  {
    key: 'waiting',
    label: 'Queued',
    description: 'Your request is waiting to start.',
    statuses: ['Queued', 'Draft'],
  },
  {
    key: 'writing',
    label: 'Writing code',
    description: 'The AI is drafting your feature based on your description.',
    statuses: ['Analyzing', 'Generating'],
  },
  {
    key: 'reviewing',
    label: 'Quality check',
    description: 'We are reviewing the code for errors and best practices.',
    statuses: ['Validating', 'AutoFixing'],
  },
  {
    key: 'publishing',
    label: 'Saving changes',
    description: 'Your code is being saved to GitHub and a pull request is being opened.',
    statuses: ['Committing', 'CreatingPr'],
  },
  {
    key: 'deploying',
    label: 'Deploying to staging',
    description: 'Running automated tests and publishing the staging app and API.',
    statuses: ['Building'],
  },
  {
    key: 'staging_review',
    label: 'Review in staging',
    description: 'Open the staging app, verify your changes, then release to production when ready.',
    statuses: ['Staging', 'Ready'],
  },
  {
    key: 'production',
    label: 'In production',
    description: 'Your feature is live for all users.',
    statuses: ['Releasing', 'Released'],
  },
]

const STATUS_TO_LABEL: Record<string, string> = {
  Draft: 'Draft',
  Queued: 'Queued',
  Analyzing: 'Writing code',
  Generating: 'Writing code',
  Validating: 'Quality check',
  AutoFixing: 'Quality check',
  Committing: 'Saving changes',
  CreatingPr: 'Saving changes',
  Building: 'Deploying to staging',
  Staging: 'Review in staging',
  Ready: 'Ready for production',
  Releasing: 'Releasing to production',
  Released: 'In production',
  Failed: 'Failed',
  Cancelled: 'Cancelled',
  Reverted: 'Reverted',
}

const STATUS_TO_DESCRIPTION: Record<string, string> = {
  Queued: 'Your request is in line and will start shortly.',
  Analyzing: 'Understanding your request and preparing to write code.',
  Generating: 'The AI is writing your feature — this usually takes a few minutes.',
  Validating: 'Checking the generated code for issues.',
  AutoFixing: 'Fixing any issues found during the quality check.',
  Committing: 'Saving the new code to your repository.',
  CreatingPr: 'Opening a pull request so you can review the changes.',
  Building: 'Running tests and deploying your staging preview.',
  Staging: 'Your staging preview is ready — open the app and verify everything before going live.',
  Ready: 'Review complete — release to production when you are satisfied.',
  Releasing: 'Merging and deploying to production.',
  Released: 'Your feature is live in production.',
  Failed: 'Something went wrong. You can try again or adjust your request.',
  Cancelled: 'This generation was cancelled.',
  Reverted: 'This generation was reverted.',
}

export function isInProgressStatus(status: string): boolean {
  return IN_PROGRESS_STATUSES.includes(status as (typeof IN_PROGRESS_STATUSES)[number])
}

export function getUserStatusLabel(status: string): string {
  return STATUS_TO_LABEL[status] ?? status
}

export function getUserStatusDescription(status: string): string {
  return STATUS_TO_DESCRIPTION[status] ?? 'Working on your request…'
}

export function getPhaseIndex(status: string): number {
  if (status === 'Released') {
    return USER_PHASES.length - 1
  }
  const idx = USER_PHASES.findIndex(p => p.statuses.includes(status))
  return idx === -1 ? 0 : idx
}

export function getCurrentPhase(status: string): UserPhase | null {
  return USER_PHASES.find(p => p.statuses.includes(status)) ?? null
}

export function statusBadgeVariant(
  status: string,
): 'success' | 'error' | 'warning' | 'gray' {
  if (SUCCESS_STATUSES.includes(status as (typeof SUCCESS_STATUSES)[number]) || status === 'Released') {
    return 'success'
  }
  if (FAILED_STATUSES.includes(status as (typeof FAILED_STATUSES)[number])) {
    return 'error'
  }
  if (isInProgressStatus(status)) {
    return 'warning'
  }
  return 'gray'
}
