import { useI18n } from '@/shared/i18n/i18n'
import { Card, PageHeader } from '@/shared/ui/Layout'
import type { MessageKey } from '@/shared/i18n/messages.en'
import styles from './gaps.module.css'

// Product requirements the backend does not support yet (spec addendum D). Shown so nothing is silently dropped.
const GAPS: MessageKey[] = [
  'gaps.messaging', 'gaps.scheduled', 'gaps.reminders', 'gaps.import', 'gaps.archive', 'gaps.teamWide', 'gaps.analytics',
  'gaps.rename', 'gaps.export', 'gaps.recruitment',
]

export function GapsPage() {
  const { t } = useI18n()
  return (
    <>
      <PageHeader title={t('gaps.title')} description={t('gaps.description')} />
      <Card>
        <ul className={styles.list}>
          {GAPS.map((k) => <li key={k}>{t(k)}</li>)}
        </ul>
      </Card>
    </>
  )
}
