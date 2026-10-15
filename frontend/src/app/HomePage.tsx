import { Link } from 'react-router'
import { Bell, ChevronLeft } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { canAnywhere } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useUnreadCount } from '@/features/notifications/api'
import { HomeSummary } from '@/features/tasks/HomeSummary'
import { UpcomingEvents } from '@/features/calendar/UpcomingEvents'
import { visibleNavItems } from './nav'
import styles from './home.module.css'

/** Home: a welcome banner, quick links to what the user may open, then the task overview. */
export function HomePage() {
  const { t } = useI18n()
  const { account, access } = useSession()
  const unread = useUnreadCount()
  const hour = new Date().getHours()
  const greeting = hour < 12 ? t('home.greeting.morning') : hour < 18 ? t('home.greeting.afternoon') : t('home.greeting.evening')
  const quick = visibleNavItems(access, !!account?.is_system_admin).filter((i) => i.to !== '/')

  return (
    <div className={styles.page}>
      <h1 className="visually-hidden">{t('home.title')}</h1>
      <section className={styles.hero}>
        <div className={styles.heroText}>
          <p className={styles.heroKicker}>{greeting}</p>
          <p className={styles.heroTitle} dir="auto">{account?.username}</p>
          <p className={styles.heroSub}>{t('home.greeting.sub')}</p>
        </div>
        <Link to="/notifications" className={styles.bellCard}>
          <span className={styles.bellIcon}><Bell size={22} aria-hidden="true" /></span>
          <span className={styles.bellCount}>{unread}</span>
          <span className={styles.bellLabel}>{t('home.notifications')}</span>
        </Link>
        <span className={`${styles.blob} ${styles.blobA}`} aria-hidden="true" />
        <span className={`${styles.blob} ${styles.blobB}`} aria-hidden="true" />
      </section>

      {quick.length > 0 && (
        <section aria-label={t('home.quick')}>
          <h2 className={styles.sectionTitle}>{t('home.quick')}</h2>
          <ul className={styles.quick}>
            {quick.map((q, i) => (
              <li key={q.to} style={{ animationDelay: `${i * 50}ms` }}>
                <Link to={q.to} className={styles.tile}>
                  <span className={`${styles.tileIcon} ${styles[`tone${i % 4}`]}`}><q.icon size={22} aria-hidden="true" /></span>
                  <span className={styles.tileLabel}>{t(q.labelKey)}</span>
                  <ChevronLeft size={18} className={styles.tileArrow} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <UpcomingEvents />
      {canAnywhere(access, 'task.view') && <HomeSummary />}
    </div>
  )
}
