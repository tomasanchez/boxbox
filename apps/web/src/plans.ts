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
 * sorteadas, en una vuelta sorteada de dónde salen de verdad, dura cinco vueltas
 * y es el **mismo** para todos los autos de esa carrera — uno que ayuda a alguno
 * perjudica a otro, y sortearlo por auto borraría eso.
 *
 * `objective` dice qué estaba maximizando. Para el que puede sumar, puntos
 * esperados. Para el que no llega a la zona de puntos ese objetivo está **plano
 * en cero** y el algoritmo no tiene nada que escalar: ahí pasa a posición.
 *
 * `stopDistribution` es cuánto de la población final se quedó en cada cantidad
 * de paradas: es la confianza de la búsqueda, no una probabilidad de la carrera.
 *
 * `decisionValue` es lo que vale elegir bien: el mejor plan menos el peor de la
 * población final. Cerca de cero significa que da igual lo que haga, y conviene
 * saberlo antes de presentar una recomendación como si importara.
 *
 * Ver `docs/research/strategy-search.md`.
 */

export interface RecommendedPlan {
  /** Puesto desde el que arranca el plan. */
  fromPosition: number
  /** Las tandas, como las diría el muro: «H16-H26». */
  plan: string
  stops: { lap: number; compound: string }[]
  /** Cuánto de la población final quedó en cada cantidad de paradas. */
  stopDistribution: Record<string, number>
  meanPosition: number
  /** Dispersión del puesto de llegada: cuánto riesgo toma el plan. */
  sdPosition: number
  meanPoints: number
  /** Mejor plan menos el peor: cuánto vale elegir bien. */
  decisionValue: number
  /** Qué se maximizó: `points` o `position`. */
  objective: string
  alternatives: { plan: string; stops: number; score: number }[]
}

