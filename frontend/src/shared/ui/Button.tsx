import type { ButtonHTMLAttributes } from 'react'
import { Link, type LinkProps } from 'react-router'
import { Loader2 } from 'lucide-react'
import styles from './Button.module.css'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  loading?: boolean
}

export function Button({ variant = 'primary', loading = false, disabled, className, children, type = 'button', ...rest }: Props) {
  return (
    <button
      type={type}
      className={[styles.button, styles[variant], className].filter(Boolean).join(' ')}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Loader2 className={styles.spin} size={18} aria-hidden="true" />}
      {children}
    </button>
  )
}

/** A router link that looks like a button (never nest a <button> inside a link). */
export function LinkButton({ variant = 'primary', className, ...rest }: LinkProps & { variant?: Props['variant'] }) {
  return <Link className={[styles.button, styles[variant], className].filter(Boolean).join(' ')} {...rest} />
}
