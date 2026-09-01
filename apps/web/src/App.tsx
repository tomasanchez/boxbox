/**
 * Simulador de estrategia — armazón.
 *
 * Todo entra en el viewport: el `.app` es una grilla de tres filas con la
 * última en `minmax(0,1fr)`, y ningún contenedor scrollea. Ver `styles.css`.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ForecastView } from './ForecastView'
import { PlaybackControls } from './Playback'
import { SPEEDS } from './playback-clock'
import { RaceView } from './RaceView'
import { GRID, RACE } from './data'
import { STATUS, STATUS_ORDER, fieldNote } from './status'
import { useField } from './useField'
import { Kpi } from './ui'
import type { TrackStatus } from './types'

type View = 'race' | 'forecast'

const TABS: { id: View; label: string }[] = [
  { id: 'race', label: 'Panel de carrera' },
  { id: 'forecast', label: 'Pronóstico' },
]

/** Los autos que se dibujan en el mapa. Se fija fuera del componente para que
 *  la identidad del arreglo no cambie en cada render y reinicie la simulación. */
const FIELD_CARS = GRID.slice(0, 8)

export default function App() {
  // El hash permite abrir una vista directo (y sacarle captura sin interactuar).
  const initial: View = window.location.hash === '#forecast' ? 'forecast' : 'race'
  const [view, setView] = useState<View>(initial)
  const [status, setStatus] = useState<TrackStatus>('GREEN')
  const [lap, setLap] = useState(RACE.currentLap)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[1])

  const spec = STATUS[status]

  const advance = useCallback(() => {
    setLap((current) => {
      if (current >= RACE.totalLaps) {
        setPlaying(false)
        return current
      }
      return current + 1
    })
  }, [])

  // El pelotón vive en useField: separación, ritmo y posición se interpolan
  // cuadro a cuadro, así que cambiar de estado es una maniobra y no un salto.
  const field = useField(FIELD_CARS, status, playing, speed.msPerLap, lap)

  // La vuelta avanza cuando la cabeza del pelotón cruza la meta.
  const crossed = useRef(field.positions[0] ?? 0)
  useEffect(() => {
    const head = field.positions[0] ?? 0
    if (crossed.current > 0.8 && head < 0.2) advance()
    crossed.current = head
  }, [field.positions, advance])

  const togglePlay = useCallback(() => setPlaying((current) => !current), [])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <div>
            <div className="brand__name">Simulador de estrategia</div>
            <div className="brand__race">
              {RACE.season} · R{RACE.round} {RACE.circuit}
            </div>
          </div>
        </div>

        <div className="tabs" role="tablist" aria-label="Vistas">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              className="tab"
              aria-selected={view === t.id}
              onClick={() => {
                setView(t.id)
                window.location.hash = t.id
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="scenarios" role="group" aria-label="Estado de pista">
          {STATUS_ORDER.map((id) => (
            <button
              key={id}
              type="button"
              className="scenario"
              aria-pressed={status === id}
              onClick={() => setStatus(id)}
            >
              {STATUS[id].label}
            </button>
          ))}
        </div>
      </header>

      <div className="strip">
        <Kpi
          label="Vuelta"
          value={`${lap} / ${RACE.totalLaps}`}
          note={`quedan ${RACE.totalLaps - lap}`}
        />
        <Kpi
          label="Costo de parar"
          value={`${spec.cost} pos`}
          note={spec.costNote}
          tone={spec.cost === '0,0' ? 'good' : 'alert'}
        />
        <Kpi
          label="Prob. Safety Car"
          value="0,571"
          note="tasa global medida"
        />
        <Kpi
          label="Compuestos obligatorios"
          value={RACE.mandatoryCompounds.length === 2 ? 'M + H' : '—'}
          note={`mínimo ${RACE.minSets} juegos · B6.3.8`}
        />
        <div className="kpi kpi--wide">
          <span className="kpi__label">Reproducción</span>
          <PlaybackControls
            playing={playing}
            onTogglePlay={togglePlay}
            speed={speed}
            onSpeed={setSpeed}
            lap={lap}
            totalLaps={RACE.totalLaps}
            onLap={(next) => {
              setPlaying(false)
              setLap(next)
            }}
            homeLap={RACE.currentLap}
          />
        </div>
      </div>

      <div
        className={`statusbar statusbar--${status}`}
        style={{ backgroundColor: spec.color, color: spec.fg }}
        role="status"
      >
        <span className="statusbar__dot" style={{ background: spec.fg }} />
        <span className="statusbar__label">{spec.label}</span>
        <span className="statusbar__note">{spec.note}</span>
        {lap <= 1 ? (
          <span className="statusbar__field">Parrilla de salida</span>
        ) : fieldNote(status, true) ? (
          <span className="statusbar__field">{fieldNote(status, true)}</span>
        ) : null}
      </div>

      {view === 'race' ? (
        <RaceView scenarioLap={lap} status={status} field={field} cars={FIELD_CARS} />
      ) : (
        <ForecastView />
      )}
    </div>
  )
}
