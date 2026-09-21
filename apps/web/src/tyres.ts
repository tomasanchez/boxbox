/**
 * Desgaste probabilístico y paradas en boxes.
 *
 * Hasta acá cada auto corría con una cifra de degradación fija, así que dos
 * autos con la misma goma andaban **exactamente** igual para siempre. Ahora hay
 * tres fuentes de variación, todas medidas, y una parada.
 *
 * ## De dónde sale cada sorteo
 *
 *   ruido de vuelta   se sortea **cada vuelta**, normal de desvío **0,457 s**.
 *                     Es lo que queda después de descontar desgaste y
 *                     combustible: tráfico, viento, una entrada ancha. No
 *                     acumula, y es lo que impide que dos autos iguales anden
 *                     igual. Medido sobre 4.407 tandas.
 *
 *   ritmo de caída    se sortea **una vez por tanda**, de la distribución
 *                     **empírica** de Zandvoort. Acumula.
 *
 *   pérdida de boxes  se sortea en la parada, de los cuartiles medidos en
 *                     Zandvoort: mediana 22,7 s, p25 19,8, p75 26,7.
 *
 * ## Por qué la distribución empírica y no una normal
 *
 * Porque las tandas no se distribuyen normal ni de casualidad. Medida sobre
 * Zandvoort, la curtosis del ritmo de caída da **48,6 en el duro, 32,8 en el
 * medio y 20,2 en el blando** — una normal tiene cero. Hay unas pocas tandas
 * catastróficas que estiran la cola y hacen que el desvío mienta: el blando de
 * Zandvoort tiene desvío 0,664 s/vuelta, pero entre el percentil 5 y el 95 va de
 * −0,184 a 0,138. Sortear de una normal con ese desvío daba tandas absurdas
 * varias veces por carrera.
 *
 * Así que no se asume forma: se guardan nueve cortes de la distribución medida y
 * se sortea interpolando entre ellos. Es lo que pidió el dato, no lo que le
 * quedaba cómodo al modelo.
 *
 * ## Las paradas
 *
 * También se sortean, y no sólo la pérdida: **cuántas, cuándo y con qué**.
 *
 *   cuántas    de la distribución medida de paradas que le quedan a un auto
 *              desde el 42% de la carrera: ninguna 15%, una 49%, dos 19%, tres
 *              16%. Medido en Zandvoort seco, sobre 73 autos que vieron la
 *              bandera.
 *
 *   cuándo     la primera cae en su ventana si tiene una —es la proyección del
 *              propio modelo—; las demás salen de dónde caen las paradas tardías
 *              acá, medido.
 *
 *   con qué    de la matriz de transición medida: de duro a duro 41%, a medio
 *              38%, a blando 21%; de medio a duro 50%; de blando a blando 63%.
 *
 * Antes esto era una regla: **una** parada, en la ventana, al compuesto que le
 * faltaba. Tres decisiones disfrazadas de certezas.
 *
 * Un auto sin ventana proyectable ya no queda sin parar: su plan sale entero de
 * la distribución medida. Antes eran ocho de veinte corriendo la carrera con un
 * solo juego.
 *
 * Medido con `apps/ml/scripts/pace_noise.py` y
 * `apps/ml/scripts/zandvoort_distributions.py`.
 */

import { RACE } from './data'
import type { Compound, DriverState, TrackStatus } from './types'

/** Desvío del ritmo de una vuelta, en segundos. Mediana de 4.407 tandas. */
export const LAP_NOISE_S = 0.457

/** Probabilidades a las que están cortadas las distribuciones de abajo. */
const CUT_AT = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]

