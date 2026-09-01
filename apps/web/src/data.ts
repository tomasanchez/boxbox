/**
 * Datos medidos, no inventados.
 *
 * La parrilla y el duelo salen de 2026 R11 Budapest vuelta 30; el pronóstico
 * congelado, de 2026 R12 Zandvoort. Reproducibles con
 * `apps/ml/scripts/broadcast_demo.py --round 11 --lap 30`.
 */

import type {
  Compound,
  DriverState,
  RaceContext,
  Scenario,
  StrategyBattle,
  StrategyForecast,
} from './types'

/** Colores de compuesto: convención del deporte, no decisión de diseño. */
export const COMPOUND_COLOR: Record<Compound, string> = {
  SOFT: '#ec3013',
  MEDIUM: '#f5c518',
  HARD: '#f4f3f2',
  INTERMEDIATE: '#35c46f',
  WET: '#3671c6',
}

export const COMPOUND_LETTER: Record<Compound, string> = {
  SOFT: 'S',
  MEDIUM: 'M',
  HARD: 'H',
  INTERMEDIATE: 'I',
  WET: 'W',
}

/**
 * Costo de parar por estado de pista, en posiciones.
 *
 * Medido sobre 413 paradas de 2026: en verde una parada cuesta 2 posiciones,
 * bajo neutralización cuesta 0 — aunque en segundos parezca más cara, porque
 * el pelotón circula agrupado.
 */
export const SCENARIOS: Scenario[] = [
  { id: 'GREEN', label: 'Verde', pitCostPositions: 2, note: 'parada normal · 22,2 s' },
  { id: 'VSC', label: 'VSC', pitCostPositions: 0, note: 'pelotón agrupado' },
  { id: 'SC', label: 'Safety Car', pitCostPositions: 0, note: 'ventana barata' },
  { id: 'RED', label: 'Bandera roja', pitCostPositions: 0, note: 'cambio gratis' },
]

export const RACE: RaceContext = {
  season: 2026,
  round: 11,
  circuit: 'Budapest',
  totalLaps: 70,
  currentLap: 30,
  trackStatus: 'GREEN',
  scProbability: 0.571,
  mandatoryCompounds: ['MEDIUM', 'HARD'],
  minSets: 2,
}

/** 2026 R11 Budapest, vuelta 30. Ventanas y degradación medidas. */
export const GRID: DriverState[] = [
  {
    code: 'PIA', team: 'McLaren', teamColor: '#ff8000', position: 1,
    compound: 'HARD', tyreAge: 14, degradationS: 1.58, degradationRate: 0.138,
    gapAheadS: null, gapBehindS: 0.98,
    pitWindow: { opensLap: 30, closesLap: 48 },
  },
  {
    code: 'NOR', team: 'McLaren', teamColor: '#ff8000', position: 2,
    compound: 'HARD', tyreAge: 13, degradationS: 1.21, degradationRate: 0.164,
    gapAheadS: 0.98, gapBehindS: 2.4,
    pitWindow: { opensLap: 30, closesLap: 48 },
  },
  {
    code: 'VER', team: 'Red Bull Racing', teamColor: '#3671c6', position: 3,
    compound: 'HARD', tyreAge: 16, degradationS: -0.5, degradationRate: 0.0,
    gapAheadS: 2.4, gapBehindS: 1.1,
    pitWindow: null,
  },
  {
    code: 'LEC', team: 'Ferrari', teamColor: '#e8002d', position: 4,
    compound: 'HARD', tyreAge: 14, degradationS: 1.1, degradationRate: 0.121,
    gapAheadS: 1.1, gapBehindS: 3.2,
    pitWindow: { opensLap: 30, closesLap: 48 },
  },
  {
    code: 'ANT', team: 'Mercedes', teamColor: '#27f4d2', position: 5,
    compound: 'HARD', tyreAge: 8, degradationS: 0.9, degradationRate: 0.11,
    gapAheadS: 3.2, gapBehindS: 0.7,
    pitWindow: { opensLap: 31, closesLap: 48 },
  },
  {
    code: 'HAM', team: 'Ferrari', teamColor: '#e8002d', position: 6,
    compound: 'HARD', tyreAge: 17, degradationS: 0.0, degradationRate: 0.0,
    gapAheadS: 0.7, gapBehindS: 4.5,
    pitWindow: null,
  },
  {
    code: 'HAD', team: 'Racing Bulls', teamColor: '#6692ff', position: 7,
    compound: 'HARD', tyreAge: 11, degradationS: 0.9, degradationRate: 0.021,
    gapAheadS: 4.5, gapBehindS: 1.9,
    pitWindow: { opensLap: 42, closesLap: 48 },
  },
  {
    code: 'RUS', team: 'Mercedes', teamColor: '#27f4d2', position: 8,
    compound: 'HARD', tyreAge: 3, degradationS: -0.15, degradationRate: 0.0,
    gapAheadS: 1.9, gapBehindS: 2.8,
    pitWindow: null,
  },
  {
    code: 'SAI', team: 'Williams', teamColor: '#64c4ff', position: 9,
    compound: 'MEDIUM', tyreAge: 12, degradationS: 0.31, degradationRate: -0.083,
    gapAheadS: 2.8, gapBehindS: 0.62,
    pitWindow: null,
  },
  {
    code: 'BEA', team: 'Haas F1 Team', teamColor: '#b6babd', position: 10,
    compound: 'HARD', tyreAge: 8, degradationS: 0.54, degradationRate: 0.09,
    gapAheadS: 0.62, gapBehindS: 1.4,
    pitWindow: { opensLap: 35, closesLap: 48 },
  },
]

