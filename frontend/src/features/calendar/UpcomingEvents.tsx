import { useState } from 'react'
import { Link } from 'react-router'
import { CalendarClock } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Chip, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { Card } from '@/shared/ui/Layout'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { useVisibleEvents } from './api'

/** Home block: the next scheduled events the caller can see. */
export function UpcomingEvents() {
  const { t, locale } = useI18n()
  const query = useVisibleEvents()
  const [now] = useState(() => Date.now())
  if (query.isPending) return <Skeleton lines={2} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const next = query.data.filter((e) => e.state === 'scheduled' && Date.parse(e.ends_at) >= now).sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)).slice(0, 4)
  return (
    <Card>
      <h2 style={{ fontSize: 'var(--text-lg)', marginBlockEnd: 'var(--space-4)' }}>{t('home.upcoming')}</h2>
      {next.length === 0 ? (
        <p style={{ color: 'var(--ui-muted)' }}>{t('home.upcoming.none')}</p>
      ) : (
        <RowList label={t('home.upcoming')}>
          {next.map((e, i) => (
            <Row
              key={e.id}
              index={i}
              to={`/calendar/${e.id}`}
              title={e.title}
              accent="navy"
              leading={<Avatar tone="navy" size={40}><CalendarClock size={20} aria-hidden="true" /></Avatar>}
              meta={<span>{formatDateTime(e.starts_at, locale)}</span>}
              trailing={<Chip tone="info">{t(`cal.type.${e.type}`)}</Chip>}
            />
          ))}
        </RowList>
      )}
      <p style={{ marginBlockStart: 'var(--space-4)' }}><Link to="/calendar">{t('home.upcoming.all')}</Link></p>
    </Card>
  )
}
