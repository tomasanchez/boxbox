/**
 * Cuánto tarda un auto dentro del pit lane. Medido, no inventado.
 *
 * La transmisión muestra un recuadro «IN PIT» con **dos** números: el tiempo
 * detenido —los dos segundos y medio con el auto en los gatos— y el total
 * perdido en el pit lane. Acá sólo se puede sostener uno de los dos.
 *
 * ## Lo que NO está y por lo tanto no se muestra
 *
 * El **tiempo detenido no se puede medir con estos datos**. FastF1 expone
 * `PitInTime` y `PitOutTime` y nada entre medio, así que los segundos parado no
 * se pueden separar del recorrido por el carril. La televisión lo muestra
 * porque tiene su propio cronometraje; nosotros no lo tenemos, y sería el
 * número más visible del recuadro. Se dice que falta en lugar de aproximarlo.
 *
 * ## Lo que sí está medido
 *
 * El **tránsito**: de la línea de entrada del pit lane a la de salida, reloj
 * contra reloj. Medido con `apps/ml/scripts/pit_lane_time.py` sobre las 14
 * carreras de 2026 — 494 paradas, 290 de ellas en verde.
 *
 * ## Tránsito y «pérdida de boxes» NO son lo mismo
 *
 * Y hay que decirlo justo porque el número se parece: el tránsito en verde da
 * mediana 23,0 s y la pérdida de boxes que usa el simulador da 22,6. **Se
 * parecen por casualidad.** Miden cosas distintas sobre ventanas distintas:
 *
 *   tránsito   reloj, de la línea de entrada a la de salida del carril.
 *
 *   pérdida    se mide sobre **dos vueltas** —la de entrada y la de salida—
 *              contra la mediana del campo en esas mismas dos vueltas, así que
 *              incluye la vuelta de entrada levantando el pie y la de salida
 *              con la goma fría, y descuenta lo que el auto habría tardado
 *              igual en recorrer ese tramo.
 *
 * El recuadro muestra los dos y los rotula distinto. Confundirlos es fácil, y
 * por eso está escrito acá y también en pantalla.
 */

import { RACE } from './data'
import type { PitStop } from './tyres'

/**
 * Tránsito por el pit lane en verde, en segundos, sobre las 290 paradas en
 * verde de 2026. Es el agregado: el número que manda es el del circuito.
 */
export const TRANSIT_GREEN = {
  p10: 18.3,
  p25: 21.66,
  median: 22.96,
  p75: 25.67,
  p90: 31.35,
  stops: 290,
  races: 14,
} as const

/**
 * Mediana del tránsito por circuito, en segundos, y sobre cuántas paradas.
 *
 * Es la cantidad por circuito más fácil de justificar de todo el proyecto: no
 * depende del auto ni del año, depende de cuán largo es el carril. Entre el más
 * corto —Zandvoort, 18,0 s— y el más largo —Madrid, 31,4— hay 13,4 s.
 *
 * Las claves son el `Location` del evento en FastF1, que es lo que usa
 * `RaceContext.circuit`.
 */
export const TRANSIT_BY_CIRCUIT: Record<string, { median: number; stops: number }> = {
  Zandvoort: { median: 18.0, stops: 38 },
  Melbourne: { median: 19.34, stops: 9 },
  Spielberg: { median: 21.61, stops: 34 },
  Budapest: { median: 22.02, stops: 37 },
  Barcelona: { median: 22.66, stops: 38 },
  'Miami Gardens': { median: 23.15, stops: 20 },
  Shanghai: { median: 23.29, stops: 10 },
  Suzuka: { median: 24.09, stops: 14 },
  'Spa-Francorchamps': { median: 24.79, stops: 10 },
  Montréal: { median: 24.98, stops: 17 },
  'Monte Carlo': { median: 25.24, stops: 22 },
  Monza: { median: 28.73, stops: 2 },
  Silverstone: { median: 30.04, stops: 25 },
  Madrid: { median: 31.41, stops: 14 },
}

export interface TransitStat {
  median: number
  stops: number
  /** `false` cuando se cae al agregado porque el circuito no está medido. */
  ownCircuit: boolean
}

/**
 * Tránsito medido del circuito de la carrera.
 *
 * Si el circuito no estuviera medido se cae al agregado en verde **y lo
 * declara**, para que la pantalla no haga pasar un promedio de catorce
 * circuitos por una medición de éste.
 */
export function transitFor(circuit: string): TransitStat {
  const own = TRANSIT_BY_CIRCUIT[circuit]
  if (own) return { ...own, ownCircuit: true }
  return { median: TRANSIT_GREEN.median, stops: TRANSIT_GREEN.stops, ownCircuit: false }
}

/** El tránsito del escenario que la vista está mostrando. */
export const TRANSIT = transitFor(RACE.circuit)

/** Un auto detenido en el pit lane, con la parada que está haciendo. */
export interface InPitCar {
  index: number
  code: string
  teamColor: string
  /**
   * La parada que está sirviendo, si se conoce el plan sorteado.
   *
   * `null` es un estado real: el recuadro puede aparecer sin que haya un plan
   * cargado para ese auto, y entonces se muestra el tránsito medido y nada más.
   * Inventarle una pérdida sería agregar el único número que no tenemos.
   */
  stop: PitStop | null
}

/**
 * Quién está en boxes ahora mismo.
 *
 * `inPit` lo publica la simulación: es el auto que ya llegó a la línea y
 * todavía debe avance, o sea el que está efectivamente detenido en el carril.
 * La parada que sirve es la última de su plan cuya vuelta ya pasó.
 */
export function inPitNow(
  cars: { code: string; teamColor: string }[],
  inPit: boolean[],
  plans: PitStop[][] | null,
  lap: number,
): InPitCar[] {
  const found: InPitCar[] = []
  for (let i = 0; i < cars.length; i += 1) {
    if (!inPit[i]) continue
    const made = plans?.[i]?.filter((s) => s.lap <= lap) ?? []
    found.push({
      index: i,
      code: cars[i].code,
      teamColor: cars[i].teamColor,
      stop: made.length > 0 ? made[made.length - 1] : null,
    })
  }
  return found
}
