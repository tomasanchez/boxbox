/**
 * La carrera desde la vuelta 1, y su relación con la recomendación (ADR-006).
 *
 * Acá está la contradicción que el trabajo decidió mostrar en vez de esconder:
 * **la recomendación sale de 1.200 carreras sorteadas y lo que se anima es
 * una**. La carrera que se ve puede terminar lejos de la llegada esperada, y eso
 * no es un error de la recomendación: es la dispersión que la recomendación ya
 * declaraba.
 *
 * Por eso la llegada se dibuja como banda —media ± un desvío— con la trayectoria
 * del sorteo en curso encima, y hay un botón para volver a sortear. Tirar los
 * dados otra vez y ver otra carrera con el mismo plan es la demostración.
 *
 * La línea de tiempo marca las paradas del plan. Cuando la carrera corre, cada
 * auto ejecuta el plan que le dio el algoritmo; lo que se sortea es cuánto se
 * cae la goma, cuánto cuesta cada parada y cuánto ruido tiene cada vuelta.
 */

import { COMPOUND_COLOR, COMPOUND_LETTER, RACE } from './data'
import { fmt } from './format'
import { PRERACE, arrivalBand, stintsOf } from './prerace'
import type { PreRaceCar } from './prerace'
import { Panel } from './ui'

const W = 300
const H = 64

/** Cuántos autos tiene la parrilla: sale del export, no de la memoria. */
const CARS = PRERACE.race.cars

export function StartRaceCard({
  car,
  lap,
  running,
  playing,
  seed,
  track,
  onStart,
  onRedraw,
  onSnapshot,
  onWatch,
}: {
  car: PreRaceCar
  lap: number
  /** La simulación arranca en la parrilla, no en la foto de la vuelta 30. */
  running: boolean
  playing: boolean
  seed: number
  /** Puesto del auto focal por vuelta, medido sobre la simulación en curso. */
  track: number[]
  onStart: () => void
  onRedraw: () => void
  onSnapshot: () => void
  onWatch: () => void
}) {
  const band = arrivalBand(car)
  const stints = stintsOf(car.plan)

  const x = (atLap: number) => ((atLap - 1) / (RACE.totalLaps - 1)) * W
  const y = (position: number) => 6 + ((position - 1) / (CARS - 1)) * (H - 12)

  // La trayectoria se dibuja con las vueltas que ya ocurrieron. Los huecos —una
  // vuelta sin muestra porque la torre publica más lento que la animación— se
  // saltean en vez de rellenarse.
  const points: string[] = []
  if (running) {
    for (let l = 1; l <= Math.min(lap, RACE.totalLaps); l += 1) {
      const place = track[l]
      if (place) points.push(`${points.length === 0 ? 'M' : 'L'} ${x(l)} ${y(place)}`)
    }
  }
  /*
   * El puesto se anota al **cerrar** cada vuelta, así que la vuelta en curso
   * todavía no tiene el suyo. Se muestra el último cierre y se dice de qué
   * vuelta es, en vez de dar por buena la posición de una vuelta a medio correr.
   */
  let closed = 0
  for (let l = Math.min(lap, RACE.totalLaps); l >= 1; l -= 1) {
    if (track[l]) {
      closed = l
      break
    }
  }
  const now = closed > 0 ? track[closed] : undefined
  const pct = (atLap: number) => ((atLap - 1) / (RACE.totalLaps - 1)) * 100

  return (
    <Panel
      title="La carrera, desde la largada"
      note={running ? `sorteo con semilla ${seed}` : 'todavía no largó'}
    >
      <div className="run">
        <button type="button" className="run__go" onClick={onStart}>
          ▶ Correr desde la vuelta 1
        </button>
        <button type="button" className="scenario" onClick={onRedraw}>
          ⟳ Volver a sortear
        </button>
        <button type="button" className="scenario" onClick={onWatch}>
          Ver el mapa
        </button>
        <button type="button" className="scenario" onClick={onSnapshot} aria-pressed={!running}>
          Foto V30
        </button>
      </div>

      {/* ------------------------------------------ línea de tiempo del plan */}
      <div className="timeline">
        {stints.map((stint, index) => (
          <span
            className="timeline__stint"
            key={`${stint.compound}-${index}`}
            style={{
              left: `${((stint.fromLap - 1) / RACE.totalLaps) * 100}%`,
              width: `${(stint.laps / RACE.totalLaps) * 100}%`,
              background: COMPOUND_COLOR[stint.compound],
            }}
            title={`${stint.compound}: vueltas ${stint.fromLap} a ${stint.fromLap + stint.laps - 1}`}
          />
        ))}
        {car.stops.map((stop) => (
          <span
            className="timeline__stop"
            key={stop.lap}
            style={{ left: `${((stop.lap - 1) / RACE.totalLaps) * 100}%` }}
            title={`Parada en la vuelta ${stop.lap}, calza ${stop.compound}`}
          >
            <span className="timeline__flag">
              V{stop.lap} {COMPOUND_LETTER[stop.compound]}
            </span>
          </span>
        ))}
        {running ? (
          <span className="timeline__now" style={{ left: `${pct(lap)}%` }} />
        ) : null}
      </div>

      {/* ------------------------------------- banda de llegada y trayectoria */}
      <div className="trace">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className="trace__svg"
          role="img"
          aria-label={`Banda de llegada entre el puesto ${fmt(band.low, 1)} y el ${fmt(
            band.high,
            1,
          )}${now ? `. Cerró la vuelta ${closed} en el puesto ${now}.` : ''}`}
        >
          <rect
            x={0}
            y={y(band.low)}
            width={W}
            height={Math.max(y(band.high) - y(band.low), 1)}
            className="trace__band"
          />
          <line x1={0} y1={y(band.mean)} x2={W} y2={y(band.mean)} className="trace__mean" />
          {points.length > 1 ? <path d={points.join(' ')} className="trace__line" /> : null}
          {running ? <line x1={x(lap)} y1={0} x2={x(lap)} y2={H} className="trace__now" /> : null}
        </svg>
        <span className="trace__tag trace__tag--band">
          banda de llegada P{fmt(band.low, 1)}–P{fmt(band.high, 1)}
        </span>
        <span className="trace__tag trace__tag--live">
          {running
            ? now
              ? `V${lap} · ${now}.º al cierre de la V${closed}${playing ? '' : ' · en pausa'}`
              : `V${lap} · todavía sin vuelta cerrada`
            : 'sin sorteo en curso'}
        </span>
      </div>

      <p className="footnote">
        Lo que corre es <strong>un sorteo</strong>; la recomendación salió de{' '}
        <strong>{PRERACE.checks.draws.toLocaleString('es-AR')} carreras</strong>. Si esta termina
        fuera de la banda no es que el plan falló:
        es la dispersión que el plan ya declaraba. Volvé a sortear y mirá salir otra.
      </p>
    </Panel>
  )
}
