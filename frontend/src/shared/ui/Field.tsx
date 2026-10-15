import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { AlertCircle } from 'lucide-react'
import styles from './Field.module.css'

interface ShellProps {
  label: string
  hint?: string
  error?: string
  required?: boolean
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode
}

/** Persistent label, hint and error text, wired to the control with aria attributes. */
function FieldShell({ label, hint, error, required, children }: ShellProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
        {required && <span aria-hidden="true" className={styles.required}> *</span>}
      </label>
      {children({ id, describedBy, invalid: !!error })}
      {hint && <p id={hintId} className={styles.hint}>{hint}</p>}
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          <AlertCircle size={16} aria-hidden="true" /> {error}
        </p>
      )}
    </div>
  )
}

type Common = { label: string; hint?: string; error?: string }

export function TextField({ label, hint, error, required, ...rest }: Common & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <input id={id} className={styles.control} aria-describedby={describedBy} aria-invalid={invalid || undefined} required={required} {...rest} />
      )}
    </FieldShell>
  )
}

export function TextAreaField({ label, hint, error, required, ...rest }: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <textarea id={id} className={`${styles.control} ${styles.textarea}`} aria-describedby={describedBy} aria-invalid={invalid || undefined} required={required} {...rest} />
      )}
    </FieldShell>
  )
}

export function SelectField({ label, hint, error, required, children, ...rest }: Common & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required}>
      {({ id, describedBy, invalid }) => (
        <select id={id} className={styles.control} aria-describedby={describedBy} aria-invalid={invalid || undefined} required={required} {...rest}>
          {children}
        </select>
      )}
    </FieldShell>
  )
}
