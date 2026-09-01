/**
 * Panel de carrera: el mapa a la izquierda y la parrilla a la derecha.
 *
 * Los dos insights —el duelo de estrategia y el plan de neumáticos— van
 * superpuestos sobre el mapa y pueden minimizarse, porque tapan justamente la
 * zona donde corren los autos.
 *
 * Los duelos **no están escritos a mano**: salen del orden en pista que va
 * marcando la simulación, así que aparecen y se resuelven solos a medida que
 * corre la carrera.
 */

import { useMemo, useState } from 'react'
import { BattleStrip } from './BattleStrip'
import { CircuitMap } from './CircuitMap'
import { GridPanel } from './GridPanel'
import { InsightOverlay } from './InsightCard'
import { IN_RANGE_S, battleKey, liveBattles } from './battle'
import { RACE } from './data'
import { fmt } from './format'
import { TRACKS } from './tracks'
import type { DriverState, TrackStatus } from './types'
import type { FieldState, Timing } from './useField'
import { Panel } from './ui'

export function RaceView({
  scenarioLap,
  status,
  field,
  cars,
  timing,
}: {
  scenarioLap: number
  status: TrackStatus
  field: FieldState
  /** Cronometraje, a menor frecuencia que la animación. */
  timing: Timing
  /** Los mismos autos que alimentan la simulación. */
  cars: DriverState[]
}) {
  const track = TRACKS[RACE.trackKey]
  const duels = useMemo(() => liveBattles(cars, timing), [cars, timing])

  // La selección se guarda por par de pilotos, no por objeto: el duelo se
  // recalcula varias veces por segundo y el usuario no debería perder el que
  // estaba mirando. Si ese par deja de estar en rango, manda el más cerrado.
  const [pick, setPick] = useState<string | null>(null)
  const duel = duels.find((b) => battleKey(b) === pick) ?? duels[0] ?? null

  const [battleOpen, setBattleOpen] = useState(true)
  const [insightOpen, setInsightOpen] = useState(true)

  return (
    <div className="view view--race">
      <GridPanel lap={scenarioLap} cars={cars} timing={timing} />

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
               * Sin nadie en rango de undercut no hay duelo que mostrar. Se deja
               * el hueco ocupado con el motivo en vez de inventar un par: con el
               * pelotón formado los intervalos son el largo de los cajones.
               */
              <div className="battle battle--idle">
                <div className="battle__head">
                  <span className="battle__title">Duelo de estrategia</span>
                  <span className="battle__sub">
                    {timing.formation
                      ? 'pelotón formado'
                      : `nadie a menos de ${fmt(IN_RANGE_S, 1)} s`}
                  </span>
                </div>
              </div>
            )}
          </div>

          <InsightOverlay
            lap={scenarioLap}
            open={insightOpen}
            onToggle={() => setInsightOpen((v) => !v)}
          />
        </CircuitMap>
      </Panel>
    </div>
  )
}