/**
 * Ritmo de caída por compuesto, en s/vuelta, como cortes de la distribución
 * medida en Zandvoort. El del medio de cada fila es la mediana.
 *
 * Vueltos a derivar después de ajustar la corrección por avance de carrera en
 * 0,056 s/vuelta, contra los 0,035 que estaban asumidos. El efecto es exacto y
 * uniforme: cada pendiente sube la diferencia, 0,021 s/vuelta, porque la
 * corrección es lineal en el número de vuelta. La **forma** de la distribución
 * no cambia, así que sigue en pie que no es normal — pero la mediana del
 * desgaste pasa de 0,034-0,040 a 0,055-0,062, y el percentil 5 del medio y del
 * duro se mueve de claramente negativo a casi cero. Casi todas las «tandas que
 * mejoraban» eran la corrección quedándose corta.
 */
const WEAR_CUTS: Record<Compound, number[]> = {
  // 98 tandas.
  SOFT: [-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592],
  // 79 tandas.
  MEDIUM: [-0.0063, 0.0322, 0.0421, 0.0547, 0.0625, 0.0749, 0.0885, 0.101, 0.1277],
  // 80 tandas.
  HARD: [-0.0143, 0.0219, 0.0342, 0.0427, 0.0554, 0.0646, 0.0708, 0.0847, 0.1176],
  // Mojados: 201 y 17 tandas en todo el conjunto, ninguna en Zandvoort seco. Se
  // presta la del blando, que es la más dispersa de las secas, y queda dicho.
  INTERMEDIATE: [-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592],
  WET: [-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592],
}

/**
 * Pérdida de boxes en verde en Zandvoort, en segundos. 172 paradas medidas.
 *
 * Cortes en las mismas probabilidades que `CUT_AT`, igual que el desgaste de
 * arriba. Antes eran tres cuartiles sorteados con una **triangular**, y eso no
 * podía representar una parada mala: una triangular no puede pasarse de su
 * máximo, y su máximo era el p75. El recuadro «IN PIT» no podía mostrar la
 * rueda trabada ni los 7 s parado de Norris en Madrid por más veces que se
 * corriera la simulación — quedaba fuera de su alcance por construcción, no por
 * suerte. Con estos cortes, una de cada cuatro paradas sorteadas pasa el viejo
 * tope.
 *
 * **También cambió de dónde se miden, y conviene saber por qué.** Antes salían
 * de `zandvoort_distributions.py`, que compara la vuelta de entrada contra la
 * mediana verde *de la carrera* —un solo número— y por eso le carga al auto el
 * combustible, la evolución de la pista y el tráfico de esa vuelta. Ahora salen
 * de `effective_pit_loss.py`, que compara contra la mediana del campo *en esa
 * misma vuelta*, que es la referencia que ese script existe para usar.
 *
 * Con la triangular la diferencia entre los dos métodos era chica y pasaba
 * inadvertida —19,8 / 22,7 / 26,7 contra 20,6 / 23,5 / 31,3—. Con los nueve
 * cortes se ve donde importa: el p95 da 41,1 con la referencia buena y 64,7 con
 * la mala. Pasar a la distribución empírica no creó el problema, lo mostró.
 */
const PIT_LOSS_CUTS = [15.8, 18.4, 19.8, 20.8, 22.7, 24.3, 26.7, 30.2, 41.1]

/**
 * De dónde salen los sorteos de una carrera.
 *
 * Existe porque hay **dos mediciones de desgaste de Zandvoort** conviviendo en
 * el repositorio y difieren un 63% en el medio (ver ADR-009): la de acá junta
 * todas las temporadas, la del export pre-carrera se queda con 2026. Cada vista
 * sortea con el modelo que le corresponde en vez de que una imponga el suyo, y
 * la diferencia queda declarada en pantalla en lugar de disimulada.
 */
export interface DrawModel {
  /**
   * Cortes del ritmo de caída por compuesto, en las probabilidades de `CUT_AT`.
   *
   * Puede no traerlos todos —el export pre-carrera sólo mide las tres secas— y
   * por eso el tipo exige **sólo** el medio, que es al que se cae `drawWear`
   * cuando le piden un compuesto sin medición. Declararlo completo sería
   * prometer una medición que no existe.
   */
  wearCuts: Partial<Record<Compound, number[]>> & Record<'MEDIUM', number[]>
  /** Cortes de la pérdida de boxes en verde, en las probabilidades de `CUT_AT`. */
  pitLoss: number[]
}

