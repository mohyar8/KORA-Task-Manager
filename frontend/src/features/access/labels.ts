import { en, type MessageKey } from '@/shared/i18n/messages.en'

type T = (key: MessageKey) => string

// Enum value → localized label; a value outside the known enum is shown raw (never hidden).
const make = (prefix: string) => (t: T, value: string) => {
  const key = `${prefix}.${value}`
  return key in en ? t(key as MessageKey) : value
}

export const permissionLabel = make('perm')
export const roleLabel = make('role')
export const unitKindLabel = make('unit.kind')
export const decisionLabel = make('decision')
