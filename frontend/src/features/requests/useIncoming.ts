import { useEffect } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { useSession } from '@/features/auth/session'
import { workUnits } from '@/features/teams/units'
import { mockOrg } from '@/mock/orgChart'
import { requestActions, useRequests } from '@/mock/requestStore'

/** The administration the signed-in person belongs to (requests are addressed to it). */
export function useMyRequestUnit(): string {
  const { access } = useSession()
  const units = workUnits(access)
  return units.find((u) => u.kind === 'administration')?.name ?? units[0]?.name ?? ''
}

/** Requests waiting for this person's administration to answer. MOCK: also plants one sample request. */
export function usePendingIncoming(): number {
  const { t } = useI18n()
  const myUnit = useMyRequestUnit()
  const all = useRequests()
  useEffect(() => {
    if (!myUnit) return
    requestActions.seed({ title: t('requests.seed.title'), description: t('requests.seed.body'), dueDate: null, priority: 'high', fromUnit: mockOrg.children[1]?.name ?? '', fromName: mockOrg.children[1]?.leader?.name ?? '', toUnit: myUnit })
  }, [myUnit, t])
  return all.filter((r) => r.toUnit === myUnit && r.status === 'pending').length
}
