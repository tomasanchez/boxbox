/**
 * Contrato de datos del simulador.
 *
 * Refleja `docs/design/brief-ui-simulador.md`. Los tipos que admiten `null`
 * lo hacen a propósito: son estados reales del sistema, no huecos de datos.
 */

export type Compound = 'SOFT' | 'MEDIUM' | 'HARD' | 'INTERMEDIATE' | 'WET'

export type TrackStatus = 'GREEN' | 'YELLOW' | 'VSC' | 'SC' | 'RED'

/** El veredicto lo manda la probabilidad, nunca el gap proyectado. */
export type Verdict = 'SALE_ADELANTE' | 'CARA_O_CRUZ' | 'SIGUE_ATRAS'

export interface DriverState {
  code: string
  /**
   * Vuelta en la que abandonó, o `null` si terminó la carrera. El estado no se
   * guarda como bandera porque depende de la vuelta que se esté mirando.
   */
  retiredOnLap?: number | null
  team: string
  teamColor: string
  position: number
  compound: Compound
  tyreAge: number
  /** Segundos por vuelta perdidos por desgaste. Negativo = todavía mejorando. */
  degradationS: number
  /** Cuánto crece esa pérdida por vuelta. */
  degradationRate: number
  /**
   * Ritmo propio respecto del más rápido, en segundos por vuelta.
   *
   * Sólo lo trae la **largada**: sale de la clasificación vía el factor
   * `quali_to_race_pace` (0,835, validado r = 0,880). En la foto de la vuelta 30
   * no hace falta —el ritmo relativo ya está dentro de los intervalos medidos—,
   * así que ahí queda sin definir y no suma nada.
   */
  paceS?: number
  /** Intervalo al auto de adelante, en segundos. */
  gapAheadS: number | null
  /** Distancia acumulada al líder, en segundos. */
  gapLeaderS: number | null
  gapBehindS?: number | null
  /**
   * Rango de vueltas donde conviene parar, o `null` cuando no hay cruce
   * proyectable. Cerca de la mitad de la parrilla está en ese estado a mitad
   * de carrera: hay que mostrarlo, no inventar un rango.
   */
  pitWindow: { opensLap: number; closesLap: number } | null
}

export interface StrategyBattle {
  chaser: string
  leader: string
  /**
   * Ventana de parada del perseguidor, que es el motivo por el que el duelo se
   * muestra. `null` sólo en un duelo armado a mano, fuera de la simulación.
   */
  chaserWindow?: { opensLap: number; closesLap: number } | null
  gapNow: number
  responseLaps: number
  perLapGain: number
  /** Negativo = el perseguidor sale adelante. */
  gapAfter: number
  probability: number
  verdict: Verdict
}

export interface RaceContext {
  season: number
  round: number
  circuit: string
  /** Clave en `tracks.ts` para la geometría real. */
  trackKey: string
  totalLaps: number
  /**
   * Vuelta verde representativa, en segundos. Es la mediana medida, y sirve para
   * convertir «segundos por vuelta perdidos» en fracción de ritmo: una décima
   * pesa distinto en una vuelta de 78 s que en una de 120.
   */
  greenLapS: number
  currentLap: number
  trackStatus: TrackStatus
  scProbability: number
  mandatoryCompounds: Compound[]
  /** 2 salvo en Mónaco, donde el reglamento exige 3 juegos. */
  minSets: number
}

export interface StintPlan {
  compound: Compound
  laps: number
}

export interface StrategyForecast {
  driver: string
  circuit: string
  season: number
  round: number
  totalLaps: number
  issuedAt: string
  /** Distribución sobre cantidad de paradas: clave = paradas, valor = probabilidad. */
  stopDistribution: Record<string, number>
  modalPlan: StintPlan[]
  firstStopInterval: { low: number; high: number; median: number }
  /** Lo que realmente pasó. `null` mientras el pronóstico sigue congelado. */
  actual: {
    stops: number
    firstStopLap: number
    plan: StintPlan[]
  } | null
}
