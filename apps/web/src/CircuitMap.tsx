/**
 * Trazado real con los autos ubicados sobre la pista.
 *
 * Las posiciones se calculan con `getPointAtLength` sobre el propio path, así
 * que los autos caen exactamente sobre el asfalto en vez de sobre una elipse
 * aproximada. Requiere el nodo montado, de ahí el `useLayoutEffect`.
 *
 * El reparto a lo largo de la vuelta es **ilustrativo**: separa los autos según
 * el intervalo acumulado al líder para que se lean, pero no es telemetría de
 * posición real, que FastF1 sí publica y todavía no ingerimos.
 */

import { useLayoutEffect, useRef, useState } from 'react'
import type { DriverState } from './types'
import type { Track } from './tracks'

interface Placed {
  driver: DriverState
  x: number
  y: number
}

export function CircuitMap({
  track,
  drivers,
  lapFraction,
}: {
  track: Track
  drivers: DriverState[]
  /** Avance dentro de la vuelta actual, 0 a 1. */
  lapFraction: number
}) {
  const pathRef = useRef<SVGPathElement>(null)
  const [placed, setPlaced] = useState<Placed[]>([])

  useLayoutEffect(() => {
    const node = pathRef.current
    if (!node) return

    const total = node.getTotalLength()

    // Cuánta vuelta representa un segundo de intervalo. El valor físico sería
    // ~0,012 (una vuelta ronda los 80 s), pero a esa escala los autos quedan
    // literalmente encimados y no se leen los números. Se exagera a propósito;
    // por eso el panel dice que el reparto es ilustrativo.
    const perSecond = 0.045

    let cumulative = 0
    const next = drivers.map((driver) => {
      cumulative += (driver.gapAheadS ?? 0) * perSecond
      // Se recorre hacia atrás desde el punto de cabeza.
      const at = (((lapFraction - cumulative) % 1) + 1) % 1
      const point = node.getPointAtLength(at * total)
      return { driver, x: point.x, y: point.y }
    })
    setPlaced(next)
  }, [track.path, drivers, lapFraction])

  return (
    <div className="circuit">
      <svg viewBox="-6 -6 112 112" role="img" aria-label={`Trazado de ${track.name}`}>
        <path ref={pathRef} className="circuit__path" d={track.path} />
        <path className="circuit__inner" d={track.path} />

        {placed.map(({ driver, x, y }) => (
          <g key={driver.code}>
            <circle
              className="circuit__car"
              cx={x}
              cy={y}
              r={3.4}
              fill={driver.teamColor}
            />
            <text className="circuit__label" x={x} y={y + 1.3} textAnchor="middle">
              {driver.position}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
