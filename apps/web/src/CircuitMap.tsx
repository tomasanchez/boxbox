/**
 * Trazado del circuito, replicando el render del concepto.
 *
 * La pista se dibuja con **tres paths apilados sobre la misma `d`**:
 *
 *   1. trazo grueso en gris  (#4a4644, ancho 14)
 *   2. el mismo trazo otra vez, para densificar las esquinas
 *   3. trazo más fino del color del fondo (#131211, ancho 9)
 *
 * El tercero vacía el centro, así que lo que queda a la vista son los dos
 * bordes finos y paralelos del asfalto. Es el truco que hace que se lea como
 * un circuito y no como una línea gruesa.
 *
 * Los autos son un halo oscuro, el disco del color del equipo, y el código del
 * piloto **por fuera** del disco — nunca encima, que es lo que lo volvía
 * ilegible.
 */

import { type ReactNode, useLayoutEffect, useRef, useState } from 'react'
import { STATUS } from './status'
import type { Track } from './tracks'
import type { DriverState, TrackStatus } from './types'

const INNER_COLOR = '#131211'
/** Cuánto más fino es el trazo interior que vacía el centro del asfalto. */
const INNER_INSET = 13

interface Placed {
  driver: DriverState
  x: number
  y: number
  labelX: number
  anchor: 'start' | 'end'
}

export function CircuitMap({
  track,
  drivers,
  lapFraction,
  status,
  children,
}: {
  track: Track
  drivers: DriverState[]
  /** Avance dentro de la vuelta actual, 0 a 1. */
  lapFraction: number
  /** El estado de pista pinta el trazado y agrupa al pelotón. */
  status: TrackStatus
  /** Contenido superpuesto sobre el mapa. */
  children?: ReactNode
}) {
  const spec = STATUS[status]
  const pathRef = useRef<SVGPathElement>(null)
  const [placed, setPlaced] = useState<Placed[]>([])

  useLayoutEffect(() => {
    const node = pathRef.current
    if (!node) return

    const total = node.getTotalLength()
    const box = node.getBBox()
    const midX = box.x + box.width / 2

    // Separación entre autos. En verde el pelotón está estirado; bajo Safety
    // Car se agrupa y con bandera roja va casi pegado, como en la realidad.
    // El valor de verde está exagerado respecto de la física (~0,012 por
    // segundo de intervalo) para que los códigos se lean.
    const perSecond = (STATUS[status].spacing / 0.055) * 0.045

    let cumulative = 0
    setPlaced(
      drivers.map((driver) => {
        cumulative += (driver.gapAheadS ?? 0) * perSecond
        const at = (((lapFraction - cumulative) % 1) + 1) % 1
        const point = node.getPointAtLength(at * total)
        // La etiqueta se va hacia afuera del circuito para no taparlo.
        const outward = point.x < midX ? -1 : 1
        return {
          driver,
          x: point.x,
          y: point.y,
          labelX: point.x + outward * 24,
          anchor: outward < 0 ? ('end' as const) : ('start' as const),
        }
      }),
    )
  }, [track.path, drivers, lapFraction, status])

  return (
    <div className="circuit panel__grow">
      <svg
        viewBox={track.viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Trazado de ${track.name}`}
      >
        <path
          ref={pathRef}
          d={track.path}
          fill="none"
          stroke={spec.stroke}
          strokeWidth={spec.width}
          strokeLinejoin="round"
        />
        <path
          d={track.path}
          fill="none"
          stroke={spec.stroke}
          strokeWidth={spec.width}
          strokeLinejoin="round"
        />
        <path
          d={track.path}
          fill="none"
          stroke={INNER_COLOR}
          strokeWidth={Math.max(spec.width - INNER_INSET, 4)}
          strokeLinejoin="round"
        />

        <g stroke="#f4f3f2" strokeWidth={4}>
          <line
            x1={track.startLine.x1}
            y1={track.startLine.y1}
            x2={track.startLine.x2}
            y2={track.startLine.y2}
          />
        </g>

        {placed.map(({ driver, x, y, labelX, anchor }) => (
          <g key={driver.code}>
            <circle cx={x} cy={y} r={15} fill={INNER_COLOR} />
            <circle cx={x} cy={y} r={12} fill={driver.teamColor} />
            <text
              x={labelX}
              y={y + 8}
              fill="#f4f3f2"
              fontFamily="Archivo, sans-serif"
              fontSize={24}
              fontWeight={800}
              textAnchor={anchor}
            >
              {driver.code}
            </text>
          </g>
        ))}
      </svg>
      {children}
    </div>
  )
}
