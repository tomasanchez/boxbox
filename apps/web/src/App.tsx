/**
 * Simulador de estrategia — armazón.
 *
 * **De 1024 px de ancho para arriba** todo entra en el viewport: el `.app` es
 * una grilla de tres filas más la vista, la última en `minmax(0,1fr)`, y ningún
 * contenedor scrollea. Ese es el diseño, y es el rango donde se toman las
 * capturas de referencia.
 *
 * Abajo de 1024 el principio **se abandona a propósito**, porque sostenerlo
 * ahí sólo se puede recortando dato:
 *
 *   768–1024  una sola columna con scroll vertical, en el orden de lectura de
 *             una transmisión: torre de tiempos → mapa → tarjetas. Es el orden
 *             que ya tiene el DOM, así que no se reordena nada: las tarjetas
 *             del mapa dejan de ser capa absoluta y pasan a fluir.
 *   < 768     sin soporte, y dicho en pantalla (`Viewport.tsx`). Abajo de ese
 *             ancho `App` ni siquiera se monta.
 *
 * Todo eso vive en el bloque final de `styles.css`, que es donde está también
 * la explicación de por qué el corte es 1024 y no otro número.
 *
 * Acá viven tres cosas que las tres vistas comparten y que por eso no pueden
 * vivir más abajo (ADR-007):
 *
 *   `focal`   el piloto elegido. Es el auto que se destaca en el mapa y en la
 *             torre, y del que hablan las tarjetas de la vista pre-carrera.
 *   `origin`  desde dónde arranca la simulación: la foto medida de la vuelta 30
 *             o la parrilla de largada con el plan que dio el algoritmo.
 *   `seed`    la semilla del sorteo. El botón de re-sorteo la cambia, y con eso
 *             la misma recomendación produce otra carrera — que es la tesis del
 *             trabajo, no un bug (ADR-006).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ForecastView } from './ForecastView'
import { PlaybackControls } from './Playback'
import { SPEEDS } from './playback-clock'
import { PreRaceView } from './PreRaceView'
import { RaceView } from './RaceView'
import { GRID, RACE } from './data'
import { PRERACE_GRID, PRERACE_MODEL, PRERACE_PLANS } from './prerace'
import { STATUS, STATUS_ORDER, fieldNote } from './status'
import { DEFAULT_SEED, evolve } from './tyres'
import { useField } from './useField'
import { Kpi } from './ui'
import type { TrackStatus } from './types'

type View = 'race' | 'forecast' | 'prerace'

/**
 * Desde dónde arranca la carrera animada.
 *
 *   `snapshot`  la foto medida de la vuelta 30: cada auto con su goma, su edad
 *               y sus intervalos reales, y las paradas que faltan sorteadas de
 *               las distribuciones medidas.
 *   `start`     la parrilla de largada de la clasificación, con **cada auto
 *               corriendo el plan que le dio el algoritmo genético**.
 */
type Origin = 'snapshot' | 'start'

const TABS: { id: View; label: string }[] = [
  { id: 'prerace', label: 'Pre-carrera' },
  { id: 'race', label: 'Panel de carrera' },
  { id: 'forecast', label: 'Pronóstico' },
]

const VIEWS = new Set<string>(TABS.map((t) => t.id))

/**
 * Los autos que se dibujan en el mapa: **todos los que están en pista**.
 *
 * Antes eran sólo los ocho primeros, y eso rompía la parrilla: ALO largó P18,
 * así que su lugar en la grilla quedaba a diecisiete puestos del resto y se
 * veía descolgado. Con la parrilla completa los huecos desaparecen.
 *
 * Van los veintidós: quién está en pista depende de la vuelta que se mire, y
 * eso lo resuelve el mapa. En la largada VER todavía corría.
 *
 * Se fija fuera del componente para que la identidad del arreglo no cambie en
 * cada render y reinicie la simulación.
 */
const FIELD_CARS = GRID

