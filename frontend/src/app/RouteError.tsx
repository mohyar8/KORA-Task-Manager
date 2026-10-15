import { useRouteError } from 'react-router'
import { useT } from '@/shared/i18n/i18n'
import { Button, LinkButton } from '@/shared/ui/Button'
import { StateBlock } from '@/shared/ui/Feedback'
import { TriangleAlert } from 'lucide-react'

/** Last-resort screen for a render error or a failed page-chunk load (e.g. offline): recoverable, never blank. */
export function RouteError() {
  const t = useT()
  const error = useRouteError()
  if (import.meta.env.DEV) console.error(error)
  return (
    <StateBlock
      icon={<TriangleAlert size={32} />}
      title={t('state.error.title')}
      body={t('state.connection.body')}
      action={
        <>
          <Button onClick={() => window.location.reload()}>{t('common.retry')}</Button>
          <LinkButton to="/" variant="secondary">{t('common.backHome')}</LinkButton>
        </>
      }
    />
  )
}
