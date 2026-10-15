import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { AlertCircle, Info } from 'lucide-react'
import { ApiError } from '@/shared/api/http'
import { useT } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { TextField } from '@/shared/ui/Field'
import { signIn } from './api'
import { AuthLayout } from './AuthLayout'
import { useSession } from './session'
import styles from './Auth.module.css'

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function SignInPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const { status, expired, applySession } = useSession()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showForgot, setShowForgot] = useState(false)
  // Seconds left of a 429 lockout (from Retry-After), counted down once a second.
  const [remaining, setRemaining] = useState(0)
  const locked = remaining > 0
  useEffect(() => {
    if (!locked) return
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(id)
  }, [locked])

  const mutation = useMutation({
    mutationFn: () => signIn(username.trim(), password),
    onSuccess: (session) => {
      applySession(session)
      navigate(session.account.must_change_password ? '/change-password' : from, { replace: true })
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 429) setRemaining(e.retryAfter ?? 900)
    },
  })

  if (status === 'ready') return <Navigate to={from} replace />
  if (status === 'passwordChange') return <Navigate to="/change-password" replace />

  const error = mutation.error
  let message: string | null = null
  if (locked) message = t('auth.signIn.locked', { time: formatCountdown(remaining) })
  else if (error instanceof ApiError) {
    if (error.status === 401) message = t('auth.signIn.invalid')
    else if (error.status === 0) message = t('auth.signIn.network')
    else if (error.status !== 429) message = t('auth.signIn.failed')
  } else if (error) message = t('auth.signIn.failed')

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!locked) mutation.mutate()
  }

  return (
    <AuthLayout>
      <div>
        <h1 className={styles.title}>{t('auth.signIn.title')}</h1>
        <p className={styles.sub}>{t('auth.signIn.subtitle')}</p>
      </div>

      {expired && (
        <div className={styles.notice} role="status">
          <Info size={18} aria-hidden="true" />
          <div>
            <strong>{t('state.sessionExpired.title')}</strong>
            <p>{t('state.sessionExpired.body')}</p>
          </div>
        </div>
      )}

      <form className={styles.form} onSubmit={onSubmit} noValidate>
        <TextField label={t('common.username')} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} dir="ltr" required />
        <TextField label={t('common.password')} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" dir="ltr" required />

        {message && (
          <p className={styles.alert} role="alert">
            <AlertCircle size={18} aria-hidden="true" /> {message}
          </p>
        )}

        <Button type="submit" loading={mutation.isPending} disabled={locked || !username.trim() || !password}>
          {t('auth.signIn.submit')}
        </Button>
      </form>

      <div>
        <button type="button" className={styles.link} aria-expanded={showForgot} onClick={() => setShowForgot((v) => !v)}>
          {t('auth.forgot.link')}
        </button>
        {showForgot && <p className={styles.forgot}>{t('auth.forgot.body')}</p>}
      </div>
    </AuthLayout>
  )
}
