/**
 * Desgaste probabilístico y paradas en boxes.
 *
 * Hasta acá cada auto corría con una cifra de degradación fija, así que dos
 * autos con la misma goma andaban **exactamente** igual para siempre. Ahora hay
 * tres fuentes de variación, todas medidas, y una parada.
 *
 * ## De dónde sale cada sorteo
 *
 *   ruido de vuelta   se sortea **cada vuelta**, normal de desvío **0,457 s**.
 *                     Es lo que queda después de descontar desgaste y
 *                     combustible: tráfico, viento, una entrada ancha. No
 *                     acumula, y es lo que impide que dos autos iguales anden
 *                     igual. Medido sobre 4.407 tandas.
 *
 *   ritmo de caída    se sortea **una vez por tanda**, de la distribución
 *                     **empírica** de Zandvoort. Acumula.
 *
 *   pérdida de boxes  se sortea en la parada, de los cuartiles medidos en
 *                     Zandvoort: mediana 23,5 s, p25 20,6, p75 31,3.
 *
 * ## Por qué la distribución empírica y no una normal
 *
 * Porque las tandas no se distribuyen normal ni de casualidad. Medida sobre
 * Zandvoort, la curtosis del ritmo de caída da **48,6 en el duro, 32,8 en el
 * medio y 20,2 en el blando** — una normal tiene cero. Hay unas pocas tandas
 * catastróficas que estiran la cola y hacen que el desvío mienta: el blando de
 * Zandvoort tiene desvío 0,664 s/vuelta, pero entre el percentil 5 y el 95 va de
 * −0,184 a 0,138. Sortear de una normal con ese desvío daba tandas absurdas
 * varias veces por carrera.
 *
 * Así que no se asume forma: se guardan nueve cortes de la distribución medida y
 * se sortea interpolando entre ellos. Es lo que pidió el dato, no lo que le
 * quedaba cómodo al modelo.
 *
 * ## La parada
 *
 * Entra en su ventana —sorteada uniforme adentro, que es lo único honesto
 * sabiendo sólo el rango— y calza el compuesto obligatorio que le falta,
 * eligiendo entre medio y duro según cuánto quede por correr. Los autos sin
 * ventana proyectable no paran: es la mitad de la parrilla, y es un hallazgo
 * anotado, no un olvido. Ver `docs/research/pace-noise.md`.
 *
 * Medido con `apps/ml/scripts/pace_noise.py` y
 * `apps/ml/scripts/zandvoort_distributions.py`.
 */

import { RACE } from './data'
import type { Compound, DriverState } from './types'

/** Desvío del ritmo de una vuelta, en segundos. Mediana de 4.407 tandas. */
export const LAP_NOISE_S = 0.457

/** Probabilidades a las que están cortadas las distribuciones de abajo. */
const CUT_AT = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]

/**
 * Ritmo de caída por compuesto, en s/vuelta, como cortes de la distribución
 * medida en Zandvoort. El del medio de cada fila es la mediana.
 */
const WEAR_CUTS: Record<Compound, number[]> = {
  // 98 tandas.
  SOFT: [-0.184, -0.0213, 0.011, 0.0184, 0.0401, 0.0549, 0.0769, 0.0875, 0.1382],
  // 79 tandas.
  MEDIUM: [-0.0273, 0.0112, 0.0211, 0.0337, 0.0415, 0.0539, 0.0675, 0.08, 0.1067],
  // 80 tandas.
  HARD: [-0.0353, 0.0009, 0.0132, 0.0217, 0.0344, 0.0436, 0.0498, 0.0637, 0.0966],
  // Mojados: 201 y 17 tandas en todo el conjunto, ninguna en Zandvoort seco. Se
  // presta la del blando, que es la más dispersa de las secas, y queda dicho.
  INTERMEDIATE: [-0.184, -0.0213, 0.011, 0.0184, 0.0401, 0.0549, 0.0769, 0.0875, 0.1382],
  WET: [-0.184, -0.0213, 0.011, 0.0184, 0.0401, 0.0549, 0.0769, 0.0875, 0.1382],
}

/** Pérdida de boxes en verde en Zandvoort, en segundos. 164 paradas medidas. */
const PIT_LOSS_CUTS = { p25: 20.6, median: 23.5, p75: 31.3 }

/**
 * Cuánto dura un juego acá, en vueltas. Mediana medida en Zandvoort.
 * Se usa para elegir compuesto: si queda más que esto, hace falta el duro.
 */
const STINT_LIFE: Partial<Record<Compound, number>> = { HARD: 28, MEDIUM: 22, SOFT: 15 }

/** Semilla por defecto. Cambiarla es, en chiquito, una corrida de Monte Carlo. */
export const DEFAULT_SEED = 20261

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

/**
 * Invierte una distribución dada por cortes: sortea interpolando entre ellos.
 *
 * Fuera del rango medido no extrapola — devuelve el corte del extremo. Es
 * deliberado: más allá del percentil 95 no hay dato, y estirar una recta ahí es
 * inventar justo en la cola, que es donde más se nota.
 */
function fromCuts(cuts: number[], u: number): number {
  if (u <= CUT_AT[0]) return cuts[0]
  const last = CUT_AT.length - 1
  if (u >= CUT_AT[last]) return cuts[last]

  let i = 0
  while (i < last && CUT_AT[i + 1] < u) i += 1
  const span = CUT_AT[i + 1] - CUT_AT[i]
  const t = span > 0 ? (u - CUT_AT[i]) / span : 0
  return cuts[i] + (cuts[i + 1] - cuts[i]) * t
}

