import { useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog } from '@/shared/ui/Modal'
import { Tabs } from '@/shared/ui/Tabs'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { Bell, CalendarDays, ClipboardCheck, Megaphone, MessageSquare, RefreshCw } from 'lucide-react'
import {
  CATEGORIES, sourceLink, useDeleteAll, useDeleteNotification, useMarkRead, useNotifications, useOpenNotification, usePreferences, useReadAll, useSavePreferences,
  type AppNotification, type NotificationCategory,
} from './api'
import styles from './notifications.module.css'

const categoryIcon: Record<NotificationCategory, ReactNode> = {
  task_assignment: <ClipboardCheck size={22} aria-hidden="true" />,
  task_update: <RefreshCw size={22} aria-hidden="true" />,
  task_comment: <MessageSquare size={22} aria-hidden="true" />,
  announcement_new: <Megaphone size={22} aria-hidden="true" />,
  announcement_change: <Bell size={22} aria-hidden="true" />,
  calendar_event: <CalendarDays size={22} aria-hidden="true" />,
}

export function NotificationsPage() {
  const { t } = useI18n()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'preferences' ? 'preferences' : 'list'
  return (
    <>
      <PageHeader title={t('notif.title')} />
      <Tabs
        label={t('notif.tabs.label')}
        active={tab}
        onChange={(id) => setParams(id === 'list' ? {} : { tab: id }, { replace: true })}
        tabs={[{ id: 'list', label: t('notif.tab.list') }, { id: 'preferences', label: t('notif.tab.prefs') }]}
      >
        {tab === 'list' ? <NotificationList /> : <PreferencesPanel />}
      </Tabs>
    </>
  )
}

function NotificationList() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const toast = useToast()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const query = useNotifications(unreadOnly)
  const markRead = useMarkRead()
  const reopen = useOpenNotification()
  const readAll = useReadAll()
  const del = useDeleteNotification()
  const delAll = useDeleteAll()
  const [confirmAll, setConfirmAll] = useState(false)

  // Re-check the notification first: if the reader lost access meanwhile it comes back redacted and we stay here.
  const open = (n: AppNotification) =>
    reopen.mutate(n.id, {
      onSuccess: (fresh) => {
        const link = sourceLink(fresh)
        if (fresh.redacted || !link) return
        if (!fresh.read_at) markRead.mutate(fresh.id)
        navigate(link)
      },
    })

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <label className={styles.check}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> {t('notif.unreadOnly')}
        </label>
        <div className={styles.actions}>
          <Button variant="secondary" loading={readAll.isPending} onClick={() => readAll.mutate()}>{t('notif.readAll')}</Button>
          <Button variant="ghost" onClick={() => { delAll.reset(); setConfirmAll(true) }}>{t('notif.deleteAll')}</Button>
        </div>
      </div>

      {query.isPending && <Skeleton lines={4} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && query.data.length === 0 && <EmptyState title={unreadOnly ? t('notif.emptyUnread') : t('notif.empty')} />}
      {query.data && query.data.length > 0 && (
        <RowList label={t('notif.title')}>
          {query.data.map((n, i) => (
            <Row
              key={n.id}
              index={i}
              accent={n.read_at ? undefined : 'coral'}
              muted={!!n.read_at}
              leading={<Avatar tone={n.read_at ? 'gray' : 'fuchsia'}>{categoryIcon[n.category]}</Avatar>}
              title={<span className={n.redacted ? styles.redacted : undefined}>{n.redacted ? t('notif.redacted') : (n.summary ?? t('notif.noSummary'))}</span>}
              meta={
                <>
                  <Chip>{t(`notif.category.${n.category}`)}</Chip>
                  {!n.read_at && <Chip tone="info">{t('notif.unread')}</Chip>}
                  <span>{formatDateTime(n.created_at, locale)}</span>
                </>
              }
              trailing={
                <>
                  {!n.redacted && sourceLink(n) && <Button variant="secondary" onClick={() => open(n)}>{t('notif.open')}</Button>}
                  {!n.read_at && <Button variant="ghost" onClick={() => markRead.mutate(n.id)}>{t('notif.markRead')}</Button>}
                  <Button variant="ghost" onClick={() => del.mutate(n.id)}>{t('notif.delete')}</Button>
                </>
              }
            />
          ))}
        </RowList>
      )}

      <ConfirmDialog
        open={confirmAll}
        title={t('notif.deleteAll.title')}
        body={<div className={styles.stack}><p>{t('notif.deleteAll.body')}</p><InlineError error={delAll.error} /></div>}
        confirmLabel={t('notif.deleteAll')}
        danger
        loading={delAll.isPending}
        onConfirm={() => delAll.mutate(undefined, { onSuccess: () => { setConfirmAll(false); toast(t('notif.deleteAll')) } })}
        onClose={() => setConfirmAll(false)}
      />
    </div>
  )
}

function PreferencesPanel() {
  const { t } = useI18n()
  const toast = useToast()
  const query = usePreferences()
  const save = useSavePreferences()

  if (query.isPending) return <Skeleton lines={4} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  const change = (category: NotificationCategory, value: boolean) =>
    save.mutate({ [category]: value }, { onSuccess: () => toast(t('notif.prefs.saved')) })

  return (
    <div className={styles.stack}>
      <p>{t('notif.prefs.description')}</p>
      <ul className={styles.list}>
        {CATEGORIES.map((c) => (
          <li key={c} className={styles.item}>
            <label className={styles.check}>
              <input type="checkbox" checked={query.data[c]} disabled={save.isPending} onChange={(e) => change(c, e.target.checked)} /> {t(`notif.category.${c}`)}
            </label>
          </li>
        ))}
      </ul>
      <InlineError error={save.error} />
    </div>
  )
}
