/**
 * Física del pelotón, integrada cuadro a cuadro.
 *
 * La versión anterior recalculaba la posición de cada auto a partir de su
 * separación deseada. Como esa separación se interpolaba, cada auto la veía
 * cambiar en distinta medida y **algunos terminaban yendo para atrás** o
 * saliendo disparados. Un auto de carrera no hace ninguna de las dos cosas.
 *
 * Acá cada auto tiene su propia posición absoluta, en vueltas recorridas, y
 * **sólo puede avanzar**. Se junta al de adelante porque levanta el pie, no
 * porque lo teletransporten. La corrección de velocidad está acotada por arriba
 * y por abajo, así que nadie retrocede ni pega un salto.
 *
 * **Cada auto tiene su propio ritmo**, derivado de la degradación medida: el
 * que pierde 1,58 s por vuelta anda más lento que el que todavía gana 0,50. En
 * verde eso hace que los intervalos evolucionen solos y que haya
 * adelantamientos cuando alguien alcanza al de adelante. Bajo neutralización el
 * ritmo se iguala y el orden queda congelado, como manda el reglamento.
 *
 * La diferencia real es chica —1,3 s sobre una vuelta de 80 s es un 1,6%— así
 * que se amplifica para que se vea. Es la misma licencia que con la separación,
 * y por eso el panel declara el movimiento como esquemático.
 *
 * Reglamento aplicable:
 *
 *  - **B5.12** VSC: cada auto debe superar un tiempo mínimo por sector, así que
 *    las distancias se conservan y el pelotón no se agrupa.
 *  - **B5.12.2** Reinicio tras safety car: nadie puede adelantar hasta cruzar
 *    la línea, y el primero detrás del coche de seguridad dicta el ritmo. Por
 *    eso acá la cabeza avanza sola y el resto se acomoda detrás.
 */

import { useEffect, useRef, useState } from 'react'
import { STATUS } from './status'
import { STARTING_GRID } from './startingGrid'
import type { DriverState, TrackStatus } from './types'

/**
 * Cuánto se amplifica la diferencia de ritmo entre autos. Con el valor físico
 * (~1,6% entre el mejor y el peor) no se notaría nada. Tampoco conviene pasarse:
 * con un valor alto la parrilla se reordena entera en pocas vueltas, que
 * tampoco es lo que pasa en una carrera.
 */
const PACE_SPREAD = 0.22

/** Qué tan rápido converge cada magnitud, en unidades por segundo. */
const RATE = {
  /** Juntar o estirar el pelotón es lo más lento. */
  spacing: 1.2,
  /** Levantar o bajar el pie es más inmediato. */
  pace: 1.8,
  /** Rodar hasta la parrilla, con bandera roja. */
  toGrid: 1.1,
  /** Pasar de orden por intervalo a formación pareja. */
  uniform: 1.1,
  /** Con cuánta insistencia cada auto persigue su hueco. */
  catchup: 1.3,
}

/**
 * Cuánto más rápido que el ritmo base puede ir un auto recuperando terreno.
 * Acotado: sin esto un rezagado cruzaría medio circuito en un cuadro.
 */
const MAX_CATCHUP = 0.9

/**
 * Cuánto de la vuelta puede ocupar el pelotón entero, como máximo.
 *
 * Este tope no es estético, es de corrección. Con los intervalos reales de
 * Zandvoort el último auto está a casi 48 s del líder; con un factor fijo eso
 * daba más de **dos vueltas** de separación, así que los rezagados envolvían el
 * circuito y reaparecían adelante — que era lo que se veía como autos yendo
 * para atrás o saliendo disparados. Normalizando, el pelotón siempre entra en
 * una vuelta y el orden en pantalla coincide con el de la carrera.
 */
const FIELD_SPAN = 0.82

/** Separación entre filas de la parrilla, como fracción de vuelta. */
const GRID_ROW_GAP = 0.016

/**
 * Formación en parrilla, en el **orden de largada real**, no en el de carrera.
 *
 * Son cosas distintas: en Zandvoort largó NOR primero y para la vuelta 30
 * lideraba ANT. Los autos que no figuran en la grilla cargada van al fondo.
 */
