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
import type { Track } from './tracks'
import type { DriverState, TrackStatus } from './types'
import type { FieldState } from './useField'

const INNER_COLOR = '#131211'
/** Cuánto más fino es el trazo interior que vacía el centro del asfalto. */
const INNER_INSET = 13

/**
 * Separación en verde, como fracción de vuelta por segundo de intervalo. El
 * valor físico sería ~0,012 (la vuelta ronda los 80 s); se exagera para que los
 * códigos se lean. Por eso el panel declara el reparto como esquemático.
 */
const SPREAD_GREEN = 0.045

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
  children,
}: {
  track: Track
  drivers: DriverState[]
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

    // La separación viene interpolada, así que juntarse o estirarse ocurre de
    // a poco en lugar de en un salto.
    const spread = (field.spacing / STATUS.GREEN.spacing) * SPREAD_GREEN

    // `gridded` va de 0 a 1 mientras los autos ruedan hacia la parrilla: la
    // cabeza del pelotón se desliza desde donde estaba hasta la línea de meta.
    const anchor = field.anchor * (1 - field.gridded)

    let byGap = 0
    setPlaced(
      drivers.map((driver, index) => {
        byGap += (driver.gapAheadS ?? 0) * spread
        // En parrilla el orden es por posición; en pista, por intervalo. Se
        // mezclan los dos según cuánto se avanzó hacia la formación.
        const cumulative = byGap * (1 - field.gridded) + spread * index * field.gridded

        const at = (((anchor - cumulative) % 1) + 1) % 1
        const point = node.getPointAtLength(at * length)
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
  }, [track.path, drivers, field.spacing, field.anchor, field.gridded])

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
