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
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 1.5,
    sdPosition: 0.74,
    meanPoints: 22.03,
    decisionValue: 6.173,
    objective: 'points',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: 22.04 }, { plan: 'H10-H32', stops: 1, score: 21.857 }, { plan: 'H19-H23', stops: 1, score: 21.72 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.219, '3': 0.031 },
    meanPosition: 1.93,
    sdPosition: 0.94,
    meanPoints: 19.81,
    decisionValue: 8.637,
    objective: 'points',
    alternatives: [{ plan: 'H18-H24', stops: 1, score: 20.447 }, { plan: 'H19-H23', stops: 1, score: 20.377 }, { plan: 'H21-H21', stops: 1, score: 20.007 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H15-H27',
    stops: [{ lap: 45, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 3.59,
    sdPosition: 1.22,
    meanPoints: 13.72,
    decisionValue: 3.957,
    objective: 'points',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: 14.29 }, { plan: 'H19-H23', stops: 1, score: 14.257 }, { plan: 'H12-H30', stops: 1, score: 14.233 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H13-H29',
    stops: [{ lap: 43, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 2.78,
    sdPosition: 1.03,
    meanPoints: 16.2,
    decisionValue: 4.28,
    objective: 'points',
    alternatives: [{ plan: 'H6-H36', stops: 1, score: 16.7 }, { plan: 'H11-H31', stops: 1, score: 16.673 }, { plan: 'H14-H28', stops: 1, score: 16.603 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.719, '2': 0.219, '3': 0.062 },
    meanPosition: 2.31,
    sdPosition: 1.13,
    meanPoints: 18.37,
    decisionValue: 7.137,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 18.873 }, { plan: 'M9-H33', stops: 1, score: 18.667 }, { plan: 'M8-H34', stops: 1, score: 18.43 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.594, '2': 0.25, '3': 0.156 },
    meanPosition: 4.54,
    sdPosition: 1.06,
    meanPoints: 11.17,
    decisionValue: 3.933,
    objective: 'points',
    alternatives: [{ plan: 'H7-H35', stops: 1, score: 11.74 }, { plan: 'H7-H20-H15', stops: 2, score: 9.817 }, { plan: 'H7-H24-S11', stops: 2, score: 9.72 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.219, '3': 0.031 },
    meanPosition: 6.76,
    sdPosition: 0.78,
    meanPoints: 6.47,
    decisionValue: 2.257,
    objective: 'points',
    alternatives: [{ plan: 'M8-H34', stops: 1, score: 6.78 }, { plan: 'M10-H32', stops: 1, score: 6.76 }, { plan: 'M7-H35', stops: 1, score: 6.597 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 9.63,
    sdPosition: 1.45,
    meanPoints: 1.8,
    decisionValue: 1.62,
    objective: 'points',
    alternatives: [{ plan: 'S6-S25-S11', stops: 2, score: 0.753 }, { plan: 'S6-H28-M8', stops: 2, score: 0.743 }, { plan: 'S6-H25-S11', stops: 2, score: 0.64 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 16.43,
    sdPosition: 0.99,
    meanPoints: 0.0,
    decisionValue: 0.943,
    objective: 'position',
    alternatives: [{ plan: 'S14-M28', stops: 1, score: -16.5 }, { plan: 'S14-S6-H22', stops: 2, score: -17.213 }, { plan: 'S14-H6-H22', stops: 2, score: -17.227 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H29-M13',
    stops: [{ lap: 59, compound: 'MEDIUM' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 11.37,
    sdPosition: 1.09,
    meanPoints: 0.24,
    decisionValue: 0.317,
    objective: 'points',
    alternatives: [{ plan: 'H29-H13', stops: 1, score: 0.297 }, { plan: 'H29-S13', stops: 1, score: 0.29 }, { plan: 'H27-H15', stops: 1, score: 0.283 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.312 },
    meanPosition: 8.39,
    sdPosition: 0.92,
    meanPoints: 3.35,
    decisionValue: 1.48,
    objective: 'points',
    alternatives: [{ plan: 'M6-H25-S11', stops: 2, score: 2.46 }, { plan: 'M6-H15-H21', stops: 2, score: 2.457 }, { plan: 'M6-H11-H25', stops: 2, score: 2.427 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H7-H35',
    stops: [{ lap: 37, compound: 'HARD' }],
    stopDistribution: { '1': 0.719, '2': 0.25, '4': 0.031 },
    meanPosition: 9.04,
    sdPosition: 1.04,
    meanPoints: 2.35,
    decisionValue: 2.457,
    objective: 'points',
    alternatives: [{ plan: 'H6-H36', stops: 1, score: 2.437 }, { plan: 'H8-H34', stops: 1, score: 2.393 }, { plan: 'H6-H26-S10', stops: 2, score: 1.51 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.312 },
    meanPosition: 9.65,
    sdPosition: 1.22,
    meanPoints: 1.62,
    decisionValue: 1.16,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 1.75 }, { plan: 'M12-H30', stops: 1, score: 1.423 }, { plan: 'M12-M30', stops: 1, score: 1.213 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 12.86,
    sdPosition: 1.14,
    meanPoints: 0.02,
    decisionValue: 1.907,
    objective: 'position',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: -12.777 }, { plan: 'H17-H25', stops: 1, score: -12.787 }, { plan: 'H13-H29', stops: 1, score: -12.983 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 14.35,
    sdPosition: 1.8,
    meanPoints: 0.02,
    decisionValue: 1.78,
    objective: 'position',
    alternatives: [{ plan: 'S6-H21-M15', stops: 2, score: -15.41 }, { plan: 'S6-S25-S11', stops: 2, score: -15.547 }, { plan: 'S6-M6-H30', stops: 2, score: -15.627 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H27-H15',
    stops: [{ lap: 57, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.6,
    sdPosition: 0.55,
    meanPoints: 0.0,
    decisionValue: 0.313,
    objective: 'position',
    alternatives: [{ plan: 'H24-H18', stops: 1, score: -18.527 }, { plan: 'H24-M18', stops: 1, score: -18.537 }, { plan: 'H25-S17', stops: 1, score: -18.54 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H24-H18',
    stops: [{ lap: 54, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '3': 0.031 },
    meanPosition: 14.27,
    sdPosition: 1.13,
    meanPoints: 0.0,
    decisionValue: 2.73,
    objective: 'position',
    alternatives: [{ plan: 'H23-H19', stops: 1, score: -14.127 }, { plan: 'H26-H16', stops: 1, score: -14.13 }, { plan: 'H21-H21', stops: 1, score: -14.133 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 15.82,
    sdPosition: 1.28,
    meanPoints: 0.0,
    decisionValue: 1.25,
    objective: 'position',
    alternatives: [{ plan: 'H7-H35', stops: 1, score: -15.643 }, { plan: 'H10-H32', stops: 1, score: -15.74 }, { plan: 'H8-H34', stops: 1, score: -15.88 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H25-H17',
    stops: [{ lap: 55, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 18.99,
    sdPosition: 0.83,
    meanPoints: 0.0,
    decisionValue: 0.89,
    objective: 'position',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: -18.847 }, { plan: 'H19-H23', stops: 1, score: -18.85 }, { plan: 'H23-H19', stops: 1, score: -18.857 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H15-H27',
    stops: [{ lap: 45, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 18.09,
    sdPosition: 0.56,
    meanPoints: 0.0,
    decisionValue: 0.707,
    objective: 'position',
    alternatives: [{ plan: 'H18-H24', stops: 1, score: -18.023 }, { plan: 'H19-H23', stops: 1, score: -18.073 }, { plan: 'H16-H26', stops: 1, score: -18.087 }],
  },
}
