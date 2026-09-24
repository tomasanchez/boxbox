/**
 * Vista pre-carrera: elegir un piloto y ver de dónde sale su plan.
 *
 * Se lee de izquierda a derecha y ese orden es el argumento:
 *
 *   1. **Quién.** Los veintidós en orden de grilla (ADR-007). El elegido manda
 *      en toda la vista, incluido el mapa y la torre de la otra pestaña.
 *   2. **Cómo se encontró.** La población del algoritmo genético convergiendo
 *      generación a generación (ADR-005). Es la pieza que muestra que esto es
 *      una búsqueda evolutiva y no una tabla de consulta.
 *   3. **Qué salió, y con cuánta incertidumbre.** El plan, las cuatro
 *      probabilidades y la llegada como banda (ADR-001), más la carrera animada
 *      desde la largada con su botón de re-sorteo (ADR-006).
 *
 * Los supuestos del export van en pantalla, abiertos con un clic. Son cinco
 * frases que dicen qué NO está medido —que todos largan en medio, que los
 * rivales no reaccionan, que nadie abandona— y sin ellas varias cifras de esta
 * pantalla se leerían como más seguras de lo que son.
 */

import { DriverPicker } from './DriverPicker'
import { EvolutionCard } from './EvolutionCard'
import { OutcomeCard } from './OutcomeCard'
import { PlanCard } from './PlanCard'
import { StartRaceCard } from './StartRaceCard'
import { PRERACE, type RivalsMode, preraceCar } from './prerace'

export function PreRaceView({
  focal,
  onFocal,
  lap,
  running,
  playing,
  seed,
  track,
  onStart,
  onRedraw,
  onWatch,
  rivals,
}: {
  focal: string
  onFocal: (code: string) => void
  lap: number
  running: boolean
  playing: boolean
  seed: number
  track: number[]
  onStart: () => void
  onRedraw: () => void
  onWatch: () => void
  /** Qué corrida se está mirando: la de rivales con plan fijo o la reactiva. */
  rivals: RivalsMode
}) {
  const car = preraceCar(focal, rivals)

  return (
    <div className="view view--prerace">
      <div className="stack stack--prerace-left">
        <DriverPicker focal={focal} onFocal={onFocal} />

        <details className="notes">
          <summary className="notes__summary">
            Supuestos del export ({PRERACE.assumptions.length})
          </summary>
          <ul className="notes__list">
            {PRERACE.assumptions.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      </div>

      <div className="stack stack--prerace-mid">
        {/*
          * `key` por piloto: elegir otro auto **remonta** la tarjeta y la
          * animación vuelve a correr desde la generación cero sin que haya que
          * reiniciarla a mano.
          */}
        <EvolutionCard key={car.code} car={car} />
        <StartRaceCard
          car={car}
          lap={lap}
          running={running}
          playing={playing}
          seed={seed}
          track={track}
          onStart={onStart}
          onRedraw={onRedraw}
          onWatch={onWatch}
        />
      </div>

      <div className="stack stack--prerace-right">
        <PlanCard car={car} />
        <OutcomeCard car={car} />
      </div>
    </div>
  )
}
