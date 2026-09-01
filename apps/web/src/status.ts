/**
 * Estados de pista, tomados del concepto de diseño.
 *
 * El estado no es una etiqueta decorativa: cambia el color y el grosor del
 * trazado, el costo de parar, y cómo se comporta el pelotón. Bajo Safety Car
 * los autos se agrupan; con bandera roja van a la parrilla.
 */

import type { TrackStatus } from './types'

export interface StatusSpec {
  id: TrackStatus
  label: string
  note: string
  /** Fondo de la barra de estado. */
  color: string
  /** Color de texto sobre ese fondo. */
  fg: string
  /** Costo de parar, en posiciones. */
  cost: string
  costNote: string
  /** El trazado se pinta con el color del estado. */
  stroke: string
  /** Y se ensancha: cuanto más grave el estado, más grueso. */
  width: number
  /** Separación objetivo entre autos, como fracción de vuelta. */
  spacing: number
}

export const STATUS: Record<TrackStatus, StatusSpec> = {
  GREEN: {
    id: 'GREEN',
    label: 'Pista verde',
    note: 'carrera en curso',
    color: '#35c46f',
    fg: '#0f0e0d',
    cost: '+2,0',
    costNote: 'pérdida 22,2 s (p25 19,0 · p75 26,3)',
    stroke: '#4a4644',
    width: 22,
    spacing: 0.055,
  },
  YELLOW: {
    id: 'YELLOW',
    label: 'Bandera amarilla',
    note: 'incidente en pista — prohibido adelantar',
    color: '#f5c518',
    fg: '#201e1d',
    cost: '+2,0',
    costNote: 'la parada sigue costando lo mismo',
    stroke: '#f5c518',
    width: 23,
    spacing: 0.05,
  },
  VSC: {
    id: 'VSC',
    label: 'VSC',
    note: 'virtual safety car — ritmo delta',
    color: '#f5c518',
    fg: '#201e1d',
    cost: '0,0',
    costNote: 'parar ahora no cuesta posiciones',
    stroke: '#f5c518',
    width: 24,
    // Los gaps quedan congelados: el pelotón no se estira ni se junta.
    spacing: 0.05,
  },
  SC: {
    id: 'SC',
    label: 'Safety car',
    note: 'pelotón agrupado, boxes abiertos',
    color: '#f5c518',
    fg: '#201e1d',
    cost: '0,0',
    costNote: 'parar ahora no cuesta posiciones',
    stroke: '#f5c518',
    width: 28,
    spacing: 0.018,
  },
  RED: {
    id: 'RED',
    label: 'Bandera roja',
    note: 'carrera detenida — cambio de goma libre en parrilla',
    color: '#ec3013',
    fg: '#f4f3f2',
    cost: '0,0',
    costNote: 'goma libre, la ventana se reinicia',
    stroke: '#ec3013',
    width: 26,
    spacing: 0.012,
  },
}

export const STATUS_ORDER: TrackStatus[] = ['GREEN', 'YELLOW', 'VSC', 'SC', 'RED']

/** Frase que describe qué está haciendo el pelotón, como en la transmisión. */
export function fieldNote(status: TrackStatus, bunched: boolean): string | null {
  switch (status) {
    case 'RED':
      return bunched
        ? 'Pelotón en parrilla · esperando relanzamiento'
        : 'Autos rodando a la parrilla · goma libre en boxes'
    case 'SC':
      return bunched
        ? 'Pelotón agrupado · rezagados recuperan su vuelta'
        : 'Pelotón agrupándose detrás del safety car'
    case 'VSC':
      return 'Gaps congelados · ritmo delta'
    case 'YELLOW':
      return 'Incidente en pista · prohibido adelantar'
    default:
      return null
  }
}
