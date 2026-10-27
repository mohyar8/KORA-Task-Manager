// A calm, stable colour per team (hash of its id), so a team looks the same everywhere.
const PALETTE = ['#5d74cc', '#b866c0', '#e0675a', '#4ea649', '#d08a2c', '#2f9fb0']

export function teamColor(unitId: string): string {
  let h = 0
  for (const ch of unitId) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return PALETTE[h % PALETTE.length]
}