function gridTravelled(drivers: DriverState[]): number[] {
  return drivers.map((d) => {
    const slot = STARTING_GRID.indexOf(d.code)
    const place = slot >= 0 ? slot : STARTING_GRID.length
    // Filas de a dos: los dos autos de una fila están casi a la par, y el de
    // la pole está apenas adelantado respecto de su compañero de fila.
    const row = Math.floor(place / 2)
    const withinRow = place % 2 === 0 ? 0 : 0.18
    return -GRID_ROW_GAP * (row + withinRow)
  })
}

/** Posiciones iniciales, a partir de los intervalos medidos. */
function initialTravelled(drivers: DriverState[]): number[] {
  const totalGap = drivers.reduce((sum, d) => sum + (d.gapAheadS ?? 0), 0)
  const spread = totalGap > 0 ? FIELD_SPAN / totalGap : 0.02
  let cumulative = 0
  return drivers.map((d) => {
    cumulative += (d.gapAheadS ?? 0) * spread
    return -cumulative
  })
}

/**
 * Cada cuánto se publican posiciones e intervalos para la tabla, en ms.
 *
 * El mapa necesita 60 cuadros por segundo; la torre de tiempos no. Una torre
 * real refresca unas pocas veces por segundo, y a 60 Hz habría que volver a
 * renderizar veintidós filas de MUI en cada cuadro sin que nadie note la
 * diferencia.
 */
const TIMING_INTERVAL_MS = 170

/** Datos de cronometraje, publicados a menor frecuencia que la animación. */
export interface Timing {
  /** Índices de piloto ordenados por posición en pista. */
  order: number[]
  /** Intervalo en segundos al de adelante; `null` para el líder. */
  gapAhead: (number | null)[]
  /** Distancia en segundos al líder. */
  gapLeader: number[]
}

export interface FieldState {
  /** Ritmo actual, de 0 (detenido) a 1 (carrera). */
  pace: number
  /** Orden en pista, de adelante hacia atrás. Cambia si hay adelantamientos. */
  order: number[]
  /** 0 = corriendo en pista, 1 = formado en la parrilla. */
  gridded: number
  /** 0 = ordenado por intervalo, 1 = formación pareja tras el safety car. */
  uniform: number
  /**
   * Posición de cada auto dentro de la vuelta, 0 a 1, en el mismo orden que los
   * pilotos recibidos. Derivada de una posición absoluta que sólo crece.
   */
  positions: number[]
}

