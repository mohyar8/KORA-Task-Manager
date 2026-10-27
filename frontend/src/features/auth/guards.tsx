import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { AccessDenied, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { canAnywhere, isAdministrationManager } from './permissions'
import { useSession } from './session'
import type { Permission } from './types'

/** Layout route: everything inside needs a signed-in user who has already replaced a temporary password. */
export function RequireAuth() {
  const { status, error, retry, signedOut } = useSession()
  const location = useLocation()

  switch (status) {
    case 'loading':
      return <Skeleton lines={4} />
    case 'error':
      return <ErrorState error={error} onRetry={retry} />
    case 'anonymous':
      return <Navigate to="/sign-in" replace state={signedOut ? null : { from: location.pathname + location.search }} />
    case 'passwordChange':
      return <Navigate to="/change-password" replace />
    case 'ready':
      return <Outlet />
  }
}

/** Page-level guard. A route must still be enforced by the API; this only avoids showing a doomed page. */
export function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { access } = useSession()
  return canAnywhere(access, permission) ? children : <AccessDenied />
}

/** Administration managers only (the all-tasks list). */
export function RequireAdministrationManager({ children }: { children: ReactNode }) {
  const { access } = useSession()
  return isAdministrationManager(access) ? children : <AccessDenied />
}

/** Guards `/admin/*` UI. System Admin is separate from operational permissions (contract §3.4). */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { account } = useSession()
  return account?.is_system_admin ? children : <AccessDenied />
}
