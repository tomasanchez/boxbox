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
  StintPlan,
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

export const RACE: RaceContext = {
  season: 2026,
  round: 12,
  circuit: 'Zandvoort',
  trackKey: 'zandvoort',
  totalLaps: 72,
  currentLap: 30,
  trackStatus: 'GREEN',
  scProbability: 0.571,
  mandatoryCompounds: ['MEDIUM', 'HARD'],
  minSets: 2,
}

/**
 * 2026 R12 Zandvoort, vuelta 30 — la parrilla completa tal como estaba.
 *
 * Los veintidós que largaron. Dos ya estaban afuera en la vuelta 30 —VER en la
 * 1 y BEA en la 2, ambos en el episodio de la bandera roja— y se listan igual
 * al pie de la torre, como en la transmisión: no se borran de la tabla.
 *
 * Regenerable con `apps/ml/scripts/broadcast_demo.py --round 12 --lap 30`.
 */
export const GRID: DriverState[] = [
  {
    code: 'ANT', team: 'Mercedes', teamColor: '#27f4d2',
    position: 1, compound: 'HARD', tyreAge: 9,
    degradationS: 0.38, degradationRate: 0.093,
    gapAheadS: null,
    gapLeaderS: 0.0,
    pitWindow: { opensLap: 37, closesLap: 50 },
  },
  {
    code: 'NOR', team: 'McLaren', teamColor: '#ff8000',
    position: 2, compound: 'HARD', tyreAge: 9,
    degradationS: 0.25, degradationRate: 0.064,
    gapAheadS: 0.69,
    gapLeaderS: 0.69,
    pitWindow: { opensLap: 42, closesLap: 50 },
  },
  {
    code: 'RUS', team: 'Mercedes', teamColor: '#27f4d2',
    position: 3, compound: 'HARD', tyreAge: 13,
    degradationS: 0.36, degradationRate: 0.024,
    gapAheadS: 7.1,
    gapLeaderS: 7.79,
    pitWindow: { opensLap: 57, closesLap: 57 },
  },
  {
    code: 'PIA', team: 'McLaren', teamColor: '#ff8000',
    position: 4, compound: 'HARD', tyreAge: 12,
    degradationS: 0.63, degradationRate: 0.005,
    gapAheadS: 1.86,
    gapLeaderS: 9.65,
    pitWindow: null,
  },
  {
    code: 'LEC', team: 'Ferrari', teamColor: '#e8002d',
    position: 5, compound: 'MEDIUM', tyreAge: 9,
    degradationS: 0.96, degradationRate: 0.161,
    gapAheadS: 0.42,
    gapLeaderS: 10.08,
    pitWindow: { opensLap: 31, closesLap: 50 },
  },
  {
    code: 'HAM', team: 'Ferrari', teamColor: '#e8002d',
    position: 6, compound: 'HARD', tyreAge: 5,
    degradationS: 0.53, degradationRate: 0.037,
    gapAheadS: 5.28,
    gapLeaderS: 15.35,
    pitWindow: { opensLap: 43, closesLap: 50 },
  },
  {
    code: 'LAW', team: 'Red Bull Racing', teamColor: '#3671c6',
    position: 7, compound: 'MEDIUM', tyreAge: 9,
    degradationS: 0.51, degradationRate: 0.112,
    gapAheadS: 16.49,
    gapLeaderS: 31.85,
    pitWindow: { opensLap: 35, closesLap: 50 },
  },
  {
    code: 'ALO', team: 'Aston Martin', teamColor: '#229971',
    position: 8, compound: 'SOFT', tyreAge: 28,
    degradationS: 0.0, degradationRate: 0.005,
    gapAheadS: 16.1,
    gapLeaderS: 47.94,
    pitWindow: null,
  },
  {
    code: 'HUL', team: 'Audi', teamColor: '#52e252',
    position: 9, compound: 'SOFT', tyreAge: 11,
    degradationS: -1.57, degradationRate: -0.549,
    gapAheadS: 7.36,
    gapLeaderS: 55.3,
    pitWindow: null,
  },
  {
    code: 'TSU', team: 'Racing Bulls', teamColor: '#6692ff',
    position: 10, compound: 'HARD', tyreAge: 12,
    degradationS: -0.1, degradationRate: -0.399,
    gapAheadS: 3.96,
    gapLeaderS: 59.26,
    pitWindow: null,
  },
  {
    code: 'LIN', team: 'Racing Bulls', teamColor: '#6692ff',
    position: 11, compound: 'MEDIUM', tyreAge: 25,
    degradationS: 1.77, degradationRate: -0.008,
    gapAheadS: 3.02,
    gapLeaderS: 62.28,
    pitWindow: { opensLap: 30, closesLap: 50 },
  },
  {
    code: 'GAS', team: 'Alpine', teamColor: '#ff87bc',
    position: 12, compound: 'HARD', tyreAge: 12,
    degradationS: 1.29, degradationRate: -0.113,
    gapAheadS: 0.31,
    gapLeaderS: 62.58,
    pitWindow: { opensLap: 30, closesLap: 50 },
  },
  {
    code: 'BOR', team: 'Audi', teamColor: '#52e252',
    position: 13, compound: 'MEDIUM', tyreAge: 19,
    degradationS: 1.21, degradationRate: 0.205,
    gapAheadS: 0.7,
    gapLeaderS: 63.29,
    pitWindow: { opensLap: 30, closesLap: 50 },
  },
  {
    code: 'ALB', team: 'Williams', teamColor: '#64c4ff',
    position: 14, compound: 'HARD', tyreAge: 4,
    degradationS: 0.0, degradationRate: 0.376,
    gapAheadS: 0.76,
    gapLeaderS: 64.05,
    pitWindow: { opensLap: 33, closesLap: 50 },
  },
  {
    code: 'SAI', team: 'Williams', teamColor: '#64c4ff',
    position: 15, compound: 'SOFT', tyreAge: 28,
    degradationS: 0.0, degradationRate: 0.279,
    gapAheadS: 2.01,
    gapLeaderS: 66.06,
    pitWindow: { opensLap: 34, closesLap: 50 },
  },
  {
    code: 'OCO', team: 'Haas F1 Team', teamColor: '#b6babd',
    position: 16, compound: 'HARD', tyreAge: 14,
    degradationS: -1.88, degradationRate: 0.049,
    gapAheadS: 1.49,
    gapLeaderS: 67.55,
    pitWindow: null,
  },
  {
    code: 'STR', team: 'Aston Martin', teamColor: '#229971',
    position: 17, compound: 'HARD', tyreAge: 15,
    degradationS: 0.13, degradationRate: -0.133,
    gapAheadS: 4.26,
    gapLeaderS: 71.81,
    pitWindow: null,
  },
  {
    code: 'COL', team: 'Alpine', teamColor: '#ff87bc',
    position: 18, compound: 'HARD', tyreAge: 9,
    degradationS: 0.54, degradationRate: 0.378,
    gapAheadS: 9.9,
    gapLeaderS: 81.71,
    pitWindow: { opensLap: 32, closesLap: 50 },
  },
  {
    code: 'PER', team: 'Cadillac', teamColor: '#c8a251',
    position: 19, compound: 'HARD', tyreAge: 1,
    degradationS: 0.0, degradationRate: 0.0,
    gapAheadS: 16.64,
    gapLeaderS: 98.35,
    pitWindow: null,
  },
  {
    code: 'BOT', team: 'Cadillac', teamColor: '#c8a251',
    position: 20, compound: 'HARD', tyreAge: 4,
    degradationS: 0.45, degradationRate: 0.0,
    gapAheadS: 1.11,
    gapLeaderS: 99.46,
    pitWindow: null,
  },
  {
    code: 'BEA', team: 'Haas F1 Team', teamColor: '#b6babd',
    position: 21, compound: 'SOFT', tyreAge: 2,
    degradationS: 0, degradationRate: 0,
    gapAheadS: null, gapLeaderS: null, pitWindow: null,
    retiredOnLap: 2,
  },
  {
    code: 'VER', team: 'Red Bull Racing', teamColor: '#3671c6',
    position: 22, compound: 'SOFT', tyreAge: 1,
    degradationS: 0, degradationRate: 0,
    gapAheadS: null, gapLeaderS: null, pitWindow: null,
    retiredOnLap: 1,
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
export const PLAN_DISTRIBUTION: {
  driver: string
  stopDistribution: Record<string, number>
  modalPlan: StintPlan[]
} = {
  driver: 'LEC',
  stopDistribution: { '1': 0.31, '2': 0.48, '3': 0.19, '4': 0.02 },
  modalPlan: [
    { compound: 'MEDIUM', laps: 18 },
    { compound: 'HARD', laps: 25 },
    { compound: 'SOFT', laps: 14 },
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
