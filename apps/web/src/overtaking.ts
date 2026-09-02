/**
 * Dificultad medida para adelantar, por circuito.
 *
 * Medido sobre **95 carreras** de 2022 a 2026 en 25 circuitos, contando los
 * cambios de posición en pista por vuelta en verde. Se descuentan las paradas en
 * boxes, las neutralizaciones y las carreras con lluvia, que cambian el orden
 * por motivos que no tienen que ver con el trazado. Reproducible con
 * `uv run python scripts/overtake_difficulty.py --offline`.
 *
 * **La cifra es una posición dentro del conjunto, no una escala absoluta.** Y
 * conviene saber de qué está hecha: con cuatro o cinco carreras por circuito, la
 * mitad de la diferencia entre ellos es ruido de una tarde. El test de mitades
 * —correlacionar la media de 2022-23 de cada circuito contra la de 2024-26— da
 * una confiabilidad de **0,346**, así que cada estimación está encogida hacia el
 * promedio general en esa proporción. Sin eso, un circuito visitado tres veces
 * se sentaba en la punta del ranking por una sola carrera caótica.
 *
 * Lo que sobrevive al encogimiento es la separación de los extremos: **Mónaco**
 * abajo de todo con 0,17 cambios por vuelta, y **Las Vegas y Monza** arriba con
 * 1,45 y 1,21. El medio de la tabla no es separable y no habría que leerlo como
 * si lo fuera; por eso la tarjeta muestra las carreras medidas al pasar el mouse
 * por encima.
 *
 * Le Castellet quedó afuera: una sola carrera medida, y ya no está en el
 * calendario.
 */

export interface CircuitOvertaking {
  /** 0 a 1, posición en el ranking encogido. 1 = el más difícil medido. */
  difficulty: number
  /** Cambios de posición en pista por vuelta en verde, sin encoger. */
  perLap: number
  /** Carreras sobre las que se midió. */
  races: number
  /** Puesto en el ranking, 1 = el más difícil. */
  rank: number
}

/** Circuitos medidos, del más difícil al más fácil. */
export const OVERTAKING: Record<string, CircuitOvertaking> = {
  Monaco: { difficulty: 1.0, perLap: 0.17, races: 4, rank: 1 },
  Budapest: { difficulty: 0.82, perLap: 0.41, races: 4, rank: 2 },
  Lusail: { difficulty: 0.78, perLap: 0.45, races: 3, rank: 3 },
  Baku: { difficulty: 0.75, perLap: 0.49, races: 4, rank: 4 },
  Zandvoort: { difficulty: 0.74, perLap: 0.5, races: 4, rank: 5 },
  Imola: { difficulty: 0.73, perLap: 0.52, races: 3, rank: 6 },
  Spielberg: { difficulty: 0.72, perLap: 0.54, races: 5, rank: 7 },
  Suzuka: { difficulty: 0.68, perLap: 0.58, races: 4, rank: 8 },
  'Mexico City': { difficulty: 0.67, perLap: 0.59, races: 4, rank: 9 },
  Barcelona: { difficulty: 0.67, perLap: 0.6, races: 5, rank: 10 },
  Melbourne: { difficulty: 0.64, perLap: 0.63, races: 4, rank: 11 },
  'São Paulo': { difficulty: 0.64, perLap: 0.63, races: 3, rank: 12 },
  Miami: { difficulty: 0.6, perLap: 0.68, races: 5, rank: 13 },
  'Marina Bay': { difficulty: 0.6, perLap: 0.69, races: 4, rank: 14 },
  Silverstone: { difficulty: 0.6, perLap: 0.69, races: 3, rank: 15 },
  Sakhir: { difficulty: 0.59, perLap: 0.7, races: 4, rank: 16 },
  Montréal: { difficulty: 0.59, perLap: 0.7, races: 4, rank: 17 },
  'Spa-Francorchamps': { difficulty: 0.51, perLap: 0.8, races: 5, rank: 18 },
  Jeddah: { difficulty: 0.49, perLap: 0.82, races: 4, rank: 19 },
  Austin: { difficulty: 0.44, perLap: 0.88, races: 4, rank: 20 },
  'Yas Island': { difficulty: 0.41, perLap: 0.93, races: 4, rank: 21 },
  Shanghai: { difficulty: 0.39, perLap: 0.95, races: 3, rank: 22 },
  Monza: { difficulty: 0.19, perLap: 1.21, races: 4, rank: 23 },
  'Las Vegas': { difficulty: 0.0, perLap: 1.45, races: 3, rank: 24 },
}

/** Cuántos circuitos entraron en el ranking, para poder decir «5 de 24». */
export const MEASURED_CIRCUITS = Object.keys(OVERTAKING).length

/** Promedio general: 0,683 cambios por vuelta, encogido a la mitad de la escala. */
const FALLBACK: CircuitOvertaking = { difficulty: 0.6, perLap: 0.68, races: 95, rank: 0 }

/** Lo medido para un circuito, o el promedio general si no está en la tabla. */
export function overtakingAt(circuit: string): CircuitOvertaking {
  return OVERTAKING[circuit] ?? FALLBACK
}
