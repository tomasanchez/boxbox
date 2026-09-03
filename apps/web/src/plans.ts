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
    plan: 'H19-H23',
    stops: [{ lap: 49, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.188, '3': 0.031 },
    meanPosition: 1.88,
    sdPosition: 0.86,
    meanPoints: 19.93,
    decisionValue: 7.893,
    objective: 'points',
    alternatives: [{ plan: 'H20-H22', stops: 1, score: 20.467 }, { plan: 'H21-H21', stops: 1, score: 20.027 }, { plan: 'H13-H29', stops: 1, score: 19.793 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H19-H23',
    stops: [{ lap: 49, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.062, '3': 0.031 },
    meanPosition: 2.05,
    sdPosition: 0.96,
    meanPoints: 19.21,
    decisionValue: 7.497,
    objective: 'points',
    alternatives: [{ plan: 'H17-H25', stops: 1, score: 19.173 }, { plan: 'H15-H27', stops: 1, score: 19.143 }, { plan: 'H18-H24', stops: 1, score: 19.12 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H16-H26',
    stops: [{ lap: 46, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.156, '3': 0.062 },
    meanPosition: 3.64,
    sdPosition: 1.19,
    meanPoints: 13.58,
    decisionValue: 4.573,
    objective: 'points',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: 13.717 }, { plan: 'H18-H24', stops: 1, score: 13.7 }, { plan: 'H15-H27', stops: 1, score: 13.643 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H13-H29',
    stops: [{ lap: 43, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 3.1,
    sdPosition: 0.99,
    meanPoints: 15.04,
    decisionValue: 3.437,
    objective: 'points',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: 15.67 }, { plan: 'H12-H30', stops: 1, score: 15.613 }, { plan: 'H18-H24', stops: 1, score: 15.227 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.656, '2': 0.25, '3': 0.094 },
    meanPosition: 2.77,
    sdPosition: 1.29,
    meanPoints: 16.65,
    decisionValue: 5.247,
    objective: 'points',
    alternatives: [{ plan: 'M9-H33', stops: 1, score: 16.673 }, { plan: 'M11-H31', stops: 1, score: 16.653 }, { plan: 'M10-H32', stops: 1, score: 16.63 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H11-H31',
    stops: [{ lap: 41, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 4.62,
    sdPosition: 1.07,
    meanPoints: 11.04,
    decisionValue: 2.65,
    objective: 'points',
    alternatives: [{ plan: 'H12-H30', stops: 1, score: 11.367 }, { plan: 'H14-H28', stops: 1, score: 11.34 }, { plan: 'H13-H29', stops: 1, score: 11.08 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M7-H35',
    stops: [{ lap: 37, compound: 'HARD' }],
    stopDistribution: { '1': 0.656, '2': 0.25, '3': 0.094 },
    meanPosition: 6.89,
    sdPosition: 0.76,
    meanPoints: 6.22,
    decisionValue: 1.693,
    objective: 'points',
    alternatives: [{ plan: 'M9-H33', stops: 1, score: 6.46 }, { plan: 'M10-H32', stops: 1, score: 6.453 }, { plan: 'M11-H31', stops: 1, score: 6.447 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.188, '3': 0.031 },
    meanPosition: 10.38,
    sdPosition: 1.77,
    meanPoints: 1.23,
    decisionValue: 1.497,
    objective: 'points',
    alternatives: [{ plan: 'S6-H12-S24', stops: 2, score: 0.597 }, { plan: 'S6-H14-S22', stops: 2, score: 0.543 }, { plan: 'S6-H6-H30', stops: 2, score: 0.527 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 16.62,
    sdPosition: 0.87,
    meanPoints: 0.0,
    decisionValue: 0.807,
    objective: 'position',
    alternatives: [{ plan: 'S12-H30', stops: 1, score: -16.6 }, { plan: 'S14-M28', stops: 1, score: -16.717 }, { plan: 'S13-H29', stops: 1, score: -16.727 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H29-H13',
    stops: [{ lap: 59, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 11.46,
    sdPosition: 1.34,
    meanPoints: 0.31,
    decisionValue: 0.38,
    objective: 'points',
    alternatives: [{ plan: 'H29-S13', stops: 1, score: 0.37 }, { plan: 'H29-M13', stops: 1, score: 0.303 }, { plan: 'H25-H17', stops: 1, score: 0.277 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.656, '2': 0.344 },
    meanPosition: 8.7,
    sdPosition: 1.13,
    meanPoints: 2.93,
    decisionValue: 0.92,
    objective: 'points',
    alternatives: [{ plan: 'M6-H13-H23', stops: 2, score: 2.63 }, { plan: 'M6-H25-S11', stops: 2, score: 2.607 }, { plan: 'M6-H27-H9', stops: 2, score: 2.6 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 9.46,
    sdPosition: 1.59,
    meanPoints: 2.1,
    decisionValue: 1.65,
    objective: 'points',
    alternatives: [{ plan: 'H11-H31', stops: 1, score: 2.087 }, { plan: 'H7-H35', stops: 1, score: 2.087 }, { plan: 'H10-H32', stops: 1, score: 2.06 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.625, '2': 0.312, '3': 0.062 },
    meanPosition: 10.25,
    sdPosition: 1.52,
    meanPoints: 1.17,
    decisionValue: 1.313,
    objective: 'points',
    alternatives: [{ plan: 'M7-H35', stops: 1, score: 1.38 }, { plan: 'M11-H31', stops: 1, score: 1.14 }, { plan: 'M12-H30', stops: 1, score: 1.057 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H19-H23',
    stops: [{ lap: 49, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 13.51,
    sdPosition: 1.2,
    meanPoints: 0.0,
    decisionValue: 1.6,
    objective: 'position',
    alternatives: [{ plan: 'H17-H25', stops: 1, score: -13.363 }, { plan: 'H16-H26', stops: 1, score: -13.373 }, { plan: 'H21-H21', stops: 1, score: -13.543 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.188, '3': 0.031 },
    meanPosition: 15.07,
    sdPosition: 1.6,
    meanPoints: 0.01,
    decisionValue: 2.053,
    objective: 'position',
    alternatives: [{ plan: 'S6-H16-M20', stops: 2, score: -15.543 }, { plan: 'S6-S6-H30', stops: 2, score: -15.62 }, { plan: 'S6-H25-S11', stops: 2, score: -15.663 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H25-H17',
    stops: [{ lap: 55, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 18.5,
    sdPosition: 0.56,
    meanPoints: 0.0,
    decisionValue: 0.427,
    objective: 'position',
    alternatives: [{ plan: 'H23-H19', stops: 1, score: -18.407 }, { plan: 'H21-H21', stops: 1, score: -18.41 }, { plan: 'H17-H25', stops: 1, score: -18.417 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H25-H17',
    stops: [{ lap: 55, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.125, '3': 0.094 },
    meanPosition: 14.5,
    sdPosition: 1.12,
    meanPoints: 0.0,
    decisionValue: 2.393,
    objective: 'position',
    alternatives: [{ plan: 'H19-H23', stops: 1, score: -14.323 }, { plan: 'H21-H21', stops: 1, score: -14.323 }, { plan: 'H24-H18', stops: 1, score: -14.4 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.719, '2': 0.281 },
    meanPosition: 16.02,
    sdPosition: 1.34,
    meanPoints: 0.0,
    decisionValue: 0.953,
    objective: 'position',
    alternatives: [{ plan: 'H7-H35', stops: 1, score: -15.843 }, { plan: 'H10-H32', stops: 1, score: -15.873 }, { plan: 'H13-H29', stops: 1, score: -15.923 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H22-H20',
    stops: [{ lap: 52, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 18.91,
    sdPosition: 0.82,
    meanPoints: 0.0,
    decisionValue: 0.843,
    objective: 'position',
    alternatives: [{ plan: 'H20-H22', stops: 1, score: -18.87 }, { plan: 'H19-H23', stops: 1, score: -18.897 }, { plan: 'H24-H18', stops: 1, score: -18.917 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H18-H24',
    stops: [{ lap: 48, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 18.18,
    sdPosition: 0.6,
    meanPoints: 0.0,
    decisionValue: 0.617,
    objective: 'position',
    alternatives: [{ plan: 'H16-H26', stops: 1, score: -18.163 }, { plan: 'H20-H22', stops: 1, score: -18.17 }, { plan: 'H14-H28', stops: 1, score: -18.24 }],
  },
}