/** El modelo de la foto de la vuelta 30, que es el que se usaba hasta acá. */
export const SNAPSHOT_MODEL: DrawModel = { wearCuts: WEAR_CUTS, pitLoss: PIT_LOSS_CUTS }

/**
 * Cuántas paradas le quedan a un auto desde la vuelta 30 de 72.
 *
 * Índice = cantidad de paradas. Medido en Zandvoort seco sobre 73 autos que
 * vieron la bandera, descontando las paradas gratis bajo bandera roja.
 *
 * Zandvoort para más que el promedio —una parada 49% contra 59% global, tres
 * 16% contra 2,6%— y hay un mecanismo detrás, no sólo ruido: **el 36% de sus
 * paradas ocurren bajo neutralización**, contra 23% global. Donde la parada sale
 * barata, se para más. Aun así son 73 autos sobre cuatro carreras: poco.
 */
const STOPS_LEFT = [0.151, 0.493, 0.192, 0.164]

/**
 * Dónde caen las paradas tardías en Zandvoort, como fracción de la carrera.
 * Cortes en las mismas probabilidades que `CUT_AT`, sobre 109 paradas.
 */
const LATE_STOP_CUTS = [0.458, 0.533, 0.597, 0.653, 0.722, 0.75, 0.778, 0.789, 0.817]

/**
 * A qué compuesto se cambia, medido sobre 1.768 paradas tardías.
 *
 * Se sortea de acá en vez de aplicar la regla «el obligatorio que le falta».
 * Parece contradecir B6.3.8, porque el 41% de las paradas de duro vuelven a
 * calzar duro — pero son paradas reales de carreras que cumplieron el
 * reglamento: el auto ya había usado el otro compuesto antes. Forzar un cambio
 * en cada parada daría carreras **menos** realistas, no más.
 *
 * Lo que no se puede verificar acá es el cumplimiento sobre la carrera entera:
 * la foto congelada de la vuelta 30 no dice qué juegos usó cada auto antes.
 */
const NEXT_COMPOUND: Record<string, [Compound, number][]> = {
  HARD: [
    ['HARD', 0.409],
    ['MEDIUM', 0.379],
    ['SOFT', 0.212],
  ],
  MEDIUM: [
    ['HARD', 0.501],
    ['MEDIUM', 0.172],
    ['SOFT', 0.327],
  ],
  SOFT: [
    ['HARD', 0.104],
    ['MEDIUM', 0.264],
    ['SOFT', 0.632],
  ],
}

/** Vueltas mínimas entre dos paradas: menos que eso no es una tanda. */
const MIN_STINT = 6

/** Semilla por defecto. Cambiarla es, en chiquito, una corrida de Monte Carlo. */
export const DEFAULT_SEED = 20261

/**
 * Ruido reproducible.
 *
 * Se sortea a partir de `(auto, vuelta, semilla)` en vez de guardar el estado de
 * un generador. Así la vuelta 40 da lo mismo se llegue reproduciendo desde la 30
 * o saltando con el botón, que es lo que uno espera de una carrera: no se
 * reescribe sola cuando la volvés a mirar.
 */
function hash(...parts: number[]): number {
  let h = 0x811c9dc5
  for (const part of parts) {
    h ^= Math.imul(part | 0, 0x01000193)
    h = Math.imul(h ^ (h >>> 15), 0x2545f491)
  }
  return (h >>> 0) / 0x100000000
}

