import { useNavigate } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { useT } from '@/shared/i18n/i18n'
import { Button, LinkButton } from '@/shared/ui/Button'
import { Chip, useToast } from '@/shared/ui/Feedback'
import { Card, PageHeader } from '@/shared/ui/Layout'
import { signOut } from './api'
import { ChangePasswordForm } from './ChangePasswordForm'
import { useSession } from './session'
import styles from './Auth.module.css'

// The contract exposes no role/Team/scope endpoint for the caller (roadmap G3), so only /auth/me facts are shown.
export function AccountPage() {
  const t = useT()
  const navigate = useNavigate()
  const toast = useToast()
  const { account, endSession } = useSession()

  const leave = (fn: () => Promise<void>) => ({
    mutationFn: fn,
    // Whether or not the server answered, this browser no longer has a usable session.
    onSettled: () => {
      endSession()
      navigate('/sign-in', { replace: true })
    },
  })
  const out = useMutation(leave(signOut))

  if (!account) return null

  return (
    <>
      <PageHeader title={t('account.title')} description={t('account.description')} />
      <div className={styles.accountGrid}>
        <Card>
          <dl className={styles.facts}>
            <dt>{t('account.username')}</dt>
            <dd dir="ltr">{account.username}</dd>
            {account.is_system_admin && (
              <>
                <dt>{t('account.systemAdmin')}</dt>
                <dd><Chip tone="info">{t('account.systemAdmin')}</Chip></dd>
              </>
            )}
          </dl>
        </Card>

        <Card>
          <h2 className={styles.cardTitle}>{t('account.passwordSection')}</h2>
          <ChangePasswordForm onChanged={() => toast(t('auth.password.changed'))} />
        </Card>

        <Card>
          <h2 className={styles.cardTitle}>{t('account.sessionsSection')}</h2>
          <div className={styles.actions}>
            <Button variant="secondary" onClick={() => out.mutate()} loading={out.isPending}>{t('account.signOut')}</Button>
          </div>
        </Card>
        <LinkButton to="/not-available" variant="ghost">{t('account.gapsLink')}</LinkButton>
      </div>

    </>
  )
}
