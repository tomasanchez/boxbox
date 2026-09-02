/**
 * Desgaste probabilístico.
 *
 * Hasta acá cada auto corría con una cifra de degradación fija, así que dos
 * autos con la misma goma andaban **exactamente** igual para siempre y los
 * intervalos evolucionaban sobre rieles. Las carreras no son así, y esto mide
 * por cuánto no lo son.
 *
 * Son dos ruidos distintos, y la diferencia importa:
 *
 *   ruido de vuelta   se sortea **cada vuelta**. Es lo que queda después de
 *                     descontar desgaste y combustible: tráfico, viento, una
 *                     entrada ancha. Desvío medido: **0,457 s**, sobre 4.407
 *                     tandas. Es lo que impide que dos autos iguales anden
 *                     igual, pero no acumula: se olvida al final de la vuelta.
 *
 *   ritmo de caída    se sortea **una vez por tanda**. Dos autos con el mismo
 *                     compuesto no lo gastan al mismo ritmo — posición en pista,
 *                     manejo, cómo se preparó el juego. Esto sí acumula, y es lo
 *                     que convierte una proyección en una distribución.
 *
 * El dato incómodo de la medición: en 2026 el desvío del ritmo de caída
 * (0,069 s/vuelta en duro, 0,112 en medio, 0,178 en blando) es **más grande que
 * la mediana del ritmo mismo** (≈0,045 en los tres). O sea que cuánto va a
 * gastar una tanda determinada es, en buena medida, impredecible. No es un
 * defecto de la medición: es el motivo por el que este sistema tiene que dar
 * distribuciones y no un número.
 *
 * Medido con `apps/ml/scripts/pace_noise.py`; ver
 * `docs/research/pace-noise.md`.
 */

import type { Compound, DriverState } from './types'

/** Desvío del ritmo de una vuelta, en segundos. Mediana de 4.407 tandas. */
export const LAP_NOISE_S = 0.457

/**
 * Desvío del ritmo de caída entre tandas del mismo compuesto, en s/vuelta.
 * Medido sobre 2026, que es la temporada que corre el simulador.
 */
export const RATE_SD_S: Record<Compound, number> = {
  SOFT: 0.1776,
  MEDIUM: 0.1124,
  HARD: 0.0686,
  // Mojados: 201 y 17 tandas, muy pocas para separarlas. Se usa la del blando,
  // que es la más dispersa de las secas, y queda anotado que es un préstamo.
  INTERMEDIATE: 0.1776,
  WET: 0.1776,
}

/**
 * Ruido reproducible.
 *
 * Se sortea a partir de `(auto, vuelta, semilla)` en vez de guardar el estado de
 * un generador. Así la vuelta 40 da lo mismo se llegue reproduciendo desde la 30
 * o saltando con el botón, que es lo que uno espera de una carrera: no se
 * reescribe sola cuando la volvés a mirar.
 */
function hash(...parts: number[]): number {
  let h = 0x811c9dc5
  for (const part of parts) {
    h ^= Math.imul(part | 0, 0x01000193)
    h = Math.imul(h ^ (h >>> 15), 0x2545f491)
  }
  return (h >>> 0) / 0x100000000
}

/** Normal estándar por Box-Muller, con dos uniformes derivadas del mismo hash. */
function gaussian(...parts: number[]): number {
  const u = Math.max(hash(...parts), 1e-9)
  const v = hash(...parts, 0x9e37)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

/** Semilla por defecto. Cambiarla es, en chiquito, una corrida de Monte Carlo. */
export const DEFAULT_SEED = 20261

export interface Stochastic {
  /** Los autos con la goma envejecida hasta `lap`. */
  cars: DriverState[]
  /**
   * Ruido de esta vuelta para cada auto, en segundos. Va aparte de
   * `degradationS` a propósito: la tabla y las tarjetas tienen que mostrar la
   * **tendencia**, no el temblor de una vuelta suelta.
   */
  paceNoise: number[]
}

/**
 * Envejece la goma de cada auto desde `fromLap` hasta `lap`.
 *
 * El ritmo de caída de cada tanda sale del nominal más un sorteo propio, así que
 * un auto puede resultar cuidadoso con la goma o no, y la carrera se entera. Es
 * la misma cuenta para adelante y para atrás: mover la vuelta con los botones no
 * altera la carrera, sólo mueve el reloj.
 *
 * **Lo que todavía no hay: paradas.** Nadie cambia gomas, así que la degradación
 * sólo crece. En una carrera de verdad la tanda se corta antes de que el número
 * se vaya de escala.
 */
export function evolve(
  base: DriverState[],
  lap: number,
  fromLap: number,
  seed: number = DEFAULT_SEED,
): Stochastic {
  const elapsed = Math.max(0, lap - fromLap)

  const cars = base.map((car, index) => {
    const spread = RATE_SD_S[car.compound] ?? RATE_SD_S.MEDIUM
    // Un sorteo por tanda, no por vuelta: la caída acumula, el ruido no.
    const rate = car.degradationRate + gaussian(seed, index, 0x5747) * spread
    return {
      ...car,
      degradationRate: rate,
      degradationS: car.degradationS + rate * elapsed,
      tyreAge: car.tyreAge + elapsed,
    }
  })

  const paceNoise = base.map((_, index) => gaussian(seed, index, lap) * LAP_NOISE_S)

  return { cars, paceNoise }
}
