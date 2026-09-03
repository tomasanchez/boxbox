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
    plan: 'H21-H21',
    stops: [{ lap: 51, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.094, '3': 0.031 },
    meanPosition: 1.59,
    sdPosition: 0.73,
    meanPoints: 21.44,
    decisionValue: 8.473,
    objective: 'points',
    alternatives: [{ plan: 'H16-H26', stops: 1, score: 21.717 }, { plan: 'H14-H28', stops: 1, score: 21.67 }, { plan: 'H20-H22', stops: 1, score: 21.627 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 1.9,
    sdPosition: 0.95,
    meanPoints: 20.0,
    decisionValue: 5.433,
    objective: 'points',
    alternatives: [{ plan: 'H18-H24', stops: 1, score: 20.637 }, { plan: 'H19-H23', stops: 1, score: 20.61 }, { plan: 'H20-H22', stops: 1, score: 20.32 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 3.51,
    sdPosition: 1.27,
    meanPoints: 14.06,
    decisionValue: 4.157,
    objective: 'points',
    alternatives: [{ plan: 'H19-H23', stops: 1, score: 14.747 }, { plan: 'H17-H25', stops: 1, score: 14.64 }, { plan: 'H18-H24', stops: 1, score: 14.633 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 2.82,
    sdPosition: 1.07,
    meanPoints: 16.07,
    decisionValue: 3.65,
    objective: 'points',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: 16.667 }, { plan: 'H13-H29', stops: 1, score: 16.643 }, { plan: 'H11-H31', stops: 1, score: 16.53 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M12-H30',
    stops: [{ lap: 42, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.156, '4': 0.031 },
    meanPosition: 2.4,
    sdPosition: 1.07,
    meanPoints: 17.83,
    decisionValue: 8.473,
    objective: 'points',
    alternatives: [{ plan: 'M8-H34', stops: 1, score: 18.4 }, { plan: 'M7-H35', stops: 1, score: 18.35 }, { plan: 'M9-H33', stops: 1, score: 17.783 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H9-H33',
    stops: [{ lap: 39, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.312 },
    meanPosition: 4.47,
    sdPosition: 1.16,
    meanPoints: 11.41,
    decisionValue: 2.69,
    objective: 'points',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: 11.8 }, { plan: 'H12-H30', stops: 1, score: 11.763 }, { plan: 'H8-H34', stops: 1, score: 11.743 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M11-H31',
    stops: [{ lap: 41, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 6.82,
    sdPosition: 0.67,
    meanPoints: 6.36,
    decisionValue: 1.15,
    objective: 'points',
    alternatives: [{ plan: 'M10-H32', stops: 1, score: 6.573 }, { plan: 'M9-H33', stops: 1, score: 6.56 }, { plan: 'M12-H30', stops: 1, score: 6.433 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.625, '2': 0.344, '3': 0.031 },
    meanPosition: 9.87,
    sdPosition: 1.68,
    meanPoints: 1.66,
    decisionValue: 1.783,
    objective: 'points',
    alternatives: [{ plan: 'S6-H24-H12', stops: 2, score: 1.053 }, { plan: 'S6-S25-S11', stops: 2, score: 0.97 }, { plan: 'S6-H20-S16', stops: 2, score: 0.953 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 16.32,
    sdPosition: 0.98,
    meanPoints: 0.0,
    decisionValue: 1.043,
    objective: 'position',
    alternatives: [{ plan: 'S13-H29', stops: 1, score: -16.323 }, { plan: 'S11-H31', stops: 1, score: -16.477 }, { plan: 'S14-M28', stops: 1, score: -16.483 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H29-H13',
    stops: [{ lap: 59, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 11.22,
    sdPosition: 1.18,
    meanPoints: 0.33,
    decisionValue: 0.41,
    objective: 'points',
    alternatives: [{ plan: 'H29-S13', stops: 1, score: 0.41 }, { plan: 'H28-H14', stops: 1, score: 0.4 }, { plan: 'H29-M13', stops: 1, score: 0.397 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.656, '2': 0.344 },
    meanPosition: 8.5,
    sdPosition: 1.02,
    meanPoints: 3.2,
    decisionValue: 1.027,
    objective: 'points',
    alternatives: [{ plan: 'M6-H20-H16', stops: 2, score: 2.823 }, { plan: 'M6-H23-H13', stops: 2, score: 2.773 }, { plan: 'M6-H25-S11', stops: 2, score: 2.743 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H9-H33',
    stops: [{ lap: 39, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.125, '3': 0.031 },
    meanPosition: 9.12,
    sdPosition: 1.13,
    meanPoints: 2.27,
    decisionValue: 1.83,
    objective: 'points',
    alternatives: [{ plan: 'H12-H30', stops: 1, score: 2.37 }, { plan: 'H17-H25', stops: 1, score: 2.143 }, { plan: 'H12-M30', stops: 1, score: 2.033 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.719, '2': 0.281 },
    meanPosition: 9.88,
    sdPosition: 1.29,
    meanPoints: 1.41,
    decisionValue: 1.04,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 1.723 }, { plan: 'M8-H34', stops: 1, score: 1.463 }, { plan: 'M7-H24-S11', stops: 2, score: 0.987 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.719, '2': 0.25, '3': 0.031 },
    meanPosition: 13.57,
    sdPosition: 1.85,
    meanPoints: 0.06,
    decisionValue: 0.117,
    objective: 'points',
    alternatives: [{ plan: 'H10-H32', stops: 1, score: 0.027 }, { plan: 'H31-M11', stops: 1, score: 0.01 }, { plan: 'H28-S14', stops: 1, score: 0.003 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 14.26,
    sdPosition: 1.94,
    meanPoints: 0.03,
    decisionValue: 1.56,
    objective: 'position',
    alternatives: [{ plan: 'S6-H29-H7', stops: 2, score: -15.363 }, { plan: 'S6-S25-S11', stops: 2, score: -15.37 }, { plan: 'S6-M25-S11', stops: 2, score: -15.537 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H21-H21',
    stops: [{ lap: 51, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.41,
    sdPosition: 0.6,
    meanPoints: 0.0,
    decisionValue: 0.387,
    objective: 'position',
    alternatives: [{ plan: 'H22-H20', stops: 1, score: -18.347 }, { plan: 'H23-H19', stops: 1, score: -18.36 }, { plan: 'H16-H26', stops: 1, score: -18.37 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.094, '3': 0.031 },
    meanPosition: 14.31,
    sdPosition: 1.18,
    meanPoints: 0.0,
    decisionValue: 2.643,
    objective: 'position',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: -14.03 }, { plan: 'H26-H16', stops: 1, score: -14.04 }, { plan: 'H19-H23', stops: 1, score: -14.05 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H13-H29',
    stops: [{ lap: 43, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 15.82,
    sdPosition: 1.21,
    meanPoints: 0.0,
    decisionValue: 1.107,
    objective: 'position',
    alternatives: [{ plan: 'H9-H33', stops: 1, score: -15.67 }, { plan: 'H11-H31', stops: 1, score: -15.697 }, { plan: 'H10-H32', stops: 1, score: -15.71 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H19-H23',
    stops: [{ lap: 49, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 18.72,
    sdPosition: 0.83,
    meanPoints: 0.0,
    decisionValue: 0.877,
    objective: 'position',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: -18.67 }, { plan: 'H20-H22', stops: 1, score: -18.673 }, { plan: 'H16-H26', stops: 1, score: -18.743 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H17-H25',
    stops: [{ lap: 47, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.031, '3': 0.031 },
    meanPosition: 18.08,
    sdPosition: 0.59,
    meanPoints: 0.0,
    decisionValue: 1.087,
    objective: 'position',
    alternatives: [{ plan: 'H19-H23', stops: 1, score: -18.033 }, { plan: 'H15-H27', stops: 1, score: -18.067 }, { plan: 'H14-H28', stops: 1, score: -18.073 }],
  },
}
