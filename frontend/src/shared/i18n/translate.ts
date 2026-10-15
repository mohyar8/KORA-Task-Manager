import { en, type MessageKey } from './messages.en'
import { ar } from './messages.ar'

export type Locale = 'ar' | 'en'
export type Params = Record<string, string | number>

const dictionaries: Record<Locale, Record<MessageKey, string>> = { ar, en }

/** Looks up a key and replaces `{name}` placeholders. Falls back to English. */
export function translate(locale: Locale, key: MessageKey, params?: Params): string {
  let text = dictionaries[locale][key] ?? en[key]
  if (params) for (const [k, v] of Object.entries(params)) text = text.replaceAll(`{${k}}`, String(v))
  return text
}
