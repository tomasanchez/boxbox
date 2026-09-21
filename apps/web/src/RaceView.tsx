/**
 * Panel de carrera: el mapa a la izquierda y la parrilla a la derecha.
 *
 * Los insights van superpuestos sobre el mapa y pueden minimizarse, porque
 * tapan justamente la zona donde corren los autos. Son cinco, y contestan cosas
 * distintas — son las cinco gráficas de estrategia de la transmisión:
 *
 *   duelo de estrategia    si el de atrás para ahora, ¿sale adelante?
 *   pronóstico de batalla  ¿lo va a alcanzar, y en cuántas vueltas?
 *   plan recomendado       ¿a cuántas paradas va la carrera?
 *   ventana de boxes       ¿cuándo PODRÍA parar este auto?
 *   amenaza de undercut    el mismo duelo, desde el que va adelante.
 *
 * Las dos últimas son nuevas y no traen modelo nuevo: la ventana ya la
 * calculaba `pit_window()` y entraba como `DriverState.pitWindow`, y la amenaza
 * es `solveBattle` leído desde el otro lado. Lo que faltaba era dónde leerlas.
 *
 * Aparte va el recuadro **EN BOXES**, que no es una de las cinco: aparece sólo
 * mientras hay un auto efectivamente detenido en el carril.
 *
 * Los duelos **no están escritos a mano**: salen del orden en pista que va
 * marcando la simulación, así que aparecen y se resuelven solos a medida que
 * corre la carrera. Y no se muestran siempre — sólo cuando el perseguidor está
 * en ventana de parada, que es cuando el undercut es una jugada disponible y no
 * una cuenta de café.
 */

import { useMemo, useState } from 'react'
import { BattleForecastCard } from './BattleForecast'
import { BattleStrip } from './BattleStrip'
import { CircuitMap } from './CircuitMap'
import { GridPanel } from './GridPanel'
import { InsightOverlay } from './InsightCard'
import { InPitBox } from './InPitBox'
import { PitWindowCard } from './PitWindowCard'
import { UndercutThreatCard } from './UndercutThreat'
import { IN_RANGE_S, battleKey, liveBattles, noBattleReason, undercutThreat } from './battle'
import { RACE } from './data'
import { pickBattle } from './forecast'
import { fmt } from './format'
import { inPitNow } from './pitlane'
import { openCount } from './pitwindow'
import { PLANS } from './plans'
import { type RivalsMode, preraceCar, recommendedPlan } from './prerace'
import { TRACKS } from './tracks'
import type { PitStop } from './tyres'
import type { DriverState, TrackStatus } from './types'
import type { FieldState, Timing } from './useField'
import { Panel } from './ui'

/** Por qué no hay duelo, dicho en la tarjeta. */
const IDLE_TEXT = {
  formation: 'pelotón formado',
  'no-window': 'nadie en ventana en los puntos',
  'no-one-close': `nadie a menos de ${fmt(IN_RANGE_S, 1)} s en los puntos`,
  'focal-clear': 'sin pelea propia · hay otros duelos abajo',
} as const