export default function App() {
  // El hash permite abrir una vista directo (y sacarle captura sin interactuar).
  const hash = window.location.hash.slice(1)
  const initial: View = VIEWS.has(hash) ? (hash as View) : 'prerace'
  const [view, setView] = useState<View>(initial)
  const [status, setStatus] = useState<TrackStatus>('GREEN')
  const [origin, setOrigin] = useState<Origin>('snapshot')
  const [lap, setLap] = useState(RACE.currentLap)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[1])
  const [focal, setFocal] = useState('NOR')
  const [seed, setSeed] = useState(DEFAULT_SEED)

  const spec = STATUS[status]
  const fromLap = origin === 'start' ? 1 : RACE.currentLap

  const [track, setTrack] = useState<number[]>([])

  /**
   * Cierra una vuelta: adelanta el reloj y anota en qué puesto la terminó el
   * auto focal.
   *
   * Las dos cosas van juntas porque son el mismo evento —la cabeza del pelotón
   * cruzando la meta—, y porque así la trayectoria tiene exactamente un punto
   * por vuelta en vez de uno por publicación de la torre.
   */
  const closeLap = useCallback((atLap: number, place: number) => {
    if (place > 0) {
      setTrack((current) => {
        const next = current.slice()
        next[atLap] = place
        return next
      })
    }
    setLap((current) => {
      if (current >= RACE.totalLaps) {
        setPlaying(false)
        return current
      }
      return current + 1
    })
  }, [])

  // La goma envejece con la carrera, y no lo hace igual para todos: cada tanda
  // tiene su propio ritmo de caída sorteado, y cada vuelta su propio ruido. Sin
  // esto dos autos con la misma goma andaban exactamente igual para siempre.
  //
  // Desde la largada cambian dos cosas: el plan de cada auto **no se sortea**
  // —es el que emitió el algoritmo— y el desgaste sale de los cortes del propio
  // export, que son de 2026 y no de todas las temporadas (ADR-009).
  const { cars, paceNoise, progressLost, plans } = useMemo(
    () =>
      origin === 'start'
        ? evolve(PRERACE_GRID, lap, 1, seed, { model: PRERACE_MODEL, plans: PRERACE_PLANS })
        : evolve(FIELD_CARS, lap, RACE.currentLap, seed),
    [lap, origin, seed],
  )

  // El pelotón vive en useField: separación, ritmo y posición se interpolan
  // cuadro a cuadro, así que cambiar de estado es una maniobra y no un salto.
  const { field, timing } = useField(cars, status, playing, speed.msPerLap, lap, paceNoise, progressLost)

  const focalIndex = cars.findIndex((c) => c.code === focal)

  /*
   * La vuelta se cierra cuando la cabeza del pelotón cruza la meta. Ahí también
   * queda anotado el puesto del auto focal: la trayectoria es una **medición de
   * la simulación**, no una proyección, y se reinicia desde los botones que
   * cambian de carrera, que es donde la vieja deja de corresponder.
   */
  const crossed = useRef(field.positions[0] ?? 0)
  useEffect(() => {
    const head = field.positions[0] ?? 0
    if (crossed.current > 0.8 && head < 0.2) {
      closeLap(lap, focalIndex >= 0 ? timing.order.indexOf(focalIndex) + 1 : 0)
    }
    crossed.current = head
  }, [field.positions, timing, focalIndex, lap, closeLap])

  const togglePlay = useCallback(() => setPlaying((current) => !current), [])

  /** Arranca la carrera desde donde diga `next`, y deja el reloj en su vuelta. */
  const startFrom = useCallback((next: Origin, play: boolean) => {
    setOrigin(next)
    setLap(next === 'start' ? 1 : RACE.currentLap)
    setPlaying(play)
    setTrack([])
  }, [])

  /** Otra semilla, mismo plan: la carrera vuelve a largar y sale distinta. */
  const redraw = useCallback(() => {
    setSeed((current) => current + 1)
    setOrigin('start')
    setLap(1)
    setPlaying(true)
    setTrack([])
  }, [])

  /** Cambiar de piloto cambia de quién es la trayectoria que se está anotando. */
  const chooseFocal = useCallback((code: string) => {
    setFocal(code)
    setTrack([])
  }, [])

  const openView = useCallback((next: View) => {
    setView(next)
    window.location.hash = next
  }, [])

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
              onClick={() => openView(t.id)}
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
          note={`quedan ${RACE.totalLaps - lap} · ${
            origin === 'start' ? 'desde la largada' : 'desde la foto V30'
          }`}
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
            homeLap={fromLap}
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
        <RaceView
          scenarioLap={lap}
          status={status}
          field={field}
          cars={cars}
          timing={timing}
          focal={focal}
          plans={origin === 'start' ? plans : null}
          /*
           * Los autos paran en los dos orígenes, así que el recuadro de boxes y
           * la ventana necesitan las paradas del sorteo siempre. `plans` sigue
           * siendo sólo lo que la torre puede llamar «plan».
           */
          drawnPlans={plans}
        />
      ) : view === 'forecast' ? (
        <ForecastView />
      ) : (
        <PreRaceView
          focal={focal}
          onFocal={chooseFocal}
          lap={lap}
          running={origin === 'start'}
          playing={playing}
          seed={seed}
          track={track}
          onStart={() => {
            startFrom('start', true)
            openView('prerace')
          }}
          onSnapshot={() => startFrom('snapshot', false)}
          onRedraw={redraw}
          onWatch={() => openView('race')}
        />
      )}
    </div>
  )
}
