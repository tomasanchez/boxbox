/**
 * Panel de carrera: el mapa a la izquierda y la parrilla a la derecha.
 *
 * Los dos insights —el duelo de estrategia y el plan de neumáticos— van
 * superpuestos sobre el mapa y pueden minimizarse, porque tapan justamente la
 * zona donde corren los autos.
 */

import { useState } from 'react'
import { BattleStrip } from './BattleStrip'
import { CircuitMap } from './CircuitMap'
import { GridPanel } from './GridPanel'
import { InsightOverlay } from './InsightCard'
import { BATTLE, BATTLE_ALT, RACE } from './data'
import { TRACKS } from './tracks'
import type { DriverState, TrackStatus } from './types'
import type { FieldState } from './useField'
import { Panel } from './ui'

export function RaceView({
  scenarioLap,
  status,
  field,
  cars,
}: {
  scenarioLap: number
  status: TrackStatus
  field: FieldState
  /** Los mismos autos que alimentan la simulación. */
  cars: DriverState[]
}) {
  const track = TRACKS[RACE.trackKey]
  const duels = [BATTLE, BATTLE_ALT]

  const [duel, setDuel] = useState(BATTLE)
  const [battleOpen, setBattleOpen] = useState(true)
  const [insightOpen, setInsightOpen] = useState(true)

  return (
    <div className="view view--race">
      <GridPanel lap={scenarioLap} />

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
            <BattleStrip
              battle={duel}
              others={duels.filter((b) => b !== duel)}
              onPick={setDuel}
              open={battleOpen}
              onToggle={() => setBattleOpen((v) => !v)}
            />
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
