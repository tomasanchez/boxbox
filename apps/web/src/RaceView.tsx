/**
 * Panel de carrera: el mapa a la izquierda y la parrilla a la derecha.
 *
 * Los insights van superpuestos sobre el mapa y pueden minimizarse, porque
 * tapan justamente la zona donde corren los autos. Son tres, y contestan cosas
 * distintas: el **duelo de estrategia** dice si conviene parar ahora, el
 * **pronóstico de batalla** dice si lo va a alcanzar, y el **plan** dice a
 * cuántas paradas va la carrera.
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
import { IN_RANGE_S, battleKey, liveBattles, noBattleReason } from './battle'
import { RACE } from './data'
import { pickBattle } from './forecast'
import { fmt } from './format'
import { PLANS } from './plans'
import { preraceCar, recommendedPlan } from './prerace'
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
} as const

export function RaceView({
  scenarioLap,
  status,
  field,
  cars,
  timing,
  focal,
  plans,
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
}) {
  const track = TRACKS[RACE.trackKey]
  const duels = useMemo(
    () => liveBattles(cars, timing, scenarioLap),
    [cars, timing, scenarioLap],
  )

  // La selección se guarda por par de pilotos, no por objeto: el duelo se
  // recalcula varias veces por segundo y el usuario no debería perder el que
  // estaba mirando. Si ese par deja de estar en rango, manda el más cerrado.
  const [pick, setPick] = useState<string | null>(null)
  const duel = duels.find((b) => battleKey(b) === pick) ?? duels[0] ?? null

  const reason = duel ? null : noBattleReason(cars, timing, scenarioLap)

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
  const insightPlan = plans !== null ? recommendedPlan(preraceCar(insightDriver)) : undefined

  const [battleOpen, setBattleOpen] = useState(true)
  const [forecastOpen, setForecastOpen] = useState(true)
  const [insightOpen, setInsightOpen] = useState(true)

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
          <div className="overlay overlay--top">
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
               * con un par inventado. Cuál de las dos condiciones falló importa:
               * «nadie va a parar» y «nadie alcanza» son carreras distintas.
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

          <InsightOverlay
            lap={scenarioLap}
            driver={insightDriver}
            plan={insightPlan}
            open={insightOpen}
            onToggle={() => setInsightOpen((v) => !v)}
          />
        </CircuitMap>
      </Panel>
    </div>
  )
}
