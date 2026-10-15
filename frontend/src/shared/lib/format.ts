import type { Locale } from '../i18n/translate'

// Latin digits and the Gregorian calendar in both languages (ar-SA would default to the Hijri calendar).
const tag = (locale: Locale) => (locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB')

export function formatDateTime(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(tag(locale), { dateStyle: 'medium', timeStyle: 'short', calendar: 'gregory' }).format(new Date(iso))
}

export function formatDate(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(tag(locale), { dateStyle: 'medium', calendar: 'gregory' }).format(new Date(iso))
}

/** `<input type="datetime-local">` value (local wall time, no offset) → ISO string WITH offset (UTC "Z"), as the API requires. */
export function localInputToIso(value: string): string | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}
