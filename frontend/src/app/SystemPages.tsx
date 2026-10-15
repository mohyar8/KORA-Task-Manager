import { FileQuestion, WifiOff } from 'lucide-react'
import { useT } from '@/shared/i18n/i18n'
import { AccessDenied, StateBlock } from '@/shared/ui/Feedback'
import { useHealth } from '@/shared/api/health'
import { Button, LinkButton } from '@/shared/ui/Button'

function HomeLink() {
  const t = useT()
  return <LinkButton to="/" variant="secondary">{t('common.backHome')}</LinkButton>
}

export function NotFoundPage() {
  const t = useT()
  return <StateBlock icon={<FileQuestion size={32} />} title={t('state.notFound.title')} body={t('state.notFound.body')} action={<HomeLink />} />
}

export function AccessDeniedPage() {
  return <AccessDenied action={<HomeLink />} />
}

export function ConnectionFailurePage() {
  const t = useT()
  const health = useHealth()
  const body = health.isPending ? t('state.connection.checking') : health.isError ? t('state.connection.down') : t('state.connection.up')
  return (
    <StateBlock
      icon={<WifiOff size={32} />}
      title={t('state.connection.title')}
      body={`${t('state.connection.body')} ${body}`}
      action={<Button onClick={() => window.location.reload()}>{t('common.retry')}</Button>}
    />
  )
}
