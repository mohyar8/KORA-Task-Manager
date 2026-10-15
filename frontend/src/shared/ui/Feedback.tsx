import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Inbox, Info, WifiOff, ShieldAlert } from 'lucide-react'
import { ApiError, formatDetail } from '../api/http'
import { useT } from '../i18n/i18n'
import { Button } from './Button'
import styles from './Feedback.module.css'

/* ---------- Chip: only for real status/category meaning ---------- */
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
const toneIcon = { neutral: null, info: Info, success: CheckCircle2, warning: AlertTriangle, danger: AlertTriangle } as const

export function Chip({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  const Icon = toneIcon[tone]
  return (
    <span className={`${styles.chip} ${styles[tone]}`}>
      {Icon && <Icon size={14} aria-hidden="true" />}
      {children}
    </span>
  )
}

/* ---------- Loading ---------- */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  const t = useT()
  return (
    <div role="status" aria-live="polite" className={styles.skeleton}>
      <span className="visually-hidden">{t('common.loading')}</span>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={styles.skeletonLine} style={{ inlineSize: `${100 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  )
}

/* ---------- Empty / error blocks ---------- */
interface BlockProps {
  icon?: ReactNode
  title: string
  body?: ReactNode
  action?: ReactNode
}

export function StateBlock({ icon, title, body, action }: BlockProps) {
  return (
    <div className={styles.block}>
      {icon && <div className={styles.blockIcon} aria-hidden="true">{icon}</div>}
      <h2 className={styles.blockTitle}>{title}</h2>
      {body && <p className={styles.blockBody}>{body}</p>}
      {action && <div className={styles.blockAction}>{action}</div>}
    </div>
  )
}

export function EmptyState({ title, body, action }: Omit<BlockProps, 'icon'>) {
  return <StateBlock icon={<Inbox size={32} />} title={title} body={body} action={action} />
}

export function AccessDenied({ action }: { action?: ReactNode }) {
  const t = useT()
  return <StateBlock icon={<ShieldAlert size={32} />} title={t('state.accessDenied.title')} body={t('state.accessDenied.body')} action={action} />
}

/** Maps an error to the right shared state: connection failure, access denied, or a generic message. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT()
  const retry = onRetry && <Button variant="secondary" onClick={onRetry}>{t('common.retry')}</Button>
  if (error instanceof ApiError && error.status === 0) {
    return <StateBlock icon={<WifiOff size={32} />} title={t('state.connection.title')} body={t('state.connection.body')} action={retry} />
  }
  if (error instanceof ApiError && error.status === 403) {
    return <AccessDenied />
  }
  return (
    <StateBlock
      icon={<AlertTriangle size={32} />}
      title={t('state.error.title')}
      body={error instanceof Error ? error.message : undefined}
      action={retry}
    />
  )
}

/** Inline alert for a failed action (mutation) inside a form or dialog. Server business-rule text is shown as-is. */
export function InlineError({ error }: { error: unknown }) {
  const t = useT()
  if (!error) return null
  let text: string
  if (error instanceof ApiError && error.status === 0) text = t('state.connection.body')
  else if (error instanceof ApiError && error.status === 403) text = t('state.accessDenied.body')
  else if (error instanceof ApiError) text = formatDetail(error.detail) || t('state.error.title')
  else text = t('state.error.title')
  return (
    <p className={styles.inlineError} role="alert">
      <AlertTriangle size={18} aria-hidden="true" /> {text}
    </p>
  )
}

/* ---------- Toasts (live region) ---------- */
interface ToastItem { id: number; tone: 'success' | 'danger' | 'info'; message: string }
const ToastContext = createContext<((message: string, tone?: ToastItem['tone']) => void) | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const show = useCallback((message: string, tone: ToastItem['tone'] = 'success') => {
    const id = Date.now() + Math.random()
    setItems((prev) => [...prev, { id, tone, message }])
    setTimeout(() => setItems((prev) => prev.filter((i) => i.id !== id)), 6000)
  }, [])
  const value = useMemo(() => show, [show])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className={styles.toasts} role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`${styles.toast} ${styles[`toast_${i.tone}`]}`}>{i.message}</div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
