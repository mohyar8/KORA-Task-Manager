import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { Ellipsis, Languages } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Modal } from '@/shared/ui/Modal'
import lockup from '@/shared/brand/kora-lockup-white.png'
import ballMark from '@/shared/brand/kora-lockup-ball.png'
import { useDisplayName } from '@/features/members/directory'
import { NotificationBell } from '@/features/notifications/NotificationBell'
import { useSession } from '@/features/auth/session'
import { visibleNavItems } from './nav'
import styles from './AppShell.module.css'

const MOBILE_PRIMARY = 4

export function AppShell() {
  const { t, locale, setLocale } = useI18n()
  const { account, access } = useSession()
  const location = useLocation()
  const navItems = visibleNavItems(access, !!account?.is_system_admin)
  const [moreOpen, setMoreOpen] = useState(false)
  const mobilePrimary = navItems.length > MOBILE_PRIMARY ? navItems.slice(0, MOBILE_PRIMARY - 1) : navItems
  const mobileMore = navItems.length > MOBILE_PRIMARY ? navItems.slice(MOBILE_PRIMARY - 1) : []

  const link = (item: (typeof navItems)[number], cls: string, onClick?: () => void) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.to === '/'}
      title={t(item.labelKey)}
      className={({ isActive }) => `${cls} ${isActive ? styles.active : ''}`}
      onClick={onClick}
    >
      <span className={styles.icon}><item.icon size={20} aria-hidden="true" /></span>
      <span className={styles.label}>{t(item.labelKey)}</span>
    </NavLink>
  )
  const displayName = useDisplayName()
  const initial = (displayName || '?').charAt(0).toUpperCase()

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">{t('app.skipToContent')}</a>

      <header className={styles.header}>
        <div className={styles.bar}>
          <NavLink to="/" className={styles.brand} aria-label={t('app.name')}>
            <img className={styles.brandFull} src={lockup} alt="" height={26} />
            <img className={styles.brandMark} src={ballMark} alt="" height={27} />
          </NavLink>

          <nav aria-label={t('common.menu')} className={styles.topNav}>
            {navItems.map((item) => link(item, styles.topLink))}
          </nav>

          <div className={styles.tools}>
            <NotificationBell className={styles.tool} />
            <button type="button" className={styles.tool} onClick={() => setLocale(locale === 'ar' ? 'en' : 'ar')} aria-label={t('common.languageLabel')}>
              <Languages size={20} aria-hidden="true" />
              <span className={styles.toolText}>{t('common.language')}</span>
            </button>
            <NavLink to="/account" className={styles.avatarLink} aria-label={t('nav.account')}>
              <span className={styles.avatar} aria-hidden="true">{initial}</span>
              <span className={styles.userName} dir="auto">{displayName}</span>
            </NavLink>
          </div>
        </div>
      </header>

      <main id="main" className={styles.main} tabIndex={-1}>
        <div className={styles.content} key={location.pathname}>
          <Outlet />
        </div>
      </main>

      <nav aria-label={t('common.menu')} className={styles.bottomNav}>
        {mobilePrimary.map((item) => link(item, styles.bottomLink))}
        {mobileMore.length > 0 && (
          <button type="button" className={styles.bottomLink} onClick={() => setMoreOpen(true)}>
            <span className={styles.icon}><Ellipsis size={21} aria-hidden="true" /></span>
            <span className={styles.label}>{t('common.more')}</span>
          </button>
        )}
      </nav>

      <Modal open={moreOpen} title={t('common.more')} onClose={() => setMoreOpen(false)}>
        <nav className={styles.moreList} aria-label={t('common.more')}>
          {mobileMore.map((item) => link(item, styles.moreLink, () => setMoreOpen(false)))}
        </nav>
      </Modal>

    </div>
  )
}
