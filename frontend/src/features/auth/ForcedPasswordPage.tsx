import { Navigate, useNavigate } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { useT } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { signOut } from './api'
import { AuthLayout } from './AuthLayout'
import { ChangePasswordForm } from './ChangePasswordForm'
import { useSession } from './session'
import styles from './Auth.module.css'

/** Signed in with a temporary password: nothing else works until it is replaced (contract §2.4). */
export function ForcedPasswordPage() {
  const t = useT()
  const navigate = useNavigate()
  const { status, endSession } = useSession()
  const leave = useMutation({
    mutationFn: signOut,
    onSettled: () => {
      endSession()
      navigate('/sign-in', { replace: true })
    },
  })

  if (status === 'anonymous') return <Navigate to="/sign-in" replace />
  if (status === 'ready') return <Navigate to="/" replace />
  if (status === 'loading') return null

  return (
    <AuthLayout>
      <div>
        <h1 className={styles.title}>{t('auth.password.title')}</h1>
        <p className={styles.sub}>{t('auth.password.forcedBody')}</p>
      </div>
      <ChangePasswordForm onChanged={() => navigate('/', { replace: true })} />
      <div>
        <Button variant="ghost" onClick={() => leave.mutate()} loading={leave.isPending}>{t('account.signOut')}</Button>
      </div>
    </AuthLayout>
  )
}
