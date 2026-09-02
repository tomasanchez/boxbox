/**
 * Planes recomendados por el algoritmo genético, uno por auto.
 *
 * **Generado. No editar a mano**: sale de
 * `apps/ml/scripts/strategy_search.py --out docs/research/strategy-zandvoort.json`,
 * sobre la foto de 2026 R12 Zandvoort en la vuelta 30.
 *
 * Cada plan es el que mejor le va al auto sobre 300 carreras sorteadas, con el
 * desgaste, la pérdida de boxes y el safety car sacados de las distribuciones
 * medidas. El safety car entra de verdad: sale en el 60% de las carreras
 * sorteadas, en una vuelta sorteada de dónde salen de verdad, y dura cinco
 * vueltas — parar adentro de esa ventana cuesta 19,5 s en vez de 22,6.
 *
 * `objective` dice qué estaba maximizando. Para el que puede sumar, puntos
 * esperados. Para el que no llega a la zona de puntos, ese objetivo está **plano
 * en cero** y el algoritmo no tiene nada que escalar: ahí pasa a posición
 * esperada. No es un matiz — con puntos, un auto 18.º terminaba con la población
 * repartida casi en partes iguales entre una y cuatro paradas, que es ruido.
 *
 * `stopDistribution` es cuánto de la población final se quedó en cada cantidad
 * de paradas: es la confianza del algoritmo, no una probabilidad de la carrera.
 */

export interface RecommendedPlan {
  /** Puesto desde el que arranca el plan. */
  fromPosition: number
  /** Las tandas, como las diría el muro: «H17-H25». */
  plan: string
  stops: { lap: number; compound: string }[]
  /** Cuánto de la población final quedó en cada cantidad de paradas. */
  stopDistribution: Record<string, number>
  meanPosition: number
  meanPoints: number
  /** Qué se maximizó: `points` o `position`. */
  objective: string
  alternatives: { plan: string; stops: number; score: number }[]
}

