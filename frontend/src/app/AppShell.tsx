import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { Ellipsis, Languages, UsersRound, type LucideIcon } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Modal } from '@/shared/ui/Modal'
import lockup from '@/shared/brand/kora-lockup-white.png'
import ballMark from '@/shared/brand/kora-lockup-ball.png'
import { useDisplayName } from '@/features/members/directory'
import { NotificationBell } from '@/features/notifications/NotificationBell'
import { useSession } from '@/features/auth/session'
import { useChannels } from '@/features/chat/useChannels'
import { useAnnouncements } from '@/features/announcements/api'
import { usePendingIncoming } from '@/features/requests/useIncoming'
import { PanelArt } from '@/shared/brand/PanelArt'
import { teamColor } from '@/features/teams/teamColor'
import { workUnits } from '@/features/teams/units'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { visibleNavItems, type NavItem, type NavSection } from './nav'
import styles from './AppShell.module.css'

interface Link {
  to: string
  label: string
  icon: LucideIcon
}

const SECTION_TITLE: Record<Exclude<NavSection, 'main'>, MessageKey> = { tools: 'nav.section.tools', admin: 'nav.section.admin' }

export function AppShell() {
  const { t, locale, setLocale } = useI18n()
  const { account, access } = useSession()
  const location = useLocation()
  const items = visibleNavItems(access, !!account?.is_system_admin)
  const units = workUnits(access)
  const [moreOpen, setMoreOpen] = useState(false)
  const { totalUnread } = useChannels()
  const pendingRequests = usePendingIncoming()
  const unreadAnnouncements = (useAnnouncements('published').data ?? []).filter((a) => !a.content_hidden && a.my_read_current === false).length
  // A number next to a place means something new is waiting there.
  const badges: Record<string, number> = { '/chat': totalUnread, '/requests': pendingRequests, '/announcements': unreadAnnouncements }

  const toLink = (i: NavItem): Link => ({ to: i.to, label: t(i.labelKey), icon: i.icon })
  const home = items.filter((i) => i.section === 'main').map(toLink)
  const calendar = items.filter((i) => i.to === '/calendar').map(toLink)
  const teams: Link[] = units.length > 0 ? [{ to: '/teams', label: t('nav.teams'), icon: UsersRound }] : []
  // Phones: the three places people use all day; everything else sits behind "More".
  const mobilePrimary = [...home, ...teams, ...calendar]
  const mobileMore = items.filter((i) => i.section !== 'main' && i.to !== '/calendar').map(toLink)

  const link = (item: Link, cls: string, onClick?: () => void) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) => `${cls} ${isActive ? styles.active : ''}`}
      onClick={onClick}
    >
      <span className={styles.icon}><item.icon size={20} aria-hidden="true" /></span>
      <span className={styles.label}>{item.label}</span>
      {(badges[item.to] ?? 0) > 0 && <span className={styles.unread} aria-label={t('common.newItems', { n: badges[item.to] })}>{badges[item.to]}</span>}
    </NavLink>
  )
  const displayName = useDisplayName()
  const initial = (displayName || '?').charAt(0).toUpperCase()
  const section = (key: Exclude<NavSection, 'main'>) => {
    const list = items.filter((i) => i.section === key)
    if (list.length === 0) return null
    return (
      <div className={styles.group} key={key}>
        <p className={styles.groupTitle}>{t(SECTION_TITLE[key])}</p>
        {list.map((i) => link(toLink(i), styles.sideLink))}
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">{t('app.skipToContent')}</a>

      <header className={styles.header}>
        <div className={styles.bar}>
          <NavLink to="/" className={styles.brand} aria-label={t('app.name')}>
            <img className={styles.brandFull} src={lockup} alt="" height={26} />
            <img className={styles.brandMark} src={ballMark} alt="" height={27} />
          </NavLink>

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

      <div className={styles.body}>
        <nav aria-label={t('common.menu')} className={styles.sidebar}>
          {home.map((i) => link(i, styles.sideLink))}
          {units.length > 0 && (
            <div className={styles.group}>
              <p className={styles.groupTitle}>{t('nav.section.teams')}</p>
              {units.map((u) => (
                <NavLink key={u.unit_id} to={`/teams/${u.unit_id}`} className={({ isActive }) => `${styles.sideLink} ${styles.teamLink} ${isActive ? styles.active : ''}`}>
                  <span className={styles.swatch} style={{ background: teamColor(u.unit_id) }} aria-hidden="true">{u.name.charAt(0)}</span>
                  <span className={styles.label} dir="auto">{u.name}</span>
                </NavLink>
              ))}
            </div>
          )}
          {section('tools')}
          {section('admin')}
          <div className={styles.artBox} aria-hidden="true"><PanelArt className={styles.art} /></div>
        </nav>

        <main id="main" className={styles.main} tabIndex={-1}>
          <div className={styles.content} key={location.pathname}>
            <Outlet />
          </div>
        </main>
      </div>

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
