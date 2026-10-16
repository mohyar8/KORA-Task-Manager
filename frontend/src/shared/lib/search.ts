const normalize = (s: string) =>
  s
    .toLowerCase()
    .replace(/[\u064B-\u065F\u0670\u0640]/g, '')
    .replace(/[أإآٱ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه')

/** Every word typed must appear somewhere in the text, in any order, so "first last" finds "first middle last". */
export function matchesSearch(query: string, ...fields: (string | null | undefined)[]): boolean {
  const words = normalize(query).split(/\s+/).filter(Boolean)
  if (words.length === 0) return true
  const haystack = normalize(fields.filter(Boolean).join(' '))
  return words.every((w) => haystack.includes(w))
}