/** Duelo medido en la vuelta 30. El veredicto sale de la probabilidad. */
export const BATTLE: StrategyBattle = {
  chaser: 'NOR',
  leader: 'PIA',
  gapNow: 0.98,
  responseLaps: 2,
  perLapGain: 1.41,
  gapAfter: -1.85,
  probability: 0.83,
  verdict: 'SALE_ADELANTE',
}

/** Segundo duelo del mismo instante, en la banda de incertidumbre. */
export const BATTLE_ALT: StrategyBattle = {
  chaser: 'BEA',
  leader: 'SAI',
  gapNow: 0.62,
  responseLaps: 2,
  perLapGain: 0.54,
  gapAfter: -0.47,
  probability: 0.57,
  verdict: 'CARA_O_CRUZ',
}

/** Salida del algoritmo genético para LEC en la carrera actual. */
export const PLAN_DISTRIBUTION = {
  driver: 'LEC',
  stopDistribution: { '1': 0.31, '2': 0.48, '3': 0.19, '4': 0.02 },
  modalPlan: [
    { compound: 'MEDIUM' as Compound, laps: 18 },
    { compound: 'HARD' as Compound, laps: 25 },
    { compound: 'SOFT' as Compound, laps: 14 },
  ],
}

/**
 * Pronóstico congelado de Zandvoort, con el resultado real.
 *
 * Es deliberadamente un caso donde el sistema falló: la carrera tuvo bandera
 * roja en la vuelta 2 y terminó en 3 paradas, fuera del plan modal. Un
 * pronóstico fallado se muestra igual de grande que uno acertado.
 */
export const FORECAST: StrategyForecast = {
  driver: 'LEC',
  circuit: 'Zandvoort',
  season: 2026,
  round: 12,
  totalLaps: 72,
  issuedAt: '21/08/2026 18:40',
  stopDistribution: { '1': 0.31, '2': 0.48, '3': 0.19, '4': 0.02 },
  modalPlan: [
    { compound: 'MEDIUM', laps: 18 },
    { compound: 'HARD', laps: 25 },
    { compound: 'SOFT', laps: 14 },
  ],
  firstStopInterval: { low: 16, high: 23, median: 19 },
  actual: {
    stops: 3,
    firstStopLap: 2,
    plan: [
      { compound: 'MEDIUM', laps: 2 },
      { compound: 'HARD', laps: 28 },
      { compound: 'MEDIUM', laps: 25 },
      { compound: 'SOFT', laps: 17 },
    ],
  },
}
