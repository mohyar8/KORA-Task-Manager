import { useState } from 'react'
import { Check, Copy, TriangleAlert } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Modal } from '@/shared/ui/Modal'
import styles from './members.module.css'

interface Props {
  /** null = closed. The password lives only in the caller's component state; it is never cached or stored. */
  secret: { name: string; username: string; password: string } | null
  onDone: () => void
}

/** Shows a temporary password exactly once (contract §8.2: returned only in the response). */
export function TemporaryPasswordDialog({ secret, onDone }: Props) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(secret?.password ?? '')
      setCopied(true)
    } catch {
      /* clipboard unavailable: the password is selectable on screen */
    }
  }
  const done = () => {
    setCopied(false)
    onDone()
  }

  return (
    <Modal
      open={!!secret}
      title={t('members.temp.title')}
      onClose={done}
      footer={<Button onClick={done}>{t('members.temp.done')}</Button>}
    >
      {secret && (
        <div className={styles.secret}>
          <p>{t('members.temp.body', { name: secret.name, username: secret.username })}</p>
          <div className={styles.passwordRow}>
            <code className={styles.password} data-testid="temporary-password">{secret.password}</code>
            <Button variant="secondary" onClick={copy}>
              {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
              {copied ? t('members.temp.copied') : t('members.temp.copy')}
            </Button>
          </div>
          <p className={styles.warning}>
            <TriangleAlert size={18} aria-hidden="true" /> {t('members.temp.warning')}
          </p>
        </div>
      )}
    </Modal>
  )
}
