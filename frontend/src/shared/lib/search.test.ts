import { describe, expect, it } from 'vitest'
import { matchesSearch } from './search'

describe('matchesSearch', () => {
  it('matches first and last name without the middle', () => {
    expect(matchesSearch('طارق الحربي', 'طارق فيصل الحربي')).toBe(true)
  })
  it('ignores hamza and ta marbuta variants', () => {
    expect(matchesSearch('احمد', 'أحمد شهاب')).toBe(true)
  })
  it('requires every word', () => {
    expect(matchesSearch('طارق سعد', 'طارق فيصل الحربي')).toBe(false)
  })
  it('matches an empty query', () => {
    expect(matchesSearch('  ', 'x')).toBe(true)
  })
})
