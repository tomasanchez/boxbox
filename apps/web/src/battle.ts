/**
 * Modelo de undercut, en vivo.
 *
 * Es el mismo cálculo que `apps/ml/src/boxbox_ml/insights.py`, portado para
 * poder recalcularlo con el intervalo que va marcando la simulación en lugar de
 * dejarlo clavado en el valor medido.
 *
 * La cuenta: los dos autos pagan la misma pérdida de boxes, así que **se
 * cancela** y el duelo lo decide el ritmo durante las vueltas de respuesta. El
 * perseguidor recupera la degradación que traía acumulada; el líder sigue
 * perdiendo a su ritmo actual, y esa pérdida crece vuelta a vuelta.
 *
 * La probabilidad sale de la dispersión medida de la pérdida de boxes (mediana
 * 22,2 s, p25 19,0, p75 26,3) y del ruido de ritmo. En Python se resuelve por
 * Monte Carlo; acá se integra la **misma** distribución sobre una grilla de
 * cuantiles, que da el mismo número sin depender de un generador aleatorio y se
 * puede recalcular varias veces por segundo.
 */

import type { DriverState, StrategyBattle, Verdict } from './types'
import type { Timing } from './useField'

/**
 * Desvío de la pérdida de boxes respecto de su mediana, en segundos.
 *
 * Los dos autos paran, así que el nivel de pérdida se cancela y lo que queda es
 * cuánto se aparta **esta** parada de la habitual. Se modela con la triangular
 * que arman los cuartiles medidos: asimétrica hacia la derecha, porque una
 * parada puede salir muy mal —tráfico, una rueda trabada— pero no puede salir
 * mucho mejor que perfecta.
 */
const PIT_DELTA = { min: 19.0 - 22.2, mode: 0, max: 26.3 - 22.2 }

/** Desvío del ritmo por vuelta, en segundos. */
const PACE_NOISE = 0.15

/** Nodos para integrar la triangular. 64 alcanza: el error queda bajo 0,5 pp. */
const NODES = 64

/** Aproximación de la función de distribución normal acumulada. */
function normalCdf(z: number): number {
  // Zelen & Severo: error por debajo de 7,5e-8, de sobra para un porcentaje.
  const t = 1 / (1 + 0.2316419 * Math.abs(z))
  const d = 0.3989422804014327 * Math.exp((-z * z) / 2)
  const p =
    d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return z > 0 ? 1 - p : p
}

/** Inversa de la triangular, para muestrear por cuantiles en vez de al azar. */
function triangularQuantile(u: number): number {
  const { min: a, mode: c, max: b } = PIT_DELTA
  const split = (c - a) / (b - a)
  return u < split
    ? a + Math.sqrt(u * (b - a) * (c - a))
    : b - Math.sqrt((1 - u) * (b - a) * (b - c))
}

/**
 * Cuantiles equiespaciados de la triangular, calculados una sola vez.
 *
 * Estratificar en lugar de sortear elimina el ruido de muestreo: con la carrera
 * corriendo, dos cuadros seguidos con el mismo intervalo tienen que dar el
 * mismo porcentaje, y con Monte Carlo el número temblaría solo.
 */
const PIT_NODES = Array.from({ length: NODES }, (_, i) => triangularQuantile((i + 0.5) / NODES))

/** Segundos que el perseguidor recupera sobre el líder en `laps` vueltas. */
export function undercutGain(chaser: DriverState, leader: DriverState, laps: number): number {
  if (laps <= 0) return 0
  const recovered = laps * Math.max(chaser.degradationS, 0)
  // La pérdida del líder se acumula: 1 + 2 + ... + laps.
  const growing = Math.max(leader.degradationRate, 0) * ((laps * (laps + 1)) / 2)
  return recovered + growing
}

/** Veredicto según la probabilidad, nunca según el gap proyectado. */
export function verdictFor(probability: number): Verdict {
  if (probability >= 0.65) return 'SALE_ADELANTE'
  if (probability <= 0.35) return 'SIGUE_ATRAS'
  return 'CARA_O_CRUZ'
}

/**
 * Resuelve el duelo con el intervalo actual.
 *
 * @param gapNow Intervalo en segundos que marca la simulación ahora mismo.
 */