export const PLANS: Record<string, RecommendedPlan> = {
  ANT: {
    fromPosition: 1,
    plan: 'H17-H25',
    stops: [{ lap: 47, compound: 'HARD' }],
    stopDistribution: { '1': 0.969, '2': 0.031 },
    meanPosition: 1.6,
    meanPoints: 21.52,
    objective: 'points',
    alternatives: [{ plan: 'H16-H26', stops: 1, score: 21.923 }, { plan: 'H12-H30', stops: 1, score: 21.54 }, { plan: 'H15-H27', stops: 1, score: 21.537 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H18-H24',
    stops: [{ lap: 48, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.094, '3': 0.031 },
    meanPosition: 1.9,
    meanPoints: 19.88,
    objective: 'points',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: 20.547 }, { plan: 'H17-H25', stops: 1, score: 20.39 }, { plan: 'H13-H29', stops: 1, score: 20.307 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.156, '3': 0.062 },
    meanPosition: 3.48,
    meanPoints: 14.17,
    objective: 'points',
    alternatives: [{ plan: 'H13-H29', stops: 1, score: 14.327 }, { plan: 'H8-H34', stops: 1, score: 14.31 }, { plan: 'H15-H27', stops: 1, score: 14.307 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H11-H31',
    stops: [{ lap: 41, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '3': 0.031 },
    meanPosition: 2.74,
    meanPoints: 16.31,
    objective: 'points',
    alternatives: [{ plan: 'H8-H34', stops: 1, score: 16.71 }, { plan: 'H7-H35', stops: 1, score: 16.463 }, { plan: 'H17-H25', stops: 1, score: 16.277 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 2.43,
    meanPoints: 17.86,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 19.107 }, { plan: 'M11-H31', stops: 1, score: 18.237 }, { plan: 'M12-H30', stops: 1, score: 17.903 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.094, '3': 0.031 },
    meanPosition: 4.51,
    meanPoints: 11.29,
    objective: 'points',
    alternatives: [{ plan: 'H10-H32', stops: 1, score: 11.723 }, { plan: 'H9-H33', stops: 1, score: 11.66 }, { plan: 'H13-H29', stops: 1, score: 11.273 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.125, '3': 0.062 },
    meanPosition: 6.74,
    meanPoints: 6.53,
    objective: 'points',
    alternatives: [{ plan: 'M10-H32', stops: 1, score: 6.773 }, { plan: 'M9-H33', stops: 1, score: 6.773 }, { plan: 'M7-H35', stops: 1, score: 6.77 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S18-H24',
    stops: [{ lap: 48, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 9.03,
    meanPoints: 2.32,
    objective: 'points',
    alternatives: [{ plan: 'S20-H22', stops: 1, score: 2.4 }, { plan: 'S22-H20', stops: 1, score: 2.377 }, { plan: 'S21-H21', stops: 1, score: 2.377 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S34-H8',
    stops: [{ lap: 64, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.094, '3': 0.031 },
    meanPosition: 16.21,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'S29-H13', stops: 1, score: -16.12 }, { plan: 'S32-H10', stops: 1, score: -16.137 }, { plan: 'S30-H12', stops: 1, score: -16.147 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H36-H6',
    stops: [{ lap: 66, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '4': 0.031 },
    meanPosition: 11.57,
    meanPoints: 0.22,
    objective: 'points',
    alternatives: [{ plan: 'H35-H7', stops: 1, score: 0.317 }, { plan: 'H34-H8', stops: 1, score: 0.317 }, { plan: 'H33-H9', stops: 1, score: 0.303 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 8.43,
    meanPoints: 3.28,
    objective: 'points',
    alternatives: [{ plan: 'M8-H34', stops: 1, score: 3.227 }, { plan: 'M6-S36', stops: 1, score: 2.967 }, { plan: 'M10-H32', stops: 1, score: 2.943 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 9.04,
    meanPoints: 2.36,
    objective: 'points',
    alternatives: [{ plan: 'H12-H30', stops: 1, score: 2.177 }, { plan: 'H6-S36', stops: 1, score: 2.023 }, { plan: 'H6-M36', stops: 1, score: 1.94 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 9.66,
    meanPoints: 1.66,
    objective: 'points',
    alternatives: [{ plan: 'M8-H34', stops: 1, score: 1.597 }, { plan: 'M7-H35', stops: 1, score: 1.58 }, { plan: 'M6-S36', stops: 1, score: 1.473 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H17-H25',
    stops: [{ lap: 47, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '4': 0.031 },
    meanPosition: 12.89,
    meanPoints: 0.01,
    objective: 'position',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: -12.81 }, { plan: 'H19-H23', stops: 1, score: -12.813 }, { plan: 'H14-H28', stops: 1, score: -12.9 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S15-H27',
    stops: [{ lap: 45, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 13.78,
    meanPoints: 0.02,
    objective: 'position',
    alternatives: [{ plan: 'S13-H29', stops: 1, score: -13.68 }, { plan: 'S17-H25', stops: 1, score: -13.807 }, { plan: 'S12-H30', stops: 1, score: -13.957 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H22-H20',
    stops: [{ lap: 52, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 18.59,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'H26-H16', stops: 1, score: -18.52 }, { plan: 'H19-H23', stops: 1, score: -18.52 }, { plan: 'H20-H22', stops: 1, score: -18.527 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H22-H20',
    stops: [{ lap: 52, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '3': 0.031 },
    meanPosition: 14.17,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'H24-H18', stops: 1, score: -14.133 }, { plan: 'H19-H23', stops: 1, score: -14.137 }, { plan: 'H25-H17', stops: 1, score: -14.14 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 15.87,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'H8-H34', stops: 1, score: -15.713 }, { plan: 'H11-H31', stops: 1, score: -15.887 }, { plan: 'H7-H35', stops: 1, score: -15.9 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H19-H23',
    stops: [{ lap: 49, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 18.86,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'H20-H22', stops: 1, score: -18.823 }, { plan: 'H22-H20', stops: 1, score: -18.85 }, { plan: 'H17-H25', stops: 1, score: -18.897 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H17-H25',
    stops: [{ lap: 47, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 18.06,
    meanPoints: 0.0,
    objective: 'position',
    alternatives: [{ plan: 'H18-H24', stops: 1, score: -18.02 }, { plan: 'H14-H28', stops: 1, score: -18.037 }, { plan: 'H13-H29', stops: 1, score: -18.04 }],
  },
}
