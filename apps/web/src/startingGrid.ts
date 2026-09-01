/**
 * Parrilla de salida real de 2026 R12 Zandvoort.
 *
 * No coincide con el orden de carrera en la vuelta 30: NOR largó primero, RUS
 * segundo y ANT tercero, y para la vuelta 30 ANT ya lideraba. Por eso la grilla
 * necesita su propio dato y no se puede derivar de las posiciones actuales.
 *
 * Sale de `GridPosition` en el resultado oficial, que ya contempla sanciones.
 */
export const STARTING_GRID: string[] = [
  'NOR', 'RUS', 'ANT', 'PIA', 'HAM', 'LEC', 'VER', 'LAW', 'BOR', 'LIN', 'GAS', 'TSU', 'HUL',
  'COL', 'OCO', 'ALB', 'SAI', 'ALO', 'STR', 'BEA', 'BOT', 'PER',
]
