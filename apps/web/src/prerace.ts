/**
 * El export pre-carrera de Zandvoort, tal como lo escribió el buscador.
 *
 * **No se transcribe: se importa** (ADR-010). El archivo es el que genera
 * `apps/ml/scripts/prerace_export.py` y se copia a `src/` sin tocar ni una
 * cifra, así que lo que se ve en pantalla es literalmente lo que midió la
 * corrida. Los tipos de abajo **describen** el archivo —por eso están en
 * `snake_case`, como el JSON— en vez de reescribirlo en las convenciones de
 * TypeScript, que obligaría a mapear campo por campo y abriría la puerta a que
 * un número se pierda en el camino.
 *
 * Lo único que no viene del JSON es el color de cada equipo, que sale de la
 * parrilla ya cargada en `data.ts`. Es convención del deporte, no una medición.
 */

import { GRID, RACE } from './data'
import { PALETTE } from './theme'
import type { RecommendedPlan } from './plans'
import type { Compound, DriverState } from './types'
import type { DrawModel, PlannedStop } from './tyres'
import raw from './prerace-zandvoort.json'

/**
 * Qué se estaba maximizando. Ver `objectiveNote`.
 *
 * Son **tres**, no dos, y el que elige lo elige la búsqueda sola según desde
 * dónde larga el auto. `in_points` es el del medio y es el que faltaba: un auto
 * en la burbuja de los puntos tiene los puntos al alcance, pero la cola de la
 * tabla es tan plana que maximizar puntos esperados no le da gradiente. Ahí lo
 * que se maximiza es la probabilidad de terminar entre los diez.
 */
export type Objective = 'points' | 'in_points' | 'position'

/** Apetito de riesgo con el que se ordenaron los planes. */
export type RiskAppetite = 'averse' | 'neutral' | 'seeking'

export interface PreRaceCar {
  code: string
  driver: string
  team: string
  grid_position: number
  best_lap_s: number
  gap_to_pole_s: number
  /** Ritmo de carrera respecto del poleman, en segundos por vuelta. */
  pace_s: number
  start_compound: Compound
  /** Las tandas como las diría el muro: «M18-H26-H27». */
  plan: string
  stops: { lap: number; compound: Compound }[]
  objective: Objective
  risk: RiskAppetite
  p_ganar: number
  p_podio: number
  p_puntos: number
  /** Probabilidad de terminar por delante de su puesto de largada. */
  p_mejora: number
  mean_position: number
  sd_position: number
  mean_points: number
  /** Mejor plan menos el peor de la población final: cuánto vale elegir bien. */
  decision_value: number
  /** Valor del plan re-evaluado con sorteos nuevos. */
  score: number
  /** Valor con el que la búsqueda lo eligió, sobre sus propios sorteos. */
  score_in_sample: number
  /** `score_in_sample` − `score`: cuánto se entusiasmó la búsqueda consigo misma. */
  optimism: number
  /**
   * Cuánto de la población final quedó en cada cantidad de paradas.
   *
   * **Es convergencia de la búsqueda, no probabilidad de la carrera.** Confundir
   * las dos cosas fue el error que originó esta vista, así que en pantalla va
   * siempre rotulado como convergencia.
   */
  stop_distribution: Record<string, number>
  /** Conteo crudo de puestos de llegada sobre las carreras sorteadas. */
  position_histogram: Record<string, number>
  alternatives: { plan: string; stops: number; score: number }[]
  history: {
    generation: number
    /** Mejor valor de la generación, en las unidades del objetivo de este auto. */
    best: number
    stop_distribution: Record<string, number>
  }[]
}

export interface PreRaceExport {
  race: {
    circuit: string
    event: string
    year: number
    round: number
    total_laps: number
    pole_s: number
    cars: number
    start_compound: Compound
    excluded: string[]
  }
  model: {
    wear_median_s_lap: Record<Compound, number>
    wear_cuts_s_lap: Record<Compound, number[]>
    cut_probabilities: number[]
    /** Cuartiles de pérdida de boxes por estado de pista: [p25, mediana, p75]. */
    pit_loss_s: Record<string, number[]>
    lap_noise_s: number
    max_stint_laps: Record<string, number>
    quali_to_race_pace: number
  }
  search: {
    engine: string
    objective: string
    risk: string
    population: number
    generations: number
    draws: number
    max_stops: number
    seed: number
  }
  /** Lo que el export asume y no midió. Se muestra en pantalla, no se esconde. */
  assumptions: string[]
  checks: {
    draws: number
    position_histogram_sums_draws: boolean
    history_generations: number
  }
  cars: PreRaceCar[]
}

export const PRERACE = raw as unknown as PreRaceExport

/** Los veintidós, en orden de grilla — que es el orden en que vienen. */
export const PRERACE_CARS: PreRaceCar[] = PRERACE.cars

const BY_CODE = new Map(PRERACE_CARS.map((car) => [car.code, car]))

export function preraceCar(code: string): PreRaceCar {
  const car = BY_CODE.get(code)
  if (!car) throw new Error(`Sin datos pre-carrera para ${code}`)
  return car
}

