/**
 * Selector de piloto: los veintidós, en orden de grilla.
 *
 * El que se elige pasa a ser el **auto focal de toda la vista** (ADR-007): se
 * destaca en el mapa y en la torre de tiempos, y es del que hablan todas las
 * tarjetas. Por eso el selector no es un desplegable perdido en una esquina —
 * es la columna de la izquierda y está siempre a la vista.
 *
 * El hueco a la pole va al lado del código porque es lo que ordena la grilla y
 * lo único que separa a los autos antes de largar: son huecos de clasificación
 * reales, no una escalera inventada (ADR-004).
 *
 * Teclado: es un grupo de radios con tabulación rodante. Una sola parada de
 * tabulador para las veintidós opciones, y las flechas mueven la elección, que
 * es como se comporta cualquier lista de opción única.
 */

import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { fmt } from './format'
import { PRERACE, PRERACE_CARS, teamColor } from './prerace'
import { Panel } from './ui'

export function DriverPicker({
  focal,
  onFocal,
}: {
  focal: string
  onFocal: (code: string) => void
}) {
  const listRef = useRef<HTMLDivElement>(null)

  /** Flechas, inicio y fin: mueven la elección y el foco juntos. */
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = PRERACE_CARS.findIndex((car) => car.code === focal)
    if (index < 0) return

    const last = PRERACE_CARS.length - 1
    let next = index
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = Math.min(index + 1, last)
    else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = Math.max(index - 1, 0)
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = last
    else return

    event.preventDefault()
    const code = PRERACE_CARS[next].code
    onFocal(code)
    listRef.current?.querySelector<HTMLButtonElement>(`[data-code="${code}"]`)?.focus()
  }

  return (
    <Panel
      title="Elegí un piloto"
      note={`${PRERACE.race.cars} autos · clasificación real · pole ${fmt(PRERACE.race.pole_s, 3)} s`}
      fill
    >
      <div
        className="picker panel__grow"
        role="radiogroup"
        aria-label="Piloto a simular"
        ref={listRef}
        onKeyDown={onKeyDown}
      >
        {PRERACE_CARS.map((car) => {
          const chosen = car.code === focal
          return (
            <button
              key={car.code}
              type="button"
              role="radio"
              aria-checked={chosen}
              tabIndex={chosen ? 0 : -1}
              data-code={car.code}
              className="picker__row"
              onClick={() => onFocal(car.code)}
              title={`${car.driver} · ${car.team}`}
            >
              {/* El triángulo marca al elegido sin depender del color. */}
              <span className="picker__mark" aria-hidden="true">
                {chosen ? '▸' : ''}
              </span>
              <span className="picker__pos num">P{car.grid_position}</span>
              <span className="picker__team" style={{ background: teamColor(car.code) }} />
              <span className="picker__code">{car.code}</span>
              <span className="picker__gap num">
                {car.gap_to_pole_s === 0 ? 'pole' : `+${fmt(car.gap_to_pole_s, 3)}`}
              </span>
            </button>
          )
        })}
      </div>
    </Panel>
  )
}
