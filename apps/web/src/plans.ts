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
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 1.86,
    sdPosition: 0.88,
    meanPoints: 20.09,
    decisionValue: 5.097,
    objective: 'points',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: 20.28 }, { plan: 'H17-H25', stops: 1, score: 20.172 }, { plan: 'H20-S22', stops: 1, score: 19.826 }],
  },
  NOR: {
    fromPosition: 2,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 2.14,
    sdPosition: 1.0,
    meanPoints: 18.9,
    decisionValue: 5.255,
    objective: 'points',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: 18.944 }, { plan: 'H17-H25', stops: 1, score: 18.857 }, { plan: 'H20-S22', stops: 1, score: 18.562 }],
  },
  RUS: {
    fromPosition: 3,
    plan: 'H14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 3.74,
    sdPosition: 1.24,
    meanPoints: 13.36,
    decisionValue: 2.591,
    objective: 'points',
    alternatives: [{ plan: 'H20-H22', stops: 1, score: 13.348 }, { plan: 'H10-H32', stops: 1, score: 13.342 }, { plan: 'H19-H23', stops: 1, score: 13.315 }],
  },
  PIA: {
    fromPosition: 4,
    plan: 'H10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 3.06,
    sdPosition: 1.15,
    meanPoints: 15.36,
    decisionValue: 2.696,
    objective: 'points',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: 15.389 }, { plan: 'H11-H31', stops: 1, score: 15.307 }, { plan: 'H16-H26', stops: 1, score: 15.077 }],
  },
  LEC: {
    fromPosition: 5,
    plan: 'M10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 2.74,
    sdPosition: 1.12,
    meanPoints: 16.55,
    decisionValue: 3.021,
    objective: 'points',
    alternatives: [{ plan: 'M11-H31', stops: 1, score: 16.549 }, { plan: 'M9-H33', stops: 1, score: 16.2 }, { plan: 'M16-H26', stops: 1, score: 15.933 }],
  },
  HAM: {
    fromPosition: 6,
    plan: 'H10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 4.58,
    sdPosition: 1.15,
    meanPoints: 11.13,
    decisionValue: 1.96,
    objective: 'points',
    alternatives: [{ plan: 'H13-H29', stops: 1, score: 11.06 }, { plan: 'H16-H26', stops: 1, score: 10.858 }, { plan: 'H7-H35', stops: 1, score: 10.814 }],
  },
  LAW: {
    fromPosition: 7,
    plan: 'M10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.812, '2': 0.188 },
    meanPosition: 6.82,
    sdPosition: 0.73,
    meanPoints: 6.35,
    decisionValue: 0.838,
    objective: 'points',
    alternatives: [{ plan: 'M14-H28', stops: 1, score: 6.25 }, { plan: 'M22-S20', stops: 1, score: 5.929 }, { plan: 'M10-H13-M19', stops: 2, score: 5.616 }],
  },
  ALO: {
    fromPosition: 8,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.125, '3': 0.031 },
    meanPosition: 10.38,
    sdPosition: 1.88,
    meanPoints: 1.3,
    decisionValue: 1.3,
    objective: 'points',
    alternatives: [{ plan: 'S6-H25-H11', stops: 2, score: 0.629 }, { plan: 'S6-S25-S11', stops: 2, score: 0.603 }, { plan: 'S6-H6-H30', stops: 2, score: 0.431 }],
  },
  HUL: {
    fromPosition: 9,
    plan: 'S14-H28',
    stops: [{ lap: 44, compound: 'HARD' }],
    stopDistribution: { '1': 0.969, '2': 0.031 },
    meanPosition: 16.63,
    sdPosition: 0.87,
    meanPoints: 0.0,
    decisionValue: 0.537,
    objective: 'position',
    alternatives: [{ plan: 'S13-H29', stops: 1, score: -16.686 }, { plan: 'S14-M28', stops: 1, score: -16.768 }, { plan: 'S12-M30', stops: 1, score: -16.863 }],
  },
  TSU: {
    fromPosition: 10,
    plan: 'H28-H14',
    stops: [{ lap: 58, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 11.58,
    sdPosition: 1.28,
    meanPoints: 0.23,
    decisionValue: 0.257,
    objective: 'points',
    alternatives: [{ plan: 'H27-H15', stops: 1, score: 0.247 }, { plan: 'H29-H13', stops: 1, score: 0.244 }, { plan: 'H29-S13', stops: 1, score: 0.235 }],
  },
  LIN: {
    fromPosition: 11,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.844, '2': 0.156 },
    meanPosition: 8.67,
    sdPosition: 1.09,
    meanPoints: 2.96,
    decisionValue: 0.789,
    objective: 'points',
    alternatives: [{ plan: 'M6-H17-M19', stops: 2, score: 2.518 }, { plan: 'M6-S25-S11', stops: 2, score: 2.277 }, { plan: 'M6-H6-H30', stops: 2, score: 2.127 }],
  },
  GAS: {
    fromPosition: 12,
    plan: 'H6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 9.57,
    sdPosition: 1.61,
    meanPoints: 1.97,
    decisionValue: 1.295,
    objective: 'points',
    alternatives: [{ plan: 'H10-H32', stops: 1, score: 1.893 }, { plan: 'H7-H35', stops: 1, score: 1.843 }, { plan: 'H12-H30', stops: 1, score: 1.825 }],
  },
  BOR: {
    fromPosition: 13,
    plan: 'M6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.75, '2': 0.25 },
    meanPosition: 10.25,
    sdPosition: 1.69,
    meanPoints: 1.28,
    decisionValue: 0.835,
    objective: 'points',
    alternatives: [{ plan: 'M10-H32', stops: 1, score: 1.116 }, { plan: 'M12-M30', stops: 1, score: 0.806 }, { plan: 'M6-H17-M19', stops: 2, score: 0.598 }],
  },
  ALB: {
    fromPosition: 14,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.906, '2': 0.094 },
    meanPosition: 13.53,
    sdPosition: 1.21,
    meanPoints: 0.01,
    decisionValue: 1.623,
    objective: 'position',
    alternatives: [{ plan: 'H15-H27', stops: 1, score: -13.529 }, { plan: 'H14-H28', stops: 1, score: -13.553 }, { plan: 'H20-S22', stops: 1, score: -13.655 }],
  },
  SAI: {
    fromPosition: 15,
    plan: 'S6-H36',
    stops: [{ lap: 36, compound: 'HARD' }],
    stopDistribution: { '1': 0.781, '2': 0.219 },
    meanPosition: 14.87,
    sdPosition: 1.69,
    meanPoints: 0.01,
    decisionValue: 1.032,
    objective: 'position',
    alternatives: [{ plan: 'S6-H12-S24', stops: 2, score: -15.672 }, { plan: 'S6-H25-S11', stops: 2, score: -15.721 }, { plan: 'S6-S25-S11', stops: 2, score: -15.817 }],
  },
  OCO: {
    fromPosition: 16,
    plan: 'H25-H17',
    stops: [{ lap: 55, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 18.46,
    sdPosition: 0.58,
    meanPoints: 0.0,
    decisionValue: 0.427,
    objective: 'position',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: -18.464 }, { plan: 'H27-H15', stops: 1, score: -18.488 }, { plan: 'H25-M17', stops: 1, score: -18.492 }],
  },
  STR: {
    fromPosition: 17,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.875, '2': 0.125 },
    meanPosition: 14.48,
    sdPosition: 1.11,
    meanPoints: 0.0,
    decisionValue: 1.447,
    objective: 'position',
    alternatives: [{ plan: 'H24-H18', stops: 1, score: -14.517 }, { plan: 'H20-S22', stops: 1, score: -14.557 }, { plan: 'H20-M22', stops: 1, score: -14.606 }],
  },
  COL: {
    fromPosition: 18,
    plan: 'H10-H32',
    stops: [{ lap: 40, compound: 'HARD' }],
    stopDistribution: { '1': 0.688, '2': 0.312 },
    meanPosition: 16.03,
    sdPosition: 1.15,
    meanPoints: 0.0,
    decisionValue: 0.725,
    objective: 'position',
    alternatives: [{ plan: 'H10-H10-H22', stops: 2, score: -16.554 }, { plan: 'H6-H26-S10', stops: 2, score: -16.563 }, { plan: 'H10-H22-S10', stops: 2, score: -16.566 }],
  },
  PER: {
    fromPosition: 19,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.9,
    sdPosition: 0.84,
    meanPoints: 0.0,
    decisionValue: 0.686,
    objective: 'position',
    alternatives: [{ plan: 'H21-H21', stops: 1, score: -18.882 }, { plan: 'H23-H19', stops: 1, score: -18.887 }, { plan: 'H19-H23', stops: 1, score: -18.891 }],
  },
  BOT: {
    fromPosition: 20,
    plan: 'H20-H22',
    stops: [{ lap: 50, compound: 'HARD' }],
    stopDistribution: { '1': 0.938, '2': 0.062 },
    meanPosition: 18.18,
    sdPosition: 0.59,
    meanPoints: 0.0,
    decisionValue: 0.537,
    objective: 'position',
    alternatives: [{ plan: 'H14-H28', stops: 1, score: -18.21 }, { plan: 'H23-H19', stops: 1, score: -18.233 }, { plan: 'H20-S22', stops: 1, score: -18.236 }],
  },
}
