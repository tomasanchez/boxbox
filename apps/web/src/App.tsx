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
 *   `started` si la carrera ya largó. Siempre arranca en la parrilla: la foto
 *             medida de la vuelta 30 se sacó, porque el producto es la
 *             estrategia PRE-carrera y empezar a mitad de camino contaba otra.
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
import { RACE } from './data'
import { fmt, pct } from './format'
import {
  PRERACE_MODEL,
  type RivalsMode,
  compoundsUsed,
  gridOf,
  plansOf,
  preraceCar,
  safetyCarAhead,
} from './prerace'
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

const TABS: { id: View; label: string }[] = [
  { id: 'prerace', label: 'Pre-carrera' },
  { id: 'race', label: 'Panel de carrera' },
  { id: 'forecast', label: 'Pronóstico' },
]

const VIEWS = new Set<string>(TABS.map((t) => t.id))


export default function App() {
  // El hash permite abrir una vista directo (y sacarle captura sin interactuar).
  const hash = window.location.hash.slice(1)
  const initial: View = VIEWS.has(hash) ? (hash as View) : 'prerace'
  const [view, setView] = useState<View>(initial)
  const [status, setStatus] = useState<TrackStatus>('GREEN')
  /*
   * Desde qué vuelta ondea esa bandera. La reacción del campo se decide UNA vez,
   * en la vuelta en que se neutralizó, y no lap a lap: así mover el reloj para
   * adelante y para atrás no cambia quién entró a boxes, que es lo que hace que
   * la carrera siga siendo la misma carrera mientras se la revisa.
   */
  const [statusSince, setStatusSince] = useState<number | null>(null)
  /*
   * Si la carrera ya largó. Antes esto era un `origin` de dos valores: la foto
   * medida de la vuelta 30, o desde la largada. La foto se fue —el producto es
   * la estrategia PRE-carrera y arrancar a mitad de camino contaba otra cosa— y
   * lo único que quedaba de ese conmutador era distinguir "todavía no largó" de
   * "está corriendo", que es lo que este booleano dice sin rodeos.
   */
  const [started, setStarted] = useState(false)
  const [lap, setLap] = useState(1)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[1])
  const [focal, setFocal] = useState('NOR')
  const [seed, setSeed] = useState(DEFAULT_SEED)
  /*
   * Cómo se portan los veintiún autos que no son el elegido. Arranca en `fixed`
   * porque ésa es la corrida de la que salen todas las cifras publicadas, y el
   * interruptor está para poder ver la otra al lado, no para reemplazarla
   * (ADR-016).
   */
  const [rivals, setRivals] = useState<RivalsMode>('fixed')

  const spec = STATUS[status]
  const fromLap = 1

  /*
   * Qué le cambia al piloto elegido pasar de una búsqueda a la otra.
   *
   * Sin esto el interruptor cambiaba los datos en silencio: había que
   * memorizar el plan, conmutar y comparar de memoria, y entonces no se
   * entendía qué compraba. Mostrar el plan del OTRO modo al lado convierte un
   * interruptor mudo en una comparación, que es lo único que este interruptor
   * vino a ofrecer (ADR-016).
   */
  const otherMode: RivalsMode = rivals === 'fixed' ? 'reactive' : 'fixed'
  const planHere = preraceCar(focal, rivals).plan
  const planThere = preraceCar(focal, otherMode).plan

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
      evolve(gridOf(rivals), lap, 1, seed, {
        model: PRERACE_MODEL,
        plans: plansOf(rivals),
        status,
        statusSince,
      }),
    [lap, seed, rivals, status, statusSince],
  )

  // El pelotón vive en useField: separación, ritmo y posición se interpolan
  // cuadro a cuadro, así que cambiar de estado es una maniobra y no un salto.
  const { field, timing } = useField(cars, status, playing, speed.msPerLap, lap, paceNoise, progressLost)

  const focalIndex = cars.findIndex((c) => c.code === focal)
  /*
   * Lo que le costó al auto elegido su última parada, contra dos varas.
   *
   * La tarjeta decía antes lo que cuesta parar «en general» bajo la bandera que
   * ondea —dos puestos en verde, cero bajo safety car— y eso no cambiaba nunca
   * ni miraba al auto. Después de que el auto para, lo que interesa es qué le
   * salió A ÉL: contra la mediana medida de la distribución de la que se sorteó,
   * y contra lo que pagaron los demás en esta misma carrera.
   */
  const mine = focalIndex >= 0 ? (plans[focalIndex] ?? []) : []
  const doneMine = mine.filter((stop) => stop.lap <= lap)
  const lastStop = doneMine[doneMine.length - 1]
  const cuts = PRERACE_MODEL.pitLoss
  const measuredMedian = cuts[(cuts.length - 1) / 2]
  const doneAll = plans.flatMap((plan) => plan.filter((stop) => stop.lap <= lap))
  const raceAverage = doneAll.length
    ? doneAll.reduce((total, stop) => total + stop.lossS, 0) / doneAll.length
    : null

  const scAhead = safetyCarAhead(lap, RACE.totalLaps)
  const used = compoundsUsed(preraceCar(focal, rivals).start_compound, doneMine)


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
  const startRace = useCallback((play: boolean) => {
    setStarted(true)
    setLap(1)
    setPlaying(play)
    setTrack([])
  }, [])

  /** Otra semilla, mismo plan: la carrera vuelve a largar y sale distinta. */
  const redraw = useCallback(() => {
    setSeed((current) => current + 1)
    setStarted(true)
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
              onClick={() => {
                setStatus(id)
                // Verde no es una neutralización: apaga la reacción en vez de
                // fecharla. Y volver a tocar la misma bandera no la re-fecha,
                // porque sigue siendo el mismo período.
                setStatusSince(id === 'GREEN' || id === 'YELLOW' ? null : (was) =>
                  status === id ? was : lap,
                )
              }}
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
            started ? 'desde la largada' : 'todavía en la parrilla'
          }`}
        />
        {lastStop ? (
          <Kpi
            label={`Última parada de ${focal}`}
            value={`${fmt(lastStop.lossS, 1)} s`}
            note={`V${lastStop.lap} · ${fmt(lastStop.lossS - measuredMedian, 1, true)} s contra la mediana medida${
              raceAverage !== null
                ? ` · ${fmt(lastStop.lossS - raceAverage, 1, true)} contra el promedio de la carrera`
                : ''
            }`}
            tone={lastStop.lossS <= measuredMedian ? 'good' : 'alert'}
          />
        ) : (
          <Kpi
            label="Costo de parar"
            value={`${spec.cost} pos`}
            note={`${spec.costNote} · ${focal} todavía no paró`}
            tone={spec.cost === '0,0' ? 'good' : 'alert'}
          />
        )}
        <Kpi
          label="Safety car por delante"
          value={pct(scAhead)}
          note={`al menos uno entre la V${lap} y el final · sobre 103 carreras`}
          tone={scAhead >= 0.4 ? 'alert' : undefined}
        />
        <Kpi
          label="B6.3.8"
          value={used.length >= 2 ? 'cumplido' : `falta 1`}
          note={
            used.length >= 2
              ? `${focal} usó ${used.length} compuestos secos`
              : `${focal} lleva sólo ${used[0]?.toLowerCase() ?? '—'}: le falta un segundo seco`
          }
          tone={used.length >= 2 ? 'good' : 'alert'}
        />
        {/*
          * OJO CON QUE DICE ESTE ROTULO. El interruptor elige de cual de las dos
          * BUSQUEDAS salieron los planes que el campo corre, y nada mas. La
          * animacion no reacciona a las banderas: `evolve` en tyres.ts no
          * conoce el estado de pista, y el selector de bandera de arriba pinta
          * la barra de estado sin tocar la simulacion.
          *
          * Una version anterior rotulaba los botones "plan fijo / reaccionan" y
          * la nota decia que tomaban las ventanas baratas y cubrian tu parada.
          * Eso es cierto de la busqueda en Python y falso de lo que se ve en
          * pantalla, que es justo el tipo de cosa que este proyecto cuenta como
          * defecto. Hasta que la politica de reaccion este portada a tyres.ts,
          * el rotulo tiene que decir lo que realmente hace.
          */}
        <div className="kpi">
          <span className="kpi__label">Planes de</span>
          <div className="rivals" role="group" aria-label="Comportamiento de los rivales">
            {(['fixed', 'reactive'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`rivals__pick${rivals === mode ? ' rivals__pick--on' : ''}`}
                aria-pressed={rivals === mode}
                onClick={() => setRivals(mode)}
                title={
                  mode === 'fixed'
                    ? 'Planes de la búsqueda con rivales de plan fijo. Es de donde salen las cifras publicadas.'
                    : 'Planes de la búsqueda con rivales que reaccionan a las banderas y a tu parada. Cambia el plan de 9 de los 22 autos; la animación en sí no reacciona todavía.'
                }
              >
                {mode === 'fixed' ? 'búsq. fija' : 'búsq. reactiva'}
              </button>
            ))}
          </div>
          <span className="kpi__note">
            {planHere === planThere ? (
              <>
                el plan de <strong>{focal}</strong> no cambia entre las dos
              </>
            ) : (
              <>
                con rivales {otherMode === 'fixed' ? 'de plan fijo' : 'reactivos'},{' '}
                <strong>{focal}</strong> haría <span className="num">{planThere}</span>
              </>
            )}
          </span>
        </div>

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
          plans={plans}
          /*
           * Los autos paran en los dos orígenes, así que el recuadro de boxes y
           * la ventana necesitan las paradas del sorteo siempre. `plans` sigue
           * siendo sólo lo que la torre puede llamar «plan».
           */
          drawnPlans={plans}
          rivals={rivals}
        />
      ) : view === 'forecast' ? (
        <ForecastView />
      ) : (
        <PreRaceView
          focal={focal}
          onFocal={chooseFocal}
          lap={lap}
          running={started}
          playing={playing}
          seed={seed}
          track={track}
          onStart={() => {
            startRace(true)
            openView('prerace')
          }}
          onRedraw={redraw}
          onWatch={() => openView('race')}
          rivals={rivals}
        />
      )}
    </div>
  )
}
