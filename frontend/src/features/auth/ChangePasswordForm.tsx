import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import { ApiError } from '@/shared/api/http'
import { useT } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { TextField } from '@/shared/ui/Field'
import { changePassword } from './api'
import { useSession } from './session'
import styles from './Auth.module.css'

/** Shared by the forced first-login screen and My Account. On success the server issues a fresh session. */
export function ChangePasswordForm({ onChanged }: { onChanged?: () => void }) {
  const t = useT()
  const { applySession } = useSession()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: (session) => {
      applySession(session)
      setCurrent('')
      setNext('')
      setConfirm('')
      setSubmitted(false)
      onChanged?.()
    },
  })

  const length = next.length
  const newError = !submitted ? undefined : length < 8 ? t('auth.password.tooShort') : length > 128 ? t('auth.password.tooLong') : undefined
  const confirmError = submitted && next !== confirm ? t('auth.password.mismatch') : undefined

  const apiError = mutation.error
  const wrongCurrent = apiError instanceof ApiError && apiError.status === 400
  const currentError = wrongCurrent ? t('auth.password.wrongCurrent') : undefined
  const generic = apiError && !wrongCurrent ? t('auth.password.generic') : null

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (length < 8 || length > 128 || next !== confirm || !current) return
    mutation.mutate()
  }

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <TextField label={t('auth.password.current')} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" error={currentError} dir="ltr" required />
      <TextField label={t('auth.password.new')} type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" hint={t('auth.password.hint')} error={newError} dir="ltr" required />
      <TextField label={t('auth.password.confirm')} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" error={confirmError} dir="ltr" required />
      {generic && (
        <p className={styles.alert} role="alert">
          <AlertCircle size={18} aria-hidden="true" /> {generic}
        </p>
      )}
      <div>
        <Button type="submit" loading={mutation.isPending}>{t('auth.password.submit')}</Button>
      </div>
    </form>
  )
}
