import { NavLink } from 'react-router'
import { Bell } from 'lucide-react'
import { useT } from '@/shared/i18n/i18n'
import { useUnreadCount } from './api'
import styles from './notifications.module.css'

/** Header entry to /notifications with the polled unread count (the count is also in the accessible name). */
export function NotificationBell({ className }: { className?: string }) {
  const t = useT()
  const count = useUnreadCount()
  return (
    <NavLink to="/notifications" className={`${className ?? ''} ${styles.bell} ${count > 0 ? styles.alert : ''}`} aria-label={t('notif.bell', { n: count })}>
      <Bell size={20} aria-hidden="true" />
      {count > 0 && <span className={styles.badge} aria-hidden="true">{count > 99 ? '99+' : count}</span>}
    </NavLink>
  )
}
