import { describe, expect, it } from 'vitest'
import { formatDateTime, localInputToIso } from './format'

describe('format', () => {
  it('turns a local datetime input into an ISO string with an explicit offset', () => {
    const iso = localInputToIso('2026-10-15T09:30')
    expect(iso).toMatch(/Z$/)
    expect(new Date(iso!).getHours()).toBe(9)
    expect(localInputToIso('')).toBeNull()
  })

  it('renders Latin digits in Arabic and a dash for empty', () => {
    expect(formatDateTime('2026-10-15T10:00:00Z', 'ar')).toMatch(/2026/)
    expect(formatDateTime(null, 'en')).toBe('—')
  })
})