export function solveBattle(
  chaser: DriverState,
  leader: DriverState,
  gapNow: number,
  responseLaps = 2,
): StrategyBattle {
  const gain = undercutGain(chaser, leader, responseLaps)
  const gapAfter = gapNow - gain

  // El undercut sale si la parada más el ritmo cierran el gap proyectado. Se
  // integra el ruido de ritmo —normal— sobre cada nodo de la pérdida de boxes.
  const sd = Math.max(PACE_NOISE * responseLaps, 1e-6)
  let probability = 0
  for (const delta of PIT_NODES) {
    probability += normalCdf(-(gapAfter + delta) / sd)
  }
  probability /= PIT_NODES.length

  return {
    chaser: chaser.code,
    leader: leader.code,
    gapNow,
    responseLaps,
    perLapGain: gain / responseLaps,
    gapAfter,
    probability,
    verdict: verdictFor(probability),
  }
}

/** Cuántos duelos se ofrecen a la vez. */
const MAX_BATTLES = 3

/** Un undercut deja de ser noticia más allá de este intervalo, en segundos. */
export const IN_RANGE_S = 2.5

/**
 * Vueltas de anticipación con las que se empieza a mirar un duelo.
 *
 * La ventana no se abre de golpe: conviene ver venir la decisión unas vueltas
 * antes de que el cruce se dé, que es cuando el muro la discute.
 */
export const WINDOW_LEAD = 3

/** ¿Este auto está en ventana de parada, o entrando? */
export function nearPitWindow(driver: DriverState, lap: number): boolean {
  const w = driver.pitWindow
  if (!w) return false
  return lap >= w.opensLap - WINDOW_LEAD && lap <= w.closesLap
}

/** Por qué no hay ningún duelo para mostrar. `null` cuando sí lo hay. */
export type NoBattleReason = 'formation' | 'no-window' | 'no-one-close'

/**
 * Duelos vivos, tomados del orden en pista de la simulación.
 *
 * Se miran los pares **contiguos** —el que va justo detrás contra el que va
 * justo adelante—, que son los que la transmisión levanta, y se ordenan por
 * cercanía.
 *
 * Hacen falta **dos** condiciones, no una. Que estén cerca no alcanza: el
 * undercut es adelantar parando antes, así que sólo tiene sentido preguntarlo
 * cuando el perseguidor está en su ventana de parada o entrando. Un auto que
 * recién cambió gomas, o que no tiene ventana proyectable porque su desgaste
 * está plano, no va a parar por más pegado que vaya; mostrar el duelo ahí es
 * ofrecer una jugada que nadie va a hacer.
 *
 * Con el pelotón formado no se devuelve nada: parados en la parrilla los
 * intervalos son el largo de los cajones, no una diferencia de ritmo.
 */
export function liveBattles(cars: DriverState[], timing: Timing, lap: number): StrategyBattle[] {
  if (timing.formation) return []

  const found: StrategyBattle[] = []
  for (let place = 1; place < timing.order.length; place += 1) {
    const chaser = cars[timing.order[place]]
    const leader = cars[timing.order[place - 1]]
    if (!chaser || !leader) continue
    if (!nearPitWindow(chaser, lap)) continue

    const gapNow = timing.gapAhead[timing.order[place]]
    if (gapNow == null || gapNow > IN_RANGE_S) continue

    found.push({ ...solveBattle(chaser, leader, gapNow), chaserWindow: chaser.pitWindow })
  }

  return found.sort((a, b) => a.gapNow - b.gapNow).slice(0, MAX_BATTLES)
}

/**
 * Cuál de las dos condiciones falló, para poder decirlo en vez de dejar el
 * hueco mudo. Sin esto no se distingue «nadie va a parar» de «nadie alcanza».
 */
export function noBattleReason(cars: DriverState[], timing: Timing, lap: number): NoBattleReason {
  if (timing.formation) return 'formation'
  const anyWindow = timing.order.some((i) => cars[i] && nearPitWindow(cars[i], lap))
  return anyWindow ? 'no-one-close' : 'no-window'
}

/** Identidad de un duelo, estable mientras el par siga existiendo. */
export function battleKey(battle: StrategyBattle): string {
  return `${battle.chaser}-${battle.leader}`
}