function approach(current: number, target: number, rate: number, dt: number): number {
  return current + (target - current) * Math.min(1, dt * rate)
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

/**
 * Ritmo propio de un auto, relativo al del pelotón.
 *
 * Sale de la degradación medida: el que más pierde por vuelta anda más lento.
 * `held` apaga la diferencia cuando la carrera está neutralizada, porque ahí
 * todos van al mismo ritmo impuesto.
 */
function carPace(driver: DriverState, held: number): number {
  const penalty = Math.max(driver.degradationS, 0) * PACE_SPREAD * 0.1
  return 1 - penalty * (1 - held)
}

export function useField(
  drivers: DriverState[],
  status: TrackStatus,
  playing: boolean,
  /** Milisegundos de reloj por vuelta a ritmo pleno; sale del selector. */
  msPerLap: number,
  /** Vuelta actual. En la 1 el pelotón está en la parrilla de salida. */
  lap: number,
): { field: FieldState; timing: Timing } {
  const spec = STATUS[status]
  // En la vuelta 1 forman en la grilla — pero sólo mientras esté en pausa. Al
  // apretar reproducir se largan: si `onGrid` siguiera valiendo, el ritmo
  // quedaría clavado en cero y los autos no arrancarían nunca.
  const onGrid = lap <= 1 && !playing

  // Todo el estado mutable vive acá: se toca una vez por cuadro y recién
  // entonces se publica una instantánea, así el render nunca lee la ref.
  //
  // El ritmo arranca en cero, no en el del estado: si arrancara en carrera, el
  // pelotón se movería —y hasta cruzaría la meta— antes de que nadie apriete
  // reproducir. Y si la vuelta es la 1, se arranca formado en la grilla.
  const sim = useRef({
    spacing: onGrid ? STATUS.RED.spacing : spec.spacing,
    pace: 0,
    gridded: onGrid ? 1 : 0,
    uniform: onGrid ? 1 : 0,
    /** Vueltas recorridas por cada auto. Monótona creciente. */
    travelled: onGrid ? gridTravelled(drivers) : initialTravelled(drivers),
  })

  const [snapshot, setSnapshot] = useState<FieldState>(() => ({
    pace: 0,
    gridded: 0,
    uniform: 0,
    positions: drivers.map(() => 0),
    order: drivers.map((_, i) => i),
  }))

  const [timing, setTiming] = useState<Timing>(() => ({
    order: drivers.map((_, i) => i),
    gapAhead: drivers.map((d) => d.gapAheadS ?? null),
    gapLeader: drivers.map((d) => d.gapLeaderS ?? 0),
  }))
  const lastTiming = useRef(0)

  // Los objetivos se leen de refs para que cambiar de estado, de velocidad o de
  // parrilla no reinicie el bucle a mitad de una transición.
  const target = useRef(spec)
  const lapsPerSecond = useRef(1000 / msPerLap)
  const grid = useRef(drivers)
  /**
   * Dónde va a formar el pelotón: la próxima vez que la cabeza cruce la meta.
   * Se fija al entrar en formación y se borra al salir, para que los autos
   * **rueden hasta la línea y ahí se detengan**, en lugar de frenar en seco
   * donde los agarró la bandera.
   */
  const gridLine = useRef<number | null>(null)

  useEffect(() => {
    // Detenidos en la vuelta 1 la parrilla se comporta como la formación de
    // bandera roja; al largar vuelve a mandar el estado de pista.
    target.current = onGrid ? { ...spec, field: 'grid', pace: 0 } : spec
  }, [spec, onGrid])

  useEffect(() => {
    lapsPerSecond.current = 1000 / msPerLap
  }, [msPerLap])

  useEffect(() => {
    grid.current = drivers
    // Si cambia la cantidad de autos, se reinicia el arreglo de posiciones.
    if (sim.current.travelled.length !== drivers.length) {
      sim.current.travelled = initialTravelled(drivers)
    }
  }, [drivers])

  // Saltar de vuelta con la barra reubica el pelotón: en la 1, sobre la línea
  // de largada; en cualquier otra, en sus intervalos medidos. Sin esto los
  // autos quedaban donde estaban y el salto no se notaba.
  const previousLap = useRef(lap)
  useEffect(() => {
    const jumped = Math.abs(lap - previousLap.current) > 1
    previousLap.current = lap
    if (!jumped) return

    const s = sim.current
    if (lap <= 1) {
      s.travelled = gridTravelled(drivers)
      s.uniform = 1
      s.gridded = 1
      s.spacing = STATUS.RED.spacing
    } else {
      s.travelled = initialTravelled(drivers)
      s.uniform = 0
      s.gridded = 0
      s.spacing = STATUS[status].spacing
    }
    s.pace = 0
  }, [lap, drivers, status])

  useEffect(() => {
    let frame = 0
    let last = performance.now()

    const tick = (now: number) => {
      // Volver de una pestaña en segundo plano entrega un delta enorme; se
      // acota para que el pelotón no dé un salto.
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now

      const t = target.current
      const cars = grid.current
      const s = sim.current
      const lps = lapsPerSecond.current

      s.spacing = approach(s.spacing, t.spacing, RATE.spacing, dt)
      s.pace = approach(s.pace, playing ? t.pace : 0, RATE.pace, dt)
      s.gridded = approach(s.gridded, t.field === 'grid' ? 1 : 0, RATE.toGrid, dt)
      s.uniform = approach(
        s.uniform,
        t.field === 'bunch' || t.field === 'grid' ? 1 : 0,
        RATE.uniform,
        dt,
      )

      // El intervalo acumulado del último auto fija la escala: se reparte el
      // pelotón dentro de FIELD_SPAN y después el estado lo comprime o estira.
      const totalGap = cars.reduce((sum, c) => sum + (c.gapAheadS ?? 0), 0)
      const spread =
        (totalGap > 0 ? FIELD_SPAN / totalGap : 0.02) * (s.spacing / STATUS.GREEN.spacing)
      const base = s.pace * lps

      // `held` es cuánto manda la formación sobre el ritmo propio: en verde
      // cada uno corre a lo suyo, neutralizado todos van en fila.
      const held = Math.max(s.uniform, s.gridded)

      if (t.field === 'grid') {
        // Se elige la próxima línea de meta y la cabeza rueda hasta ahí, cada
        // vez más despacio, hasta detenerse encima. El margen evita elegir una
        // línea que ya está prácticamente debajo del auto.
        if (gridLine.current === null) {
          gridLine.current = Math.ceil(s.travelled[0] + 0.05)
        }
        const remaining = gridLine.current - s.travelled[0]
        const roll = Math.min(lps * 0.75, Math.max(remaining * 2.2, 0))
        s.travelled[0] = Math.min(s.travelled[0] + dt * roll, gridLine.current)
      } else {
        gridLine.current = null
        // La cabeza dicta el ritmo (B5.12.2): avanza sola y el resto se acomoda
        // detrás.
        s.travelled[0] += dt * base * carPace(cars[0], held)
      }

      let byGap = 0
      for (let i = 1; i < cars.length; i += 1) {
        byGap += (cars[i].gapAheadS ?? 0) * spread
        const desired = byGap * (1 - s.uniform) + spread * i * s.uniform
        const goal = s.travelled[0] - desired

        // Acelera si quedó lejos y levanta si se pasó, pero la velocidad nunca
        // baja de cero: acá está el arreglo del retroceso.
        //
        // `roll` es lo que puede avanzar aunque el ritmo de carrera sea cero.
        // Sin esto, con bandera roja el pelotón quedaba desparramado por el
        // circuito porque nadie tenía con qué llegar hasta la parrilla.
        const roll = lps * 0.75 * held
        const correction = clamp(
          (goal - s.travelled[i]) * RATE.catchup,
          -base * 0.6,
          base * MAX_CATCHUP + roll + lps * 0.04,
        )
        // En verde manda el ritmo propio y la corrección casi no interviene;
        // neutralizado es al revés y el pelotón se acomoda en formación.
        const own = base * carPace(cars[i], held)
        s.travelled[i] += Math.max(0, dt * (own + correction * held))
      }

      // El orden en pista sale de la distancia recorrida, así que un
      // adelantamiento aparece solo cuando un auto pasa al de adelante.
      const order = cars
        .map((_, i) => i)
        .sort((a, b) => s.travelled[b] - s.travelled[a])

      // Los intervalos se reconstruyen desde la simulación deshaciendo la
      // escala con la que se repartió el pelotón, así vuelven a leerse en
      // segundos. Son los de ahora, no los del dato de la vuelta 30.
      const gapAhead: (number | null)[] = cars.map(() => null)
      const gapLeader: number[] = cars.map(() => 0)
      const head = s.travelled[order[0]]
      for (let place = 0; place < order.length; place += 1) {
        const car = order[place]
        gapLeader[car] = spread > 0 ? (head - s.travelled[car]) / spread : 0
        gapAhead[car] =
          place === 0
            ? null
            : spread > 0
              ? (s.travelled[order[place - 1]] - s.travelled[car]) / spread
              : 0
      }

      setSnapshot({
        pace: s.pace,
        gridded: s.gridded,
        uniform: s.uniform,
        positions: s.travelled.map((v) => ((v % 1) + 1) % 1),
        order,
      })

      // La tabla se refresca aparte, más lento: ver TIMING_INTERVAL_MS.
      if (now - lastTiming.current >= TIMING_INTERVAL_MS) {
        lastTiming.current = now
        setTiming({ order, gapAhead, gapLeader })
      }
      frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing])

  return { field: snapshot, timing }
}
