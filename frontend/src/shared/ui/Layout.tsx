import type { ReactNode } from 'react'
import styles from './Layout.module.css'

interface PageHeaderProps {
  title: string
  description?: string
  /** Page-specific primary actions; render only those the user may perform. */
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <h1 className={styles.title}>{title}</h1>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </header>
  )
}

/** Horizontal-scroll wrapper so dense tables never overflow the page (use inside a <table> parent). */
export function TableWrap({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className={styles.tableWrap} role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  )
}

/** A calm functional surface. Use only when content needs grouping. */
export function Card({ children }: { children: ReactNode }) {
  return <section className={styles.card}>{children}</section>
}
