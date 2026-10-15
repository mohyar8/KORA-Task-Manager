import { useSearchParams } from 'react-router'
import { useT } from '@/shared/i18n/i18n'
import { PageHeader } from '@/shared/ui/Layout'
import { Tabs } from '@/shared/ui/Tabs'
import { AccountAccessTab } from './AccountAccessTab'
import { RoleDefaultsTab } from './RoleDefaultsTab'
import { SystemAdminsTab } from './SystemAdminsTab'

const TAB_IDS = ['accounts', 'roles', 'admins'] as const
type TabId = (typeof TAB_IDS)[number]

/** /admin/access — the active tab (and the chosen account) live in the URL so the page is linkable. */
export function AdminAccessPage() {
  const t = useT()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const active: TabId = TAB_IDS.find((id) => id === requested) ?? 'accounts'

  const select = (id: string) => {
    const next = new URLSearchParams(params)
    next.set('tab', id)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageHeader title={t('admin.access.title')} description={t('admin.access.description')} />
      <Tabs
        label={t('admin.tabs.label')}
        active={active}
        onChange={select}
        tabs={[
          { id: 'accounts', label: t('admin.tab.accounts') },
          { id: 'roles', label: t('admin.tab.roles') },
          { id: 'admins', label: t('admin.tab.admins') },
        ]}
      >
        {active === 'accounts' && <AccountAccessTab />}
        {active === 'roles' && <RoleDefaultsTab />}
        {active === 'admins' && <SystemAdminsTab />}
      </Tabs>
    </>
  )
}