/** La mediana de un compuesto, que es el corte del medio. */
function medianWear(compound: Compound): number {
  const cuts = WEAR_CUTS[compound] ?? WEAR_CUTS.MEDIUM
  return cuts[(CUT_AT.length - 1) / 2]
}

/** Ritmo de caída sorteado para un compuesto, en s/vuelta. */
function drawWear(compound: Compound, ...parts: number[]): number {
  return fromCuts(WEAR_CUTS[compound] ?? WEAR_CUTS.MEDIUM, hash(...parts))
}

/** Pérdida de boxes sorteada, triangular sobre los cuartiles medidos. */
function drawPitLoss(...parts: number[]): number {
  const { p25: a, median: c, p75: b } = PIT_LOSS_CUTS
  const u = hash(...parts)
  const split = (c - a) / (b - a)
  return u < split
    ? a + Math.sqrt(u * (b - a) * (c - a))
    : b - Math.sqrt((1 - u) * (b - a) * (b - c))
}

export interface PitStop {
  /** Vuelta en la que entra a boxes. */
  lap: number
  /** Compuesto que calza. */
  compound: Compound
  /** Segundos que pierde. */
  lossS: number
}

export interface Stochastic {
  /** Los autos con la goma envejecida —o cambiada— hasta `lap`. */
  cars: DriverState[]
  /**
   * Ruido de esta vuelta para cada auto, en segundos. Va aparte de
   * `degradationS` a propósito: la tabla y las tarjetas tienen que mostrar la
   * **tendencia**, no el temblor de una vuelta suelta.
   */
  paceNoise: number[]
  /** La parada planeada de cada auto, o `null` si no para. */
  stops: (PitStop | null)[]
  /**
   * Vueltas de avance que cada auto ya cedió en boxes. Sube de golpe cuando
   * para; `useField` lo convierte en tiempo detenido en el pit lane.
   */
  progressLost: number[]
}

/**
 * Cuándo y con qué para un auto.
 *
 * La vuelta sale uniforme dentro de su ventana. Con sólo un rango, uniforme es
 * la distribución de máxima entropía: cualquier otra forma estaría metiendo una
 * creencia sobre cuándo paran los equipos que no salió de ningún dato.
 *
 * El compuesto es el obligatorio que le falta —B6.3.8 exige dos secas—, medio o
 * duro según si lo que queda entra en la vida medida de un juego de medios.
 */
function planStop(car: DriverState, index: number, seed: number): PitStop | null {
  const window = car.pitWindow
  if (!window || car.retiredOnLap != null) return null

  const span = Math.max(0, window.closesLap - window.opensLap)
  const lap = window.opensLap + Math.round(hash(seed, index, 0x9017) * span)

  const remaining = RACE.totalLaps - lap
  const alternatives = RACE.mandatoryCompounds.filter((c) => c !== car.compound)
  const compound: Compound =
    alternatives.length === 0
      ? car.compound
      : (alternatives.find((c) => remaining <= (STINT_LIFE[c] ?? 99)) ?? alternatives[0])

  return { lap, compound, lossS: drawPitLoss(seed, index, 0x1055) }
}

/**
 * Envejece la goma de cada auto desde `fromLap` hasta `lap`, con su parada.
 *
 * Es la misma cuenta para adelante y para atrás: mover la vuelta con los botones
 * no altera la carrera, sólo mueve el reloj.
 */
export function evolve(
  base: DriverState[],
  lap: number,
  fromLap: number,
  seed: number = DEFAULT_SEED,
): Stochastic {
  const stops = base.map((car, index) => planStop(car, index, seed))

  const cars = base.map((car, index) => {
    const stop = stops[index]

    if (stop && lap >= stop.lap) {
      // Juego nuevo: no hay medición previa de este auto con esta goma, así que
      // el ritmo se sortea entero de la distribución del compuesto.
      const age = lap - stop.lap
      const rate = drawWear(stop.compound, seed, index, 0x2472)
      return {
        ...car,
        compound: stop.compound,
        tyreAge: age,
        degradationRate: rate,
        degradationS: rate * age,
        // La ventana que traía era para **esta** parada, y ya la hizo. No hay
        // una proyectada para la siguiente, así que se limpia en vez de dejar
        // un rango vencido: la tabla mostraba la ventana pasada y el duelo de
        // boxes seguía ofreciendo parar a un auto que acababa de parar.
        pitWindow: null,
      }
    }

    // Tanda en curso: hay un ritmo medido para este auto. Se conserva como valor
    // central y se le suma la incertidumbre con la forma de la distribución
    // —el sorteo menos su mediana—, en vez de tirarlo y sortear de cero.
    const deviation = drawWear(car.compound, seed, index, 0x5747) - medianWear(car.compound)
    const rate = car.degradationRate + deviation
    const elapsed = Math.max(0, lap - fromLap)
    return {
      ...car,
      degradationRate: rate,
      degradationS: car.degradationS + rate * elapsed,
      tyreAge: car.tyreAge + elapsed,
    }
  })

  const paceNoise = base.map((_, index) => gaussian(seed, index, lap) * LAP_NOISE_S)

  const progressLost = stops.map((stop) =>
    stop && lap >= stop.lap ? stop.lossS / RACE.greenLapS : 0,
  )

  return { cars, paceNoise, stops, progressLost }
}
