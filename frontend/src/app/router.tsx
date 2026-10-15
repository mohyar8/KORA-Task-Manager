import type { ComponentType, ReactNode } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { AccountPage } from '@/features/auth/AccountPage'
import { ForcedPasswordPage } from '@/features/auth/ForcedPasswordPage'
import { RequireAdmin, RequireAuth, RequirePermission } from '@/features/auth/guards'
import { SignInPage } from '@/features/auth/SignInPage'
import { AppShell } from './AppShell'
import { GapsPage } from './GapsPage'
import { HomePage } from './HomePage'
import { RouteError } from './RouteError'
import { AccessDeniedPage, ConnectionFailurePage, NotFoundPage } from './SystemPages'

type Loader = () => Promise<Record<string, unknown>>

/** A route whose page code is fetched on first visit (each feature is its own chunk). */
function page(path: string, load: Loader, name: string, guard?: (page: ReactNode) => ReactNode): RouteObject {
  return {
    path,
    lazy: async () => {
      const Page = (await load())[name] as ComponentType
      return { Component: () => (guard ? guard(<Page />) : <Page />) }
    },
  }
}

const admin = (node: ReactNode) => <RequireAdmin>{node}</RequireAdmin>
const manageOrg = (node: ReactNode) => <RequirePermission permission="organization.manage">{node}</RequirePermission>

/** The shell wraps every signed-in route. Pages are guarded here as well as by the API (the API is the authority). */
export const routes: RouteObject[] = [
  { path: 'sign-in', element: <SignInPage /> },
  { path: 'change-password', element: <ForcedPasswordPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        errorElement: <RouteError />,
        children: [
          { index: true, element: <HomePage /> },
          { path: 'account', element: <AccountPage /> },
          { path: 'not-available', element: <GapsPage /> },
          page('tasks', () => import('@/features/tasks/TasksPage'), 'TasksPage'),
          page('tasks/:taskId', () => import('@/features/tasks/TaskDetailPage'), 'TaskDetailPage'),
          page('task-series/:seriesId', () => import('@/features/tasks/SeriesPage'), 'SeriesPage'),
          page('calendar', () => import('@/features/calendar/CalendarPage'), 'CalendarPage'),
          page('calendar/:eventId', () => import('@/features/calendar/EventDetailPage'), 'EventDetailPage'),
          page('announcements', () => import('@/features/announcements/AnnouncementsPage'), 'AnnouncementsPage'),
          page('announcements/:announcementId', () => import('@/features/announcements/AnnouncementDetailPage'), 'AnnouncementDetailPage'),
          page('notifications', () => import('@/features/notifications/NotificationsPage'), 'NotificationsPage'),
          page('organization', () => import('@/features/organization/OrganizationPage'), 'OrganizationPage', manageOrg),
          page('admin/members', () => import('@/features/members/MembersPage'), 'MembersPage', admin),
          page('admin/members/:memberId', () => import('@/features/members/MemberDetailPage'), 'MemberDetailPage', admin),
          page('admin/access', () => import('@/features/access/AdminAccessPage'), 'AdminAccessPage', admin),
          page('admin/audit', () => import('@/features/audit/AuditPage'), 'AuditPage', admin),
          { path: 'access-denied', element: <AccessDeniedPage /> },
          { path: 'connection-failure', element: <ConnectionFailurePage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