/**
 * Color de equipo por piloto, tomado de la parrilla ya cargada.
 *
 * El export no trae colores, y no se inventa ninguno: si algún día apareciera un
 * código sin cargar, queda en gris neutro y se nota que falta el dato.
 */
const TEAM_COLOR = new Map(GRID.map((d) => [d.code, d.teamColor]))

export function teamColor(code: string): string {
  return TEAM_COLOR.get(code) ?? PALETTE.txt3
}

const LETTER_COMPOUND: Record<string, Compound> = { H: 'HARD', M: 'MEDIUM', S: 'SOFT' }

export interface Stint {
  compound: Compound
  laps: number
  /** Primera vuelta de la tanda. */
  fromLap: number
}

/**
 * Las tandas que codifica un plan como «M18-H26-H27».
 *
 * Ojo con el total: las tandas del export suman **71** en una carrera de 72
 * vueltas, para los veintidós autos. Se muestra lo que dice el archivo; acá no
 * se le agrega la vuelta que falta para que cierre más lindo.
 */
export function stintsOf(plan: string): Stint[] {
  let fromLap = 1
  return plan.split('-').map((part) => {
    const laps = Number.parseInt(part.slice(1), 10) || 0
    const stint = { compound: LETTER_COMPOUND[part[0]] ?? 'MEDIUM', laps, fromLap }
    fromLap += laps
    return stint
  })
}

/** Vueltas que cubre el plan. Son 71 de 72: ver `stintsOf`. */
export function plannedLaps(plan: string): number {
  return stintsOf(plan).reduce((total, stint) => total + stint.laps, 0)
}

/**
 * La llegada como banda, nunca como número solo (ADR-001).
 *
 * Media ± un desvío, recortada a la parrilla: no existe el puesto 0 ni el 23.
 */
export function arrivalBand(car: PreRaceCar): { low: number; high: number; mean: number } {
  const cars = PRERACE.race.cars
  return {
    low: Math.max(1, car.mean_position - car.sd_position),
    high: Math.min(cars, car.mean_position + car.sd_position),
    mean: car.mean_position,
  }
}

export interface HistogramBar {
  position: number
  count: number
  /** Fracción de las carreras sorteadas que terminaron en ese puesto. */
  share: number
}

/**
 * El histograma de llegada, con los puestos vacíos incluidos.
 *
 * El JSON trae sólo los puestos con conteo, así que dibujarlo tal cual dejaría
 * el eje con huecos y cambiaría de ancho según el auto. Los que faltan valen
 * cero, que es un dato y no un relleno.
 */
export function histogramBars(car: PreRaceCar): HistogramBar[] {
  const draws = PRERACE.checks.draws
  const bars: HistogramBar[] = []
  for (let position = 1; position <= PRERACE.race.cars; position += 1) {
    const count = car.position_histogram[String(position)] ?? 0
    bars.push({ position, count, share: count / draws })
  }
  return bars
}

/**
 * Las cantidades de paradas presentes en una distribución, ordenadas.
 *
 * **No se asume 0..4.** El reparador agrega una parada cuando el plan no cumple
 * el reglamento, así que hay generaciones con la clave `"5"` aunque el máximo de
 * la búsqueda sea 4. Recorrer un rango fijo se comía esa columna.
 */
export function stopKeys(distribution: Record<string, number>): number[] {
  return Object.keys(distribution)
    .map(Number)
    .sort((a, b) => a - b)
}

/** Todas las cantidades de paradas que aparecen en la historia de un auto. */
export function historyStopKeys(car: PreRaceCar): number[] {
  const keys = new Set<number>()
  for (const generation of car.history) {
    for (const key of stopKeys(generation.stop_distribution)) keys.add(key)
  }
  return [...keys].sort((a, b) => a - b)
}

/**
 * Qué estaba maximizando la búsqueda, dicho en castellano.
 *
 * El objetivo es ADAPTATIVO: lo elige la búsqueda según desde dónde larga el
 * auto, y por eso no es el mismo para los veintidós. Mostrar la etiqueta cruda
 * —`points`, `in_points`, `position`— haría parecer que el sistema se
 * contradice de un auto al otro; es adaptación, y se explica.
 *
 * La escala de los tres es distinta, así que el valor de un auto **no se compara
 * con el de otro**: puntos esperados, probabilidad, y puesto en negativo.
 */
export function objectiveNote(car: PreRaceCar): string {
  switch (car.objective) {
    case 'points':
      return 'Maximizó puntos esperados: desde ese puesto la tabla de puntos gradúa sola cada mejora.'
    case 'in_points':
      return 'Maximizó la probabilidad de entrar a los puntos: está en la burbuja, donde los puntos esperados son alcanzables pero la cola de la tabla es demasiado plana para guiar la búsqueda.'
    default:
      return 'Maximizó puesto de llegada: desde ahí los puntos no llegan, y lo que queda por ganar son puestos.'
  }
}

