import { CalendarDays, ScrollText, Home, ListTodo, Megaphone, Network, ShieldCheck, Users, type LucideIcon } from 'lucide-react'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { canAnywhere } from '@/features/auth/permissions'
import type { EffectiveAccess, Permission } from '@/features/auth/types'

export interface NavItem {
  to: string
  labelKey: MessageKey
  icon: LucideIcon
  /** Show only if the user holds this permission at some unit. */
  permission?: Permission
  /** Show only to System Admins (an account grant, not an operational permission). */
  adminOnly?: boolean
}

/**
 * Primary navigation. Only routes that exist are listed (no dead links).
 * Visibility follows effective permissions (see `visibleNavItems`); later milestones append their items.
 */
export const navItems: NavItem[] = [
  { to: '/', labelKey: 'nav.home', icon: Home },
  { to: '/tasks', labelKey: 'nav.tasks', icon: ListTodo, permission: 'task.view' },
  { to: '/calendar', labelKey: 'nav.calendar', icon: CalendarDays },
  { to: '/announcements', labelKey: 'nav.announcements', icon: Megaphone },
  { to: '/organization', labelKey: 'nav.organization', icon: Network, permission: 'organization.manage' },
  { to: '/admin/members', labelKey: 'nav.members', icon: Users, adminOnly: true },
  { to: '/admin/audit', labelKey: 'nav.audit', icon: ScrollText, adminOnly: true },
  { to: '/admin/access', labelKey: 'nav.admin', icon: ShieldCheck, adminOnly: true },
]

export function visibleNavItems(access: EffectiveAccess | null, isSystemAdmin: boolean): NavItem[] {
  return navItems.filter((i) => (!i.permission || canAnywhere(access, i.permission)) && (!i.adminOnly || isSystemAdmin))
}
