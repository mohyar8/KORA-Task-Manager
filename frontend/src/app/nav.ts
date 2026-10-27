import { CalendarDays, ClipboardCheck, Trophy, ScrollText, Home, ListTodo, MessageSquare, Megaphone, Network, ShieldCheck, Users, Workflow, Handshake, type LucideIcon } from 'lucide-react'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { canAnywhere, isAdministrationManager } from '@/features/auth/permissions'
import type { EffectiveAccess, Permission } from '@/features/auth/types'

export type NavSection = 'main' | 'tools' | 'admin'

export interface NavItem {
  to: string
  labelKey: MessageKey
  icon: LucideIcon
  section: NavSection
  /** Show only if the user holds this permission at some unit. */
  permission?: Permission
  /** Show only to System Admins (an account grant, not an operational permission). */
  adminOnly?: boolean
  /** Show only to managers of an Administration (not team leaders). */
  administrationManagerOnly?: boolean
}

/**
 * Primary navigation. Only routes that exist are listed (no dead links).
 * Visibility follows effective permissions (see `visibleNavItems`); later milestones append their items.
 * The team list ("My teams") is built from the access response in the shell, not listed here.
 */
export const navItems: NavItem[] = [
  { to: '/', labelKey: 'nav.home', icon: Home, section: 'main' },
  { to: '/chat', labelKey: 'nav.chat', icon: MessageSquare, section: 'main' },
  { to: '/tasks', labelKey: 'nav.tasks', icon: ListTodo, section: 'tools', permission: 'task.view', administrationManagerOnly: true },
  { to: '/follow', labelKey: 'nav.follow', icon: ClipboardCheck, section: 'tools', permission: 'task.follow' },
  { to: '/structure', labelKey: 'nav.structure', icon: Workflow, section: 'tools' },
  { to: '/requests', labelKey: 'nav.requests', icon: Handshake, section: 'tools', permission: 'task.manage' },
  { to: '/calendar', labelKey: 'nav.calendar', icon: CalendarDays, section: 'tools' },
  { to: '/announcements', labelKey: 'nav.announcements', icon: Megaphone, section: 'tools' },
  { to: '/league', labelKey: 'nav.league', icon: Trophy, section: 'tools' },
  { to: '/organization', labelKey: 'nav.organization', icon: Network, section: 'admin', permission: 'organization.manage' },
  { to: '/admin/members', labelKey: 'nav.members', icon: Users, section: 'admin', adminOnly: true },
  { to: '/admin/audit', labelKey: 'nav.audit', icon: ScrollText, section: 'admin', adminOnly: true },
  { to: '/admin/access', labelKey: 'nav.admin', icon: ShieldCheck, section: 'admin', adminOnly: true },
]

export function visibleNavItems(access: EffectiveAccess | null, isSystemAdmin: boolean): NavItem[] {
  return navItems.filter((i) => (!i.permission || canAnywhere(access, i.permission)) && (!i.adminOnly || isSystemAdmin) && (!i.administrationManagerOnly || isAdministrationManager(access)))
}