export function RaceView({
  scenarioLap,
  status,
  field,
  cars,
  timing,
  focal,
  plans,
  drawnPlans,
  rivals,
}: {
  scenarioLap: number
  status: TrackStatus
  field: FieldState
  /** Cronometraje, a menor frecuencia que la animación. */
  timing: Timing
  /** Los mismos autos que alimentan la simulación. */
  cars: DriverState[]
  /** El piloto elegido en la vista pre-carrera: se destaca acá también (ADR-007). */
  focal: string
  /**
   * Plan de paradas de cada auto, cuando la carrera corre desde la largada.
   * `null` en la foto de la vuelta 30, donde lo que hay es una **ventana
   * proyectada** y no un plan: son cosas distintas y la torre no las mezcla.
   */
  plans: PitStop[][] | null
  /**
   * Las paradas sorteadas de **este** sorteo, siempre.
   *
   * Va aparte de `plans` a propósito. `plans` es lo que la torre puede
   * presentar como «lo que el auto va a hacer», y por eso es `null` en la foto
   * de la vuelta 30, donde lo que hay es una ventana proyectada. Pero los autos
   * paran igual en los dos orígenes, así que el recuadro de boxes y la tarjeta
   * de ventana necesitan las paradas del sorteo en curso pasen lo que pasen.
   *
   * Mezclarlos en una sola prop volvería a juntar ventana y plan, que es
   * justamente lo que la vista se cuidó de separar.
   */
  drawnPlans: PitStop[][]
  /** Qué corrida se está mirando: rivales con plan fijo, o reaccionando. */
  rivals: RivalsMode
}) {
  const track = TRACKS[RACE.trackKey]
  const duels = useMemo(
    () => liveBattles(cars, timing, scenarioLap, focal),
    [cars, timing, scenarioLap, focal],
  )

  // La selección se guarda por par de pilotos, no por objeto: el duelo se
  // recalcula varias veces por segundo y el usuario no debería perder el que
  // estaba mirando.
  const [pick, setPick] = useState<string | null>(null)

  /*
   * Por defecto, el duelo del PILOTO ELEGIDO. Antes caía en `duels[0]`, que es
   * el más cerrado del campo, así que la tarjeta saltaba de auto en auto y podía
   * estar hablando de dos McLaren mientras el usuario miraba a otro. Es el mismo
   * principio que ADR-007 ya había fijado para la tarjeta de undercut —acompaña
   * al piloto elegido aunque no esté pasando nada— y tenerlo en una tarjeta y no
   * en la de al lado era contradecirse en la misma pantalla.
   *
   * Una elección explícita sigue mandando: si el usuario tocó otro duelo, ése es
   * el que quiere ver.
   */
  const ofFocal = duels.find((b) => b.chaser === focal || b.leader === focal) ?? null
  const duel = duels.find((b) => battleKey(b) === pick) ?? ofFocal

  // Y si no está en pelea se dice, en vez de mostrar la de otro: una tarjeta que
  // salta no se puede seguir, y el usuario no tendría cómo saber de quién habla.
  const reason = duel
    ? null
    : duels.length > 0
      ? ('focal-clear' as const)
      : noBattleReason(cars, timing, scenarioLap)

  // El pronóstico de batalla no depende de la ventana de parada: pregunta si
  // lo alcanza, no si conviene parar, y eso se puede preguntar siempre.
  const forecast = useMemo(
    () =>
      pickBattle(
        cars,
        timing,
        RACE.totalLaps - scenarioLap,
        RACE.circuit,
        duel ? battleKey(duel) : null,
      ),
    [cars, timing, scenarioLap, duel],
  )

  /*
   * El plan que se muestra es el del **auto focal** (ADR-007): el selector de
   * la vista pre-carrera manda también acá. La foto de la vuelta 30 tiene dos
   * autos sin plan cargado —los que abandonaron—, y ahí se cae a la lógica
   * vieja: el perseguidor del duelo, o el líder si no hay duelo.
   *
   * Corriendo desde la largada el plan sale del export pre-carrera, que es el
   * que la carrera está ejecutando. Mostrar el de la vuelta 30 mientras el auto
   * corre otro sería la tarjeta contradiciendo al mapa.
   */
  const hasPlan = plans !== null || PLANS[focal] !== undefined
  const insightDriver = hasPlan
    ? focal
    : (duel?.chaser ?? cars[timing.order[0]]?.code ?? 'ANT')
  const insightPlan = plans !== null ? recommendedPlan(preraceCar(insightDriver, rivals)) : undefined

  const [battleOpen, setBattleOpen] = useState(true)
  const [forecastOpen, setForecastOpen] = useState(true)
  const [insightOpen, setInsightOpen] = useState(true)
  const [windowOpen, setWindowOpen] = useState(true)
  const [threatOpen, setThreatOpen] = useState(true)

  /*
   * El auto focal manda en las dos tarjetas nuevas, como en el resto de la
   * vista (ADR-007): la ventana es la suya y la amenaza es la que él corre.
   */
  const focalIndex = cars.findIndex((c) => c.code === focal)
  const focalCar = focalIndex >= 0 ? cars[focalIndex] : undefined

  /** Las paradas que el auto focal ya hizo en este sorteo. */
  const focalStops = useMemo(
    () => (focalIndex >= 0 ? (drawnPlans[focalIndex] ?? []) : []).filter((s) => s.lap <= scenarioLap),
    [drawnPlans, focalIndex, scenarioLap],
  )

  const inWindow = useMemo(() => openCount(cars, scenarioLap), [cars, scenarioLap])
  const running = useMemo(
    () => cars.filter((c) => c.retiredOnLap == null || scenarioLap < c.retiredOnLap).length,
    [cars, scenarioLap],
  )

  /*
   * ¿Este origen trae ventanas proyectadas?
   *
   * La foto de la vuelta 30 sí: cada auto llega con la salida de `pit_window()`.
   * Desde la largada no: `PRERACE_GRID` pone `pitWindow: null` en los veintidós
   * porque el export pre-carrera trae el **plan** del algoritmo y no la ventana.
   *
   * Es justamente la distinción que la torre ya hacía —muestra «Vent.» o
   * «Plan», nunca las dos— y por eso se deriva de la misma prop: donde hay plan
   * cargado, no hay ventana proyectada.
   *
   * Sin esto las dos tarjetas explicaban ese `null` como «la goma está plana» y
   * «no va a parar», que en ese origen son afirmaciones que nadie midió — y la
   * segunda además es falsa, porque el auto tiene plan y para.
   *
   * **Ya no hace falta distinguir por origen**: el export pre-carrera ahora trae
   * la ventana proyectada de cada auto, y un `null` significa lo mismo en los dos
   * lados —no hay cruce proyectable— así que la bandera se decide por el dato y
   * no por de dónde vino. Se deja porque sigue siendo verdad que un origen sin
   * ventanas existiría, y explicarlo mal fue el error que esto vino a atajar.
   */
  const windowsProjected = cars.some((car) => car.pitWindow !== null)

  const threat = useMemo(
    () => undercutThreat(cars, timing, scenarioLap, focalIndex, windowsProjected),
    [cars, timing, scenarioLap, focalIndex, windowsProjected],
  )

  /*
   * Quién está detenido en el carril ahora mismo. Sale de `timing.inPit`, que
   * es el mismo estado con el que la torre escribe BOXES: si las dos cosas
   * salieran de cuentas distintas podrían contradecirse en pantalla.
   */
  const inPit = useMemo(
    () => inPitNow(cars, timing.inPit, drawnPlans, scenarioLap),
    [cars, timing.inPit, drawnPlans, scenarioLap],
  )

  return (
    <div className="view view--race">
      <GridPanel lap={scenarioLap} cars={cars} timing={timing} focal={focal} plans={plans} />

      <Panel
        title={`Trazado · ${track.name}`}
        note={`${track.lengthM.toLocaleString('es-AR')} m · geometría real (OSM · f1-circuits)`}
        fill
      >
        <CircuitMap
          track={track}
          drivers={cars}
          status={status}
          field={field}
          lap={scenarioLap}
          focal={focal}
        >
          {/*
           * Todo lo anclado arriba vive en el mismo contenedor y en columna, no
           * en dos capas absolutas: así la fila de abajo se acomoda sola cuando
           * el duelo se minimiza, en vez de quedar clavada a un alto supuesto.
           */}
          <div className="overlay overlay--top">
            <div className="overlay__row">
              {duel ? (
                <BattleStrip
                  battle={duel}
                  others={duels.filter((b) => battleKey(b) !== battleKey(duel))}
                  onPick={(b) => setPick(battleKey(b))}
                  open={battleOpen}
                  onToggle={() => setBattleOpen((v) => !v)}
                />
              ) : (
                /*
                 * Sin duelo se deja el hueco ocupado con el motivo, no vacío ni
                 * con un par inventado. Cuál de las dos condiciones falló
                 * importa: «nadie va a parar» y «nadie alcanza» son carreras
                 * distintas.
                 */
                <div className="battle battle--idle">
                  <div className="battle__head">
                    <span className="battle__title">Duelo de estrategia</span>
                    <span className="battle__sub">{IDLE_TEXT[reason ?? 'no-one-close']}</span>
                  </div>
                </div>
              )}

              {forecast ? (
                <BattleForecastCard
                  forecast={forecast}
                  open={forecastOpen}
                  onToggle={() => setForecastOpen((v) => !v)}
                />
              ) : null}
            </div>

            {/*
             * Columna izquierda: las dos tarjetas que hablan del auto elegido y
             * no del par que la carrera ofrezca en ese momento. Van juntas
             * porque son las dos caras de la misma decisión — cuándo podría
             * parar él, y qué pasa si para el de atrás.
             */}
            <div className="overlay__rail">
              <PitWindowCard
                car={focalCar}
                lap={scenarioLap}
                openNow={inWindow}
                windowsProjected={windowsProjected}
                running={running}
                stopsMade={focalStops.length}
                lastStopLap={focalStops.length > 0 ? focalStops[focalStops.length - 1].lap : null}
                open={windowOpen}
                onToggle={() => setWindowOpen((v) => !v)}
              />

              <UndercutThreatCard
                threat={threat}
                driver={focal}
                open={threatOpen}
                onToggle={() => setThreatOpen((v) => !v)}
              />
            </div>
          </div>

          <InsightOverlay
            lap={scenarioLap}
            driver={insightDriver}
            plan={insightPlan}
            open={insightOpen}
            onToggle={() => setInsightOpen((v) => !v)}
            /* Sólo hay algo que mostrar mientras haya un auto en el carril. */
            aside={<InPitBox cars={inPit} />}
          />
        </CircuitMap>
      </Panel>
    </div>
  )
}
