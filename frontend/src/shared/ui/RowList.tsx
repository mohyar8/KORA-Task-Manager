import type { ReactNode } from 'react'
import { Link } from 'react-router'
import styles from './RowList.module.css'

export type RowTone = 'navy' | 'fuchsia' | 'coral' | 'green' | 'gray'

/** A round gradient badge with an initial or an icon: the leading mark of a row. */
export function Avatar({ children, tone = 'navy', size = 44 }: { children: ReactNode; tone?: RowTone; size?: number }) {
  return (
    <span className={`${styles.avatar} ${styles[tone]}`} style={{ inlineSize: size, blockSize: size }} aria-hidden="true">
      {children}
    </span>
  )
}

export function RowList({ children, label }: { children: ReactNode; label: string }) {
  return <ul className={styles.list} aria-label={label}>{children}</ul>
}

interface RowProps {
  leading?: ReactNode
  title: ReactNode
  /** Where the title links to; omit for a plain row. */
  to?: string
  /** Secondary line (chips, dates, names). */
  meta?: ReactNode
  /** Right-hand (end) side: status, actions. */
  trailing?: ReactNode
  /** Colored edge that reflects the row's state. */
  accent?: RowTone
  muted?: boolean
  index?: number
}

export function Row({ leading, title, to, meta, trailing, accent, muted, index = 0 }: RowProps) {
  return (
    <li
      className={`${styles.row} ${accent ? styles[`edge_${accent}`] : ''} ${muted ? styles.muted : ''}`}
      style={{ animationDelay: `${Math.min(index, 12) * 35}ms` }}
    >
      {leading}
      <div className={styles.main}>
        <div className={styles.title}>{to ? <Link to={to} className={styles.titleLink}>{title}</Link> : title}</div>
        {meta && <div className={styles.meta}>{meta}</div>}
      </div>
      {trailing && <div className={styles.trailing}>{trailing}</div>}
    </li>
  )
}
