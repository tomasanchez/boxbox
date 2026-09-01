/**
 * Trazado del circuito, replicando el render del concepto.
 *
 * La pista se dibuja con **tres paths apilados sobre la misma `d`**: dos trazos
 * gruesos en el color del estado y uno más fino del color del fondo. El tercero
 * vacía el centro, así que lo que queda a la vista son los dos bordes finos y
 * paralelos del asfalto.
 *
 * El estado de pista no sólo repinta: cambia **dónde y cómo** se ubican los
 * autos, que es lo que pasa en la realidad.
 *
 *   verde     el pelotón estirado, cada uno a su intervalo
 *   amarilla  igual, pero con el sector del incidente marcado
 *   VSC       distancias congeladas — nadie gana ni pierde terreno
 *   SC        se reagrupan detrás del coche de seguridad
 *   roja      forman en la parrilla, detenidos, esperando el relanzamiento
 */

import { type ReactNode, useLayoutEffect, useRef, useState } from 'react'
import { STATUS } from './status'
import { STARTING_GRID } from './startingGrid'
import type { Track } from './tracks'
import type { DriverState, TrackStatus } from './types'
import type { FieldState } from './useField'

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
  status,
  field,
  lap,
  children,
}: {
  track: Track
  drivers: DriverState[]
  /** Vuelta actual: los que ya abandonaron dejan de dibujarse. */
  lap: number
  /** El estado de pista pinta el trazado. */
  status: TrackStatus
  /** Posición interpolada del pelotón; ver `useField`. */
  field: FieldState
  /** Contenido superpuesto sobre el mapa. */
  children?: ReactNode
}) {
  const spec = STATUS[status]
  const pathRef = useRef<SVGPathElement>(null)
  const [placed, setPlaced] = useState<Placed[]>([])
  const [total, setTotal] = useState(0)

  useLayoutEffect(() => {
    const node = pathRef.current
    if (!node) return

    const length = node.getTotalLength()
    setTotal(length)

    const box = node.getBBox()
    const midX = box.x + box.width / 2

    // Las posiciones llegan resueltas desde `useField`: acá sólo se traducen a
    // coordenadas sobre el path. Toda la física vive en el hook.
    setPlaced(
      drivers.map((driver, index) => {
        const at = field.positions[index] ?? 0
        const point = node.getPointAtLength(at * length)

        // Filas de a dos, una a cada lado de la línea de carrera: los puestos
        // impares de un lado y los pares del otro, como una grilla real. El
        // lado sale del puesto de largada, no del orden del arreglo.
        const slot = STARTING_GRID.indexOf(driver.code)
        const stagger = (slot >= 0 ? slot : 0) % 2 === 0 ? -1 : 1
        const ahead = node.getPointAtLength(Math.min(at * length + 6, length))
        const dx = ahead.x - point.x
        const dy = ahead.y - point.y
        const norm = Math.hypot(dx, dy) || 1
        // Normal a la dirección de marcha.
        const offset = 22 * stagger * field.gridded
        const x = point.x + (-dy / norm) * offset
        const y = point.y + (dx / norm) * offset

        const outward = x < midX ? -1 : 1
        return {
          driver,
          x,
          y,
          labelX: x + outward * 20,
          anchor: outward < 0 ? ('end' as const) : ('start' as const),
        }
      }),
    )
  }, [track.path, drivers, field.positions, field.gridded])

  // El sector afectado se dibuja encima con un guion del largo justo.
  const sector = spec.sector
  const sectorDash =
    sector && total
      ? {
          dashArray: `${(sector[1] - sector[0]) * total} ${total}`,
          dashOffset: -sector[0] * total,
        }
      : null

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

        {/* Amarilla es por sector: se marca sólo el tramo afectado. */}
        {sectorDash ? (
          <path
            className="circuit__sector"
            d={track.path}
            fill="none"
            stroke="#f5c518"
            strokeWidth={spec.width + 8}
            strokeLinecap="butt"
            strokeDasharray={sectorDash.dashArray}
            strokeDashoffset={sectorDash.dashOffset}
          />
        ) : null}

        <g stroke="#f4f3f2" strokeWidth={4}>
          <line
            x1={track.startLine.x1}
            y1={track.startLine.y1}
            x2={track.startLine.x2}
            y2={track.startLine.y2}
          />
        </g>

        {placed
          .filter(({ driver }) => driver.retiredOnLap == null || lap <= driver.retiredOnLap)
          .map(({ driver, x, y, labelX, anchor }) => (
          <g key={driver.code}>
            <circle cx={x} cy={y} r={15} fill={INNER_COLOR} />
            <circle cx={x} cy={y} r={12} fill={driver.teamColor} />
            <text
              x={labelX}
              y={y + 8}
              fill="#f4f3f2"
              fontFamily="Archivo, sans-serif"
              fontSize={24 - 7 * field.gridded}
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
