import { describe, expect, it } from 'vitest'
import { accessFor } from '@/test/fakeApi'
import { visibleNavItems } from '@/app/nav'
import { allUnits, allowedUnits, canAnywhere, canAt } from './permissions'
import type { EffectiveAccess } from './types'

const access = accessFor(['task.create@u-team', 'organization.manage@u-kora']) as unknown as EffectiveAccess

describe('permissions', () => {
  it('reads decisions from the access response only', () => {
    expect(canAt(access, 'task.create', 'u-team')).toBe(true)
    expect(canAt(access, 'task.create', 'u-kora')).toBe(false)
    expect(canAnywhere(access, 'organization.manage')).toBe(true)
    expect(canAnywhere(access, 'calendar.manage')).toBe(false)
    expect(allowedUnits(access, 'task.create').map((u) => u.name)).toEqual(['Team A'])
  })

  it('denies everything without an access response', () => {
    expect(canAnywhere(null, 'task.view')).toBe(false)
    expect(allUnits(null)).toEqual([])
  })

  it('lists each unit once for lookups', () => {
    expect(allUnits(access).map((u) => u.unit_id).sort()).toEqual(['u-kora', 'u-team'])
  })

  it('shows Home to everyone (no permission required)', () => {
    expect(visibleNavItems(null, false).map((i) => i.to)).toContain('/')
  })
})
