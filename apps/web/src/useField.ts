/**
 * Estado físico del pelotón, interpolado cuadro a cuadro.
 *
 * Los cambios de estado de pista **no son instantáneos en la realidad**: cuando
 * sale el safety car los autos tardan una vuelta larga en juntarse, y con
 * bandera roja ruedan hasta la parrilla antes de detenerse. Si la UI salta de
 * un arreglo al otro, se pierde justamente lo que hace entendible la maniobra.
 *
 * Acá cada magnitud —separación, ritmo, y el punto donde está la cabeza del
 * pelotón— persigue su objetivo con una interpolación exponencial: se acerca
 * una fracción de la distancia restante en cada cuadro. Es el mismo enfoque del
 * concepto: `valor += (objetivo - valor) * min(1, dt * tasa)`.
 */

import { useEffect, useRef, useState } from 'react'
import { STATUS } from './status'
import type { TrackStatus } from './types'

/** Qué tan rápido converge cada magnitud, en unidades por segundo. */
const RATE = {
  /** La separación es lo más lento: juntar al pelotón lleva su tiempo. */
  spacing: 1.2,
  /** Levantar o bajar el pie es más inmediato. */
  pace: 1.8,
  /** Rodar hasta la parrilla, con bandera roja. */
  toGrid: 0.7,
  /** Pasar de orden por intervalo a formación pareja. */
  uniform: 1.1,
}



export interface FieldState {
  /** Separación actual entre autos, como fracción de vuelta. */
  spacing: number
  /** Ritmo actual, de 0 (detenido) a 1 (carrera). */
  pace: number
  /** Dónde está la cabeza del pelotón dentro de la vuelta, 0 a 1. */
  anchor: number
  /** 0 = corriendo en pista, 1 = formado en la parrilla. */
  gridded: number
  /**
   * Cuánto se ordena el pelotón por posición en lugar de por intervalo.
   *
   * Es la diferencia entre correr y estar neutralizado. En carrera cada auto
   * está donde lo pone su intervalo, y un rezagado a 16 s queda lejos. Detrás
   * del safety car el pelotón se forma **parejo**, a pocos metros uno del otro,
   * sin importar la diferencia que traían. Sin este término los rezagados nunca
   * terminaban de agruparse.
   */
  uniform: number
}

/** Interpolación exponencial estable ante saltos de cuadro. */
function approach(current: number, target: number, rate: number, dt: number): number {
  return current + (target - current) * Math.min(1, dt * rate)
}

export function useField(
  status: TrackStatus,
  playing: boolean,
  /** Milisegundos de reloj por vuelta a ritmo pleno; sale del selector. */
  msPerLap: number,
): FieldState {
  const spec = STATUS[status]

  // El acumulador muta en la ref —una asignación por cuadro, sin renders— y se
  // publica como instantánea inmutable al final del cuadro. Así el render nunca
  // lee la ref y el componente se entera del cambio por la vía normal.
  const initial: FieldState = {
    spacing: spec.spacing,
    pace: spec.pace,
    anchor: 0,
    gridded: 0,
    uniform: 0,
  }
  const acc = useRef<FieldState>(initial)
  const [snapshot, setSnapshot] = useState<FieldState>(initial)

  // El objetivo se lee de una ref para que cambiar de estado o de velocidad no
  // reinicie el bucle de animación a mitad de una transición. La asignación va
  // en un efecto, no en el render.
  const target = useRef(spec)
  const lapsPerSecond = useRef(1000 / msPerLap)

  useEffect(() => {
    target.current = spec
  }, [spec])

  useEffect(() => {
    lapsPerSecond.current = 1000 / msPerLap
  }, [msPerLap])

  useEffect(() => {
    let frame = 0
    let last = performance.now()

    const tick = (now: number) => {
      // Al volver de una pestaña en segundo plano el delta puede ser enorme;
      // se acota para que el pelotón no pegue un salto.
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now

      const t = target.current
      const state = acc.current

      state.spacing = approach(state.spacing, t.spacing, RATE.spacing, dt)
      state.pace = approach(state.pace, playing ? t.pace : 0, RATE.pace, dt)
      state.gridded = approach(state.gridded, t.field === 'grid' ? 1 : 0, RATE.toGrid, dt)
      // Detrás del safety car y en parrilla la formación es pareja; corriendo
      // y bajo VSC cada uno conserva su intervalo.
      const uniformTarget = t.field === 'bunch' || t.field === 'grid' ? 1 : 0
      state.uniform = approach(state.uniform, uniformTarget, RATE.uniform, dt)

      // La cabeza del pelotón avanza al ritmo actual. Con bandera roja el ritmo
      // cae a cero, así que se frena sola en lugar de cortarse de golpe.
      state.anchor = (state.anchor + dt * state.pace * lapsPerSecond.current) % 1

      setSnapshot({ ...state })
      frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing])

  return snapshot
}
