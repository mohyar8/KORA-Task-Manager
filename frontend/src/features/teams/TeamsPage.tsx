import { Link } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { EmptyState } from '@/shared/ui/Feedback'
import { PageHeader } from '@/shared/ui/Layout'
import { useSession } from '@/features/auth/session'
import { teamColor } from './teamColor'
import { workUnits } from './units'
import styles from './teams.module.css'

/** Every team and administration the person works in (this is the phone's way into a team). */
export function TeamsPage() {
  const { t } = useI18n()
  const { access } = useSession()
  const units = workUnits(access)
  return (
    <>
      <PageHeader title={t('teams.title')} description={t('teams.description')} />
      {units.length === 0 ? (
        <EmptyState title={t('teams.empty')} />
      ) : (
        <ul className={styles.cards}>
          {units.map((u) => (
            <li key={u.unit_id}>
              <Link to={`/teams/${u.unit_id}`} className={styles.cardLink}>
                <span className={styles.swatch} style={{ background: teamColor(u.unit_id), inlineSize: 40, blockSize: 40, fontSize: 'var(--text-md)' }} aria-hidden="true">{u.name.charAt(0)}</span>
                <span className={styles.cardName} dir="auto">{u.name}<small className={styles.cardKind}>{t(u.kind === 'team' ? 'team.kind.team' : 'team.kind.administration')}</small></span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