/** La misma idea en dos palabras, para donde no entra la frase entera. */
export function objectiveLabel(objective: string): string {
  switch (objective) {
    case 'points':
      return 'máx. puntos'
    case 'in_points':
      return 'máx. entrar a los puntos'
    default:
      return 'máx. posición'
  }
}

/** Lo mismo con el apetito de riesgo, que también se elige solo. */
export function riskNote(car: PreRaceCar): string {
  switch (car.risk) {
    case 'averse':
      return 'Con aversión al riesgo: entre dos planes parecidos prefiere el de llegada más pareja.'
    case 'seeking':
      return 'Buscando riesgo: desde el fondo conviene el plan que abre la dispersión, porque abajo casi no hay nada que perder.'
    default:
      return 'Riesgo neutro: ordena por el valor esperado, sin premiar ni castigar la dispersión.'
  }
}

/**
 * El mismo plan, con la forma que espera la tarjeta del mapa.
 *
 * Es una traducción de nombres, no una copia de números: cada campo apunta al
 * del export. Existe para que la tarjeta superpuesta al trazado pueda mostrar el
 * plan pre-carrera cuando la carrera está corriendo desde la largada, en vez del
 * de la vuelta 30, que es otro plan para otro momento.
 */
export function recommendedPlan(car: PreRaceCar): RecommendedPlan {
  return {
    fromPosition: car.grid_position,
    plan: car.plan,
    stops: car.stops,
    stopDistribution: car.stop_distribution,
    meanPosition: car.mean_position,
    sdPosition: car.sd_position,
    meanPoints: car.mean_points,
    decisionValue: car.decision_value,
    objective: car.objective,
    alternatives: car.alternatives,
  }
}

/* ------------------------------------------------------- la carrera desde V1 */

/**
 * El modelo con el que se sortea la carrera de largada.
 *
 * Son los cortes que trae el propio export, no los de `tyres.ts`. Hay dos
 * mediciones de desgaste de Zandvoort conviviendo en el repositorio y difieren
 * un 63% (ver ADR-009): la de `tyres.ts` junta todas las temporadas, la de acá
 * se queda con 2026, que es lo que la política del informe declara. Si la vista
 * pre-carrera sorteara con la otra, la carrera animada estaría contradiciendo al
 * buscador que emitió la recomendación que la misma pantalla muestra.
 *
 * La pérdida de boxes viene como terna por estado de pista; se lee
 * [p25, mediana, p75], igual que el resto de las ternas del modelo.
 */
export const PRERACE_MODEL: DrawModel = {
  wearCuts: PRERACE.model.wear_cuts_s_lap,
  pitLoss: {
    p25: PRERACE.model.pit_loss_s.green[0],
    median: PRERACE.model.pit_loss_s.green[1],
    p75: PRERACE.model.pit_loss_s.green[2],
  },
}

/**
 * La parrilla de largada como estado inicial de la simulación.
 *
 * Qué es medición y qué no, campo por campo:
 *
 *   `position`    el puesto de clasificación, del export.
 *   `compound`    MEDIUM para todos: es un SUPUESTO declarado del export —antes
 *                 de largar no se sabe con qué sale cada uno— y está listado en
 *                 `assumptions`, que la vista muestra.
 *   `tyreAge`     cero: juego nuevo.
 *   `degradationS` cero: con la goma nueva todavía no perdió nada.
 *   `degradationRate` la mediana medida del compuesto. `evolve` le suma el
 *                 sorteo menos la mediana, así que arrancar en la mediana deja
 *                 el ritmo de caída siendo un sorteo limpio de la distribución.
 *   `gapAheadS`   null: en la parrilla los autos están **detenidos**. No hay
 *                 intervalo que medir y no se inventa uno.
 *   `paceS`       el ritmo relativo medido, que es lo que separa al pelotón una
 *                 vez que larga.
 */
export const PRERACE_GRID: DriverState[] = PRERACE_CARS.map((car) => ({
  code: car.code,
  team: car.team,
  teamColor: teamColor(car.code),
  position: car.grid_position,
  compound: car.start_compound,
  tyreAge: 0,
  degradationS: 0,
  degradationRate: medianOf(PRERACE_MODEL.wearCuts[car.start_compound]),
  gapAheadS: null,
  gapLeaderS: null,
  pitWindow: null,
  paceS: car.pace_s,
}))

/** Cada auto corre el plan que le dio el algoritmo. El sorteo no los cambia. */
export const PRERACE_PLANS: PlannedStop[][] = PRERACE_CARS.map((car) => car.stops)

/** La mediana de una distribución dada por cortes es el corte del medio. */
function medianOf(cuts: number[]): number {
  return cuts[(cuts.length - 1) / 2]
}

/**
 * La carrera del export y la que dibuja la web son la misma.
 *
 * Si algún día dejan de serlo —otro circuito, otra cantidad de vueltas— la vista
 * estaría mezclando dos carreras sin avisar. Mejor que reviente acá.
 */
if (PRERACE.race.total_laps !== RACE.totalLaps) {
  throw new Error(
    `El export es de ${PRERACE.race.total_laps} vueltas y la web corre ${RACE.totalLaps}`,
  )
}
