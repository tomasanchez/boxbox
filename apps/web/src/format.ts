/** Formato numérico en castellano: coma decimal y signo explícito. */

export function fmt(value: number, decimals = 2, signed = false): string {
  const text = Math.abs(value).toFixed(decimals).replace('.', ',')
  if (!signed) return value < 0 ? `−${text}` : text
  return value < 0 ? `−${text}` : `+${text}`
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}