export const PLANS: Record<string, RecommendedPlan> = {
  ANT: {
    fromPosition: 1,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 1.85,
    sdPosition: 0.91,
    meanPoints: 20.16,
    decisionValue: 4.493,
    objective: 'points',
    alternatives: [{ plan: 'H22-H20', stops: 1, score: 20.177 }, { plan: 'H14-H28', stops: 1, score: 20.165 }, { plan: 'H16-M26', stops: 1, score: 19.603 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 2.16,
    sdPosition: 1.04,
    meanPoints: 18.86,
    decisionValue: 5.2,
    objective: 'points',
    alternatives: [{ plan: 'H17-H25', stops: 1, score: 18.992 }, { plan: 'H19-H23', stops: 1, score: 18.946 }, { plan: 'H22-H20', stops: 1, score: 18.806 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.625, '2': 0.312, '4': 0.062 },
    meanPosition: 3.74,
    sdPosition: 1.19,
    meanPoints: 13.29,
    decisionValue: 5.598,
    objective: 'points',
    alternatives: [{ plan: 'H20-H22', stops: 1, score: 13.33 }, { plan: 'H18-H24', stops: 1, score: 13.271 }, { plan: 'H10-H32', stops: 1, score: 13.02 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H12-H30',
    stops: [{ lap: 42, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 3.02,
    sdPosition: 1.07,
    meanPoints: 15.41,
    decisionValue: 2.707,
    objective: 'points',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: 15.309 }, { plan: 'H10-H32', stops: 1, score: 15.159 }, { plan: 'H18-H24', stops: 1, score: 15.023 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M12-H30',
    stops: [{ lap: 42, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 2.73,
    sdPosition: 1.07,
    meanPoints: 16.45,
    decisionValue: 2.319,
    objective: 'points',
    alternatives: [{ plan: 'M6-H36', stops: 1, score: 16.529 }, { plan: 'M15-H27', stops: 1, score: 16.225 }, { plan: 'M10-H32', stops: 1, score: 16.222 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H12-H30',
    stops: [{ lap: 42, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.281, '3': 0.031 },
    meanPosition: 4.61,
    sdPosition: 1.02,
    meanPoints: 11.0,
    decisionValue: 3.047,
    objective: 'points',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: 11.072 }, { plan: 'H11-H31', stops: 1, score: 10.974 }, { plan: 'H18-H24', stops: 1, score: 10.893 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M12-H30',
    stops: [{ lap: 42, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 6.85,
    sdPosition: 0.67,
    meanPoints: 6.29,
    decisionValue: 0.752,
    objective: 'points',
    alternatives: [{ plan: 'M10-H32', stops: 1, score: 6.257 }, { plan: 'M6-H36', stops: 1, score: 6.221 }, { plan: 'M15-H27', stops: 1, score: 6.183 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 10.31,
    sdPosition: 1.81,
    meanPoints: 1.3,
    decisionValue: 0.903,
    objective: 'points',
    alternatives: [{ plan: 'S6-S25-S11', stops: 2, score: 0.589 }, { plan: 'S6-H25-S11', stops: 2, score: 0.583 }, { plan: 'S6-H18-M18', stops: 2, score: 0.557 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 16.68,
    sdPosition: 0.84,
    meanPoints: 0.0,
    decisionValue: 0.575,
    objective: 'position',
    alternatives: [{ plan: 'S14-M28', stops: 1, score: -16.738 }, { plan: 'S11-H31', stops: 1, score: -16.754 }, { plan: 'S8-H34', stops: 1, score: -16.871 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H29-H13',
    stops: [{ lap: 59, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 11.52,
    sdPosition: 1.3,
    meanPoints: 0.26,
    decisionValue: 0.243,
    objective: 'points',
    alternatives: [{ plan: 'H29-S13', stops: 1, score: 0.252 }, { plan: 'H29-M13', stops: 1, score: 0.247 }, { plan: 'H25-H17', stops: 1, score: 0.243 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 8.67,
    sdPosition: 1.05,
    meanPoints: 2.94,
    decisionValue: 0.714,
    objective: 'points',
    alternatives: [{ plan: 'M6-H14-H22', stops: 2, score: 2.592 }, { plan: 'M6-H24-S12', stops: 2, score: 2.547 }, { plan: 'M6-S25-S11', stops: 2, score: 2.322 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.312 },
    meanPosition: 9.53,
    sdPosition: 1.5,
    meanPoints: 1.94,
    decisionValue: 0.925,
    objective: 'points',
    alternatives: [{ plan: 'H8-H34', stops: 1, score: 1.992 }, { plan: 'H9-H33', stops: 1, score: 1.938 }, { plan: 'H6-H23-H13', stops: 2, score: 1.382 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 10.18,
    sdPosition: 1.57,
    meanPoints: 1.27,
    decisionValue: 0.728,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 1.228 }, { plan: 'M9-H33', stops: 1, score: 1.163 }, { plan: 'M10-H32', stops: 1, score: 1.144 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 13.54,
    sdPosition: 1.32,
    meanPoints: 0.01,
    decisionValue: 1.358,
    objective: 'position',
    alternatives: [{ plan: 'H19-H23', stops: 1, score: -13.494 }, { plan: 'H18-H24', stops: 1, score: -13.552 }, { plan: 'H22-H20', stops: 1, score: -13.569 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 14.88,
    sdPosition: 1.7,
    meanPoints: 0.01,
    decisionValue: 0.997,
    objective: 'position',
    alternatives: [{ plan: 'S6-H25-M11', stops: 2, score: -15.68 }, { plan: 'S6-H12-M24', stops: 2, score: -15.72 }, { plan: 'S6-S25-S11', stops: 2, score: -15.773 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H23-H19',
    stops: [{ lap: 53, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.45,
    sdPosition: 0.59,
    meanPoints: 0.0,
    decisionValue: 0.421,
    objective: 'position',
    alternatives: [{ plan: 'H25-H17', stops: 1, score: -18.442 }, { plan: 'H26-H16', stops: 1, score: -18.462 }, { plan: 'H18-H24', stops: 1, score: -18.469 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H22-H20',
    stops: [{ lap: 52, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 14.46,
    sdPosition: 1.14,
    meanPoints: 0.0,
    decisionValue: 1.338,
    objective: 'position',
    alternatives: [{ plan: 'H24-H18', stops: 1, score: -14.48 }, { plan: 'H22-S20', stops: 1, score: -14.52 }, { plan: 'H25-H17', stops: 1, score: -14.522 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.219, '3': 0.031 },
    meanPosition: 16.07,
    sdPosition: 1.3,
    meanPoints: 0.0,
    decisionValue: 1.035,
    objective: 'position',
    alternatives: [{ plan: 'H9-H33', stops: 1, score: -16.058 }, { plan: 'H6-H14-H22', stops: 2, score: -16.511 }, { plan: 'H6-H24-S12', stops: 2, score: -16.55 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H21-H21',
    stops: [{ lap: 51, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.125, '3': 0.031 },
    meanPosition: 18.9,
    sdPosition: 0.83,
    meanPoints: 0.0,
    decisionValue: 0.948,
    objective: 'position',
    alternatives: [{ plan: 'H23-H19', stops: 1, score: -18.902 }, { plan: 'H19-H23', stops: 1, score: -18.908 }, { plan: 'H25-H17', stops: 1, score: -18.926 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H21-H21',
    stops: [{ lap: 51, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.22,
    sdPosition: 0.59,
    meanPoints: 0.0,
    decisionValue: 0.6,
    objective: 'position',
    alternatives: [{ plan: 'H18-H24', stops: 1, score: -18.205 }, { plan: 'H15-H27', stops: 1, score: -18.209 }, { plan: 'H23-H19', stops: 1, score: -18.23 }],
  },
}
