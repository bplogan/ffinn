import {
  isInProgressStatus,
  getUserStatusLabel,
  getPhaseIndex,
  USER_PHASES,
} from '@/lib/generationStatus'

describe('generationStatus', () => {
  it('treats Staging as complete for the header badge, not in progress', () => {
    expect(isInProgressStatus('Staging')).toBe(false)
    expect(getUserStatusLabel('Staging')).toBe('Review in staging')
  })

  it('treats active pipeline statuses as in progress', () => {
    expect(isInProgressStatus('Generating')).toBe(true)
    expect(isInProgressStatus('Building')).toBe(true)
    expect(isInProgressStatus('Releasing')).toBe(true)
  })

  it('treats terminal statuses as not in progress', () => {
    expect(isInProgressStatus('Ready')).toBe(false)
    expect(isInProgressStatus('Released')).toBe(false)
    expect(isInProgressStatus('Failed')).toBe(false)
  })

  it('maps production states to user-facing labels', () => {
    expect(getUserStatusLabel('Ready')).toBe('Ready for production')
    expect(getUserStatusLabel('Releasing')).toBe('Releasing to production')
    expect(getUserStatusLabel('Released')).toBe('In production')
  })

  it('places staging review and production on separate pipeline steps', () => {
    const stagingIdx = USER_PHASES.findIndex(p => p.key === 'staging_review')
    const productionIdx = USER_PHASES.findIndex(p => p.key === 'production')
    expect(stagingIdx).toBeGreaterThan(-1)
    expect(productionIdx).toBe(stagingIdx + 1)
    expect(getPhaseIndex('Staging')).toBe(stagingIdx)
    expect(getPhaseIndex('Released')).toBe(productionIdx)
  })
})
