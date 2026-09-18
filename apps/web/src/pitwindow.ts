/**
 * Estado de la ventana de parada, vuelta a vuelta.
 *
 * La ventana es **cuándo un auto PODRÍA parar**: el rango donde el modelo
 * proyecta que el cruce le conviene. La calcula `pit_window()` en
 * `apps/ml/src/boxbox_ml/insights.py` y entra a la vista como
 * `DriverState.pitWindow`.
 *
 * ## No es el plan, y la diferencia ya nos mordió una vez
 *
 * El **plan** es cuándo el auto VA A parar: la realización sorteada que la
 * simulación está ejecutando (`tyres.ts`). La torre ya las distingue —muestra
 * una o la otra según de dónde arranque la carrera, nunca las dos en la misma
 * columna— y esta tarjeta mantiene la misma línea:
 *
 *   ventana   cuándo podría. Proyección del modelo sobre el desgaste medido.
 *   plan      cuándo va a. Un sorteo concreto de esta carrera.
 *
 * Un auto puede tener la ventana abierta y no parar, o parar sin tenerla.
 *
 * ## Por qué hay autos sin ventana
 *
 * `null` casi siempre es un estado real y frecuente, no un hueco: si la goma
 * está plana o todavía mejorando no hay cruce que anticipar, y cerca de la
 * mitad de la parrilla está así a mitad de carrera. También queda en `null`
 * después de parar, porque la ventana que traía era para la parada que ya hizo.
 *
 * **Pero hay un caso en que sí es un hueco de dato**, y quien muestre esto
 * tiene que distinguirlo: corriendo desde la largada, `PRERACE_GRID` pone
 * `pitWindow: null` en los veintidós autos porque el export pre-carrera trae el
 * plan del algoritmo y **no incluye la salida de `pit_window()`**. Ahí el
 * modelo no dijo que no haya ventana: no se le preguntó.
 */

import type { DriverState } from './types'

export type WindowPhase = 'none' | 'pending' | 'open' | 'closed'

export interface WindowState {
  phase: WindowPhase
  /** El rango proyectado, o `null` si no hay ninguno. */
  window: { opensLap: number; closesLap: number } | null
  /**
   * Vueltas que faltan para que abra (`pending`), que quedan antes de que
   * cierre (`open`), o que pasaron desde que cerró (`closed`). `null` en
   * `none`, que es donde no hay nada que contar.
   */
  laps: number | null
}

/** En qué punto de su ventana está este auto en esta vuelta. */
export function windowState(driver: DriverState, lap: number): WindowState {
  const w = driver.pitWindow
  if (!w) return { phase: 'none', window: null, laps: null }
  if (lap < w.opensLap) return { phase: 'pending', window: w, laps: w.opensLap - lap }
  if (lap > w.closesLap) return { phase: 'closed', window: w, laps: lap - w.closesLap }
  return { phase: 'open', window: w, laps: w.closesLap - lap }
}

/** ¿La ventana de este auto está abierta en esta vuelta? */
export function windowOpen(driver: DriverState, lap: number): boolean {
  const w = driver.pitWindow
  return w !== null && w !== undefined && lap >= w.opensLap && lap <= w.closesLap
}

/**
 * Cuántos autos en pista tienen la ventana abierta ahora.
 *
 * Es el contexto que le falta al dato de un auto solo: una ventana abierta
 * significa una cosa cuando es la única y otra cuando la mitad del pelotón
 * está en la misma, porque ahí el pit lane se congestiona y la decisión pasa a
 * ser cuándo, no si.
 */
export function openCount(cars: DriverState[], lap: number): number {
  return cars.filter((c) => {
    const out = c.retiredOnLap != null && lap >= c.retiredOnLap
    return !out && windowOpen(c, lap)
  }).length
}
