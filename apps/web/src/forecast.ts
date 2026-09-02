/**
 * Pronóstico de batalla: en cuántas vueltas el de atrás queda a tiro.
 *
 * Es la otra mitad de lo que muestra la transmisión, y responde una pregunta
 * distinta de la del duelo de boxes. Aquel pregunta «¿conviene parar ahora?» y
 * sólo tiene sentido en ventana de parada. Este pregunta «¿lo va a alcanzar?»,
 * que se puede preguntar en cualquier momento de la carrera.
 *
 * El modelo usa las **mismas** cifras de desgaste que el undercut, así que las
 * dos tarjetas no pueden contradecirse: si el perseguidor recorta, recorta en
 * las dos. Lo que se recorta por vuelta es la diferencia de ritmo actual, y esa
 * diferencia se agranda sola, porque las gomas del que va adelante siguen
 * cayendo a su propio ritmo.
 *
 * Lo que el modelo **no** tiene: aire sucio. Un auto pegado al de adelante
 * pierde carga aerodinámica y deja de recortar, que es justamente por qué
 * adelantar es difícil. Por eso el pronóstico se corta en la zona de DRS y no
 * proyecta el adelantamiento en sí — eso lo dice el medidor de dificultad, que
 * está medido aparte.
 */

import { type CircuitOvertaking, overtakingAt } from './overtaking'
import type { DriverState } from './types'
import type { Timing } from './useField'

/** A un segundo se abre el DRS: de ahí para adentro ya es pelea, no persecución. */
export const STRIKE_S = 1.0

/** Más lejos que esto no es una batalla, son dos carreras distintas. */
const MAX_GAP_S = 12

/**
 * Último puesto que reparte puntos.
 *
 * Una pelea por el 14.º no cambia el resultado de nadie: los dos terminan con
 * cero. Se muestran sólo las que se dan dentro de la zona de puntos, que es
 * donde una posición vale algo.
 */
export const POINTS_POSITIONS = 10

/** Recorte por vuelta por debajo del cual se considera que no se acerca. */
const CLOSING_DEAD_ZONE = 0.01

export type BattleState = 'IN_RANGE' | 'CLOSING' | 'PULLING_AWAY'

export interface BattleForecast {
  chaser: string
  leader: string
  /** Puesto en disputa: el que ocupa el de adelante. */
  position: number
  gapNow: number
  /** Segundos por vuelta que recorta ahora. Negativo = se le escapa. */
  closingPerLap: number
  /** Vueltas hasta quedar a tiro, o `null` si no llega antes del final. */
  lapsToStrike: number | null
  state: BattleState
  /** Lo medido para este circuito: dificultad, tasa cruda, carreras y puesto. */
  overtaking: CircuitOvertaking
}

/**
 * Cuánto recorta el perseguidor en la vuelta número `ahead`, a partir de ahora.
 *
 * La diferencia de ritmo no es fija: cada vuelta los dos pierden un poco más
 * por desgaste, y lo que importa es cuánto más pierde uno que el otro.
 */
function closingOnLap(chaser: DriverState, leader: DriverState, ahead: number): number {
  const now = leader.degradationS - chaser.degradationS
  const growth = leader.degradationRate - chaser.degradationRate
  return now + growth * ahead
}

/**
 * Vueltas hasta quedar a menos de `STRIKE_S`, o `null` si no llega.
 *
 * Se acumula vuelta a vuelta en lugar de despejar la cuadrática porque el
 * recorte puede cambiar de signo en el medio —el perseguidor alcanza y después
 * se queda sin goma— y la fórmula cerrada devolvería una raíz que ya no
 * significa nada.
 */
function lapsToStrike(
  chaser: DriverState,
  leader: DriverState,
  gap: number,
  horizon: number,
): number | null {
  let remaining = gap
  for (let lap = 1; lap <= horizon; lap += 1) {
    remaining -= closingOnLap(chaser, leader, lap - 1)
    if (remaining <= STRIKE_S) return lap
  }
  return null
}

/**
 * Arma el pronóstico de un par.
 *
 * @param lapsRemaining Vueltas que quedan: más allá del final no hay pronóstico
 *   que dar, por más que la cuenta cierre.
 */
export function forecastBattle(
  chaser: DriverState,
  leader: DriverState,
  position: number,
  gapNow: number,
  lapsRemaining: number,
  circuit: string,
): BattleForecast {
  const closingPerLap = closingOnLap(chaser, leader, 0)
  const state: BattleState =
    gapNow <= STRIKE_S
      ? 'IN_RANGE'
      : closingPerLap > CLOSING_DEAD_ZONE
        ? 'CLOSING'
        : 'PULLING_AWAY'

  return {
    chaser: chaser.code,
    leader: leader.code,
    position,
    gapNow,
    closingPerLap,
    lapsToStrike:
      state === 'CLOSING' ? lapsToStrike(chaser, leader, gapNow, lapsRemaining) : null,
    state,
    overtaking: overtakingAt(circuit),
  }
}

/**
 * La batalla que vale la pena mirar, o `null` si no hay ninguna.
 *
 * Se prefiere la que se resuelve antes: una persecución que se define en tres
 * vueltas es noticia y una de treinta no. Los que ya están a tiro van primero,
 * porque eso ya no es pronóstico sino pelea.
 *
 * **No siempre hay batalla.** Un par que se abre, o uno que recorta tan despacio
 * que no llega antes de la bandera a cuadros, no es una pelea: es el orden de la
 * carrera. Tampoco lo es una pelea por el 14.º, donde los dos terminan con cero
 * puntos igual. Esos quedan afuera y la tarjeta no se muestra, como la
 * transmisión no pone el gráfico cuando no hay nada que anunciar.
 */
export function pickBattle(
  cars: DriverState[],
  timing: Timing,
  lapsRemaining: number,
  circuit: string,
  /**
   * Par que ya está en pantalla en el duelo de boxes, con la forma
   * `PERSEGUIDOR-LÍDER`. Se elige otro si lo hay: dos tarjetas sobre la misma
   * pelea ocupan el doble de lugar sin contar nada nuevo.
   */
  avoid?: string | null,
): BattleForecast | null {
  if (timing.formation) return null

  const found: BattleForecast[] = []
  for (let place = 1; place < timing.order.length; place += 1) {
    const chaser = cars[timing.order[place]]
    const leader = cars[timing.order[place - 1]]
    if (!chaser || !leader) continue

    // `place` es el puesto que ocupa el de adelante: el que está en disputa.
    if (place > POINTS_POSITIONS) break

    const gapNow = timing.gapAhead[timing.order[place]]
    if (gapNow == null || gapNow > MAX_GAP_S) continue

    found.push(forecastBattle(chaser, leader, place, gapNow, lapsRemaining, circuit))
  }

  const real = found.filter((b) => b.state === 'IN_RANGE' || b.lapsToStrike != null)
  if (real.length === 0) return null

  const sorted = real.sort((a, b) => rank(a) - rank(b))
  return sorted.find((b) => `${b.chaser}-${b.leader}` !== avoid) ?? sorted[0]
}

/** Orden de interés: a tiro primero, después por vueltas hasta el tiro. */
function rank(b: BattleForecast): number {
  if (b.state === 'IN_RANGE') return b.gapNow
  if (b.lapsToStrike != null) return 10 + b.lapsToStrike
  return 1000 + b.gapNow
}