/** Normal estándar por Box-Muller, con dos uniformes derivadas del mismo hash. */
function gaussian(...parts: number[]): number {
  const u = Math.max(hash(...parts), 1e-9)
  const v = hash(...parts, 0x9e37)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

/**
 * Invierte una distribución dada por cortes: sortea interpolando entre ellos.
 *
 * Fuera del rango medido no extrapola — devuelve el corte del extremo. Es
 * deliberado: más allá del percentil 95 no hay dato, y estirar una recta ahí es
 * inventar justo en la cola, que es donde más se nota.
 */
function fromCuts(cuts: number[], u: number): number {
  if (u <= CUT_AT[0]) return cuts[0]
  const last = CUT_AT.length - 1
  if (u >= CUT_AT[last]) return cuts[last]

  let i = 0
  while (i < last && CUT_AT[i + 1] < u) i += 1
  const span = CUT_AT[i + 1] - CUT_AT[i]
  const t = span > 0 ? (u - CUT_AT[i]) / span : 0
  return cuts[i] + (cuts[i + 1] - cuts[i]) * t
}

/** La mediana de un compuesto, que es el corte del medio. */
function medianWear(model: DrawModel, compound: Compound): number {
  const cuts = model.wearCuts[compound] ?? model.wearCuts.MEDIUM
  return cuts[(CUT_AT.length - 1) / 2]
}

/** Ritmo de caída sorteado para un compuesto, en s/vuelta. */
function drawWear(model: DrawModel, compound: Compound, ...parts: number[]): number {
  return fromCuts(model.wearCuts[compound] ?? model.wearCuts.MEDIUM, hash(...parts))
}

/** Pérdida de boxes sorteada de la distribución medida, sin forma asumida. */
function drawPitLoss(model: DrawModel, ...parts: number[]): number {
  return fromCuts(model.pitLoss, hash(...parts))
}

export interface PitStop {
  /** Vuelta en la que entra a boxes. */
  lap: number
  /** Compuesto que calza. */
  compound: Compound
  /** Segundos que pierde. */
  lossS: number
}

export interface Stochastic {
  /** Los autos con la goma envejecida —o cambiada— hasta `lap`. */
  cars: DriverState[]
  /**
   * Ruido de esta vuelta para cada auto, en segundos. Va aparte de
   * `degradationS` a propósito: la tabla y las tarjetas tienen que mostrar la
   * **tendencia**, no el temblor de una vuelta suelta.
   */
  paceNoise: number[]
  /** La próxima parada de cada auto, o `null` si no le queda ninguna. */
  stops: (PitStop | null)[]
  /** El plan completo de cada auto, para poder mirarlo entero. */
  plans: PitStop[][]
  /**
   * Vueltas de avance que cada auto ya cedió en boxes. Sube de golpe cuando
   * para; `useField` lo convierte en tiempo detenido en el pit lane.
   */
  progressLost: number[]
}

/** Elige de una lista de opciones con peso. */
function pick<T>(options: [T, number][], u: number): T {
  let acc = 0
  for (const [value, weight] of options) {
    acc += weight
    if (u < acc) return value
  }
  return options[options.length - 1][0]
}

/**
 * El plan de paradas de un auto para lo que queda de carrera.
 *
 * Nada de esto es una regla: la cantidad, las vueltas y los compuestos salen los
 * tres de distribuciones medidas. La única concesión al modelo propio es que la
 * primera parada, si el auto tiene ventana proyectada, cae adentro — porque esa
 * ventana **es** la salida del modelo y tiene más información sobre este auto en
 * particular que la distribución agregada del circuito.
 *
 * Las vueltas sorteadas se ordenan y se separan al menos `MIN_STINT` vueltas:
 * dos paradas pegadas no son un plan, son un sorteo mal leído.
 */
function planStops(
  model: DrawModel,
  car: DriverState,
  index: number,
  seed: number,
  fromLap: number,
): PitStop[] {
  if (car.retiredOnLap != null) return []

  const count = pick(
    STOPS_LEFT.map((p, n) => [n, p] as [number, number]),
    hash(seed, index, 0x570b),
  )
  if (count === 0) return []

  const laps: number[] = []
  for (let n = 0; n < count; n += 1) {
    const window = car.pitWindow
    if (n === 0 && window) {
      const span = Math.max(0, window.closesLap - window.opensLap)
      laps.push(window.opensLap + Math.round(hash(seed, index, 0x9017) * span))
      continue
    }
    const share = fromCuts(LATE_STOP_CUTS, hash(seed, index, 0x4a97 + n))
    laps.push(Math.round(share * RACE.totalLaps))
  }

  laps.sort((a, b) => a - b)

  const stops: PitStop[] = []
  let compound = car.compound
  let previous = fromLap
  for (let n = 0; n < laps.length; n += 1) {
    const lap = Math.max(laps[n], previous + MIN_STINT)
    // Una parada en las últimas vueltas no le sirve a nadie: no queda carrera
    // para amortizar los veintitrés segundos.
    if (lap > RACE.totalLaps - MIN_STINT) break

    compound = pick(NEXT_COMPOUND[compound] ?? NEXT_COMPOUND.MEDIUM, hash(seed, index, 0x8c02 + n))
    stops.push({ lap, compound, lossS: drawPitLoss(model, seed, index, 0x1055 + n) })
    previous = lap
  }

  return stops
}

/** Una parada dicha de antemano: cuándo y con qué. Lo que cuesta se sortea. */
export interface PlannedStop {
  lap: number
  compound: Compound
}

export interface EvolveOptions {
  /** De dónde se sortea el desgaste y la pérdida de boxes. Ver `DrawModel`. */
  model?: DrawModel
  /**
   * Plan fijo de cada auto, en el mismo orden que `base`.
   *
   * Es lo que separa a la carrera desde la largada de la foto de la vuelta 30:
   * ahí las paradas se sortean de las distribuciones medidas porque no se sabe
   * qué va a hacer cada auto, y acá **cada auto corre el plan que le dio el
   * algoritmo genético**. Lo que sigue sorteándose es cuánto cuesta esa parada y
   * cómo se cae la goma, que es lo que hace que dos sorteos del mismo plan
   * terminen distinto — la tesis del trabajo (ADR-006).
   */
  plans?: PlannedStop[][]
  /**
   * Bandera que ondea ahora, y desde qué vuelta.
   *
   * Sin esto la animación no sabía que existían las neutralizaciones: el
   * selector de arriba pintaba la barra de estado y nada más, así que nadie
   * paraba bajo VSC por más que el modelo de Python dijera que para el 24% del
   * campo. El usuario lo vio en pantalla antes de que ningún test lo dijera.
   */
  status?: TrackStatus
  /** Vuelta en que se puso esa bandera. Lo que hace la reacción reproducible. */
  statusSince?: number | null
}

/**
 * Envejece la goma de cada auto desde `fromLap` hasta `lap`, con su parada.
 *
 * Es la misma cuenta para adelante y para atrás: mover la vuelta con los botones
 * no altera la carrera, sólo mueve el reloj.
 */
/**
 * Probabilidad de que un auto entre a boxes durante una neutralización, según
 * la edad de su goma al empezarla. Espejo de `boxbox_ml.reaction.REACT`.
 *
 * Una neutralización **no es una parada automática**, que era el supuesto que la
 * animación tenía sin decirlo: bajo VSC para el 24,2% del campo y bajo safety
 * car el 43,0%. Sólo bajo bandera roja —la carrera detenida, el cambio no cuesta
 * posición— entra casi todo el mundo.
 *
 * Medido sobre 2.828 casos auto-por-período de 2022 a 2026 por
 * `apps/ml/scripts/rival_reaction.py`. Las bandas son 0-5, 6-10, 11-15, 16-20,
 * 21-25, 26-30 y 31+ vueltas de goma.
 */
const REACT: Partial<Record<TrackStatus, number[]>> = {
  RED: [0.924, 0.982, 1.0, 1.0, 1.0, 1.0, 1.0],
  SC: [0.17, 0.473, 0.605, 0.73, 0.825, 0.737, 0.938],
  VSC: [0.088, 0.169, 0.356, 0.324, 0.246, 0.444, 0.447],
}

/** Bordes superiores de cada banda de edad de goma, en vueltas. */
const AGE_EDGES = [5, 10, 15, 20, 25, 30]

/**
 * Cuánto se corre la probabilidad de todo el campo en un mismo período.
 *
 * Los períodos reales son estampidas o congelamientos: bajo safety car la cuota
 * del campo que para va de 0,05 en el percentil diez a 0,85 en el noventa. Con
 * una moneda por auto la pantalla mostraría siempre más o menos medio campo
 * entrando, y nunca el caso que de verdad te arruina la carrera, que es que
 * entren todos menos vos. El corrimiento es **uno solo por período** y lo
 * sienten los veintidós.
 */
const PERIOD_SIGMA: Partial<Record<TrackStatus, number>> = { RED: 0, SC: 1.8, VSC: 1.15 }

/** Normal estándar a partir de dos uniformes, por Box-Muller. */
function normalFrom(u1: number, u2: number): number {
  return Math.sqrt(-2 * Math.log(Math.max(u1, 1e-9))) * Math.cos(2 * Math.PI * u2)
}

/**
 * Qué autos se tiran a boxes cuando la pista se neutraliza en `since`.
 *
 * Normalmente adelanta la **próxima parada pendiente**, pero también puede
 * agregar una. Que sólo adelantara fue la primera versión del lado de Python y
 * dejaba al modelo en la mitad de las cuotas medidas, porque un tercio de los
 * autos ya había gastado todas las paradas de su plan y no podía reaccionar
 * nunca más. En pantalla se veía peor todavía: con la bandera puesta tarde no
 * entraba nadie. Un auto con goma de treinta vueltas cuando sale un safety car
 * para, diga lo que diga el plan.
 *
 * Es determinista a partir de la semilla y de la vuelta en que se puso la
 * bandera, así que mover el reloj para adelante y para atrás no cambia quién
 * entró: la carrera sigue siendo la misma carrera.
 */
function reactToFlag(
  plans: PitStop[][],
  base: DriverState[],
  status: TrackStatus,
  since: number,
  fromLap: number,
  seed: number,
): PitStop[][] {
  const table = REACT[status]
  const sigma = PERIOD_SIGMA[status]
  if (!table || sigma === undefined || since < fromLap + MIN_STINT) return plans

  // Un solo corrimiento para todo el campo, que es lo que produce la estampida
  // y el período en que no se mueve nadie.
  const shift = sigma * normalFrom(hash(seed, since, 0x5eed), hash(seed, since, 0x5eee))

  return plans.map((plan, index) => {
    const pending = plan.findIndex((stop) => stop.lap > since)
    // Sin parada pendiente el auto igual puede entrar: es una parada agregada, y
    // calza lo mismo que calzó la última vez.
    const next = pending < 0 ? plan.length : pending
    const previous = next > 0 ? plan[next - 1].lap : fromLap
    const age = since - previous + (next > 0 ? 0 : base[index].tyreAge)
    if (age < MIN_STINT || since > RACE.totalLaps - MIN_STINT) return plan

    let band = 0
    while (band < AGE_EDGES.length && age > AGE_EDGES[band]) band += 1
    const p = table[band]
    const logit = Math.log(Math.min(Math.max(p, 1e-6), 1 - 1e-6) / (1 - Math.min(Math.max(p, 1e-6), 1 - 1e-6)))
    const chance = 1 / (1 + Math.exp(-(logit + shift)))
    if (hash(seed, index, since, 0xb0c5) >= chance) return plan

    // La parada se adelanta a esta vuelta. Las que siguen se quedan donde
    // estaban salvo que queden demasiado cerca, en cuyo caso se caen: un juego
    // de cuatro vueltas no lo cambia nadie.
    const fitting = plan[next] ?? plan[plan.length - 1]
    const moved = [...plan]
    moved[next] = {
      lap: since,
      compound: fitting?.compound ?? base[index].compound,
      lossS: fitting?.lossS ?? drawPitLoss(SNAPSHOT_MODEL, seed, index, 0x1055 + next),
    }
    return moved.filter((stop, n) => n <= next || stop.lap >= since + MIN_STINT)
  })
}

export function evolve(
  base: DriverState[],
  lap: number,
  fromLap: number,
  seed: number = DEFAULT_SEED,
  options: EvolveOptions = {},
): Stochastic {
  const model = options.model ?? SNAPSHOT_MODEL
  const plans = base.map((car, index) => {
    const planned = options.plans?.[index]
    if (!planned) return planStops(model, car, index, seed, fromLap)
    // El plan dice cuándo y con qué; cuánto cuesta cada parada se sigue
    // sorteando de la distribución medida de pérdida de boxes.
    return planned.map((stop, n) => ({
      ...stop,
      lossS: drawPitLoss(model, seed, index, 0x1055 + n),
    }))
  })
  const neutralised =
    options.status !== undefined && options.statusSince != null
      ? reactToFlag(plans, base, options.status, options.statusSince, fromLap, seed)
      : plans
  // La última parada ya hecha es la que define con qué goma anda ahora.
  const done = neutralised.map((plan) => plan.filter((stop) => lap >= stop.lap))
  const stops = neutralised.map((plan) => plan.find((stop) => lap < stop.lap) ?? null)

  const cars = base.map((car, index) => {
    const stop = done[index][done[index].length - 1]

    if (stop) {
      // Juego nuevo: no hay medición previa de este auto con esta goma, así que
      // el ritmo se sortea entero de la distribución del compuesto.
      const age = lap - stop.lap
      const rate = drawWear(model, stop.compound, seed, index, 0x2472 + done[index].length)
      return {
        ...car,
        compound: stop.compound,
        tyreAge: age,
        degradationRate: rate,
        degradationS: rate * age,
        // La ventana que traía era para la parada que ya hizo, y no hay otra
        // proyectada: se limpia en vez de dejar un rango vencido, que la tabla
        // mostraba y el duelo de boxes seguía ofreciendo.
        //
        // No se pone acá la próxima parada del plan. La ventana es lo que
        // **proyecta** el modelo; el plan es una realización sorteada. Mezclar
        // las dos en la misma columna las hace pasar por lo mismo, y no lo son:
        // un auto puede tener ventana abierta y no parar, o parar sin tenerla.
        pitWindow: null,
      }
    }

    // Tanda en curso: hay un ritmo medido para este auto. Se conserva como valor
    // central y se le suma la incertidumbre con la forma de la distribución
    // —el sorteo menos su mediana—, en vez de tirarlo y sortear de cero.
    const deviation = drawWear(model, car.compound, seed, index, 0x5747) - medianWear(model, car.compound)
    const rate = car.degradationRate + deviation
    const elapsed = Math.max(0, lap - fromLap)
    return {
      ...car,
      degradationRate: rate,
      degradationS: car.degradationS + rate * elapsed,
      tyreAge: car.tyreAge + elapsed,
    }
  })

  const paceNoise = base.map((_, index) => gaussian(seed, index, lap) * LAP_NOISE_S)

  // Se suman todas las paradas ya hechas: `useField` cobra sólo el incremento.
  const progressLost = done.map((made) =>
    made.reduce((total, stop) => total + stop.lossS / RACE.greenLapS, 0),
  )

  // La torre muestra el plan YA REACCIONADO: si el auto se tiro a boxes bajo la
  // bandera, eso es lo que hizo, y mostrarle al usuario el plan original seria
  // contradecir en la torre lo que pasa en la pista.
  return { cars, paceNoise, stops, plans: neutralised, progressLost }
}
