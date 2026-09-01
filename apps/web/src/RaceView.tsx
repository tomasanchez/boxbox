/** Panel de carrera: parrilla, trazado, duelo y ventanas de boxes. */

import { useState } from 'react'
import { BattleStrip } from './BattleStrip'
import { CircuitMap } from './CircuitMap'
import { InsightOverlay } from './InsightCard'
import { BATTLE, BATTLE_ALT, GRID, RACE } from './data'
import { TRACKS } from './tracks'
import { fmt } from './format'
import type { DriverState } from './types'
import { Panel, Tyre } from './ui'

function windowText(driver: DriverState): string {
  if (!driver.pitWindow) return 'sin proyectar'
  return `${driver.pitWindow.opensLap}–${driver.pitWindow.closesLap}`
}

export function RaceView({
  scenarioLap,
  lapFraction,
}: {
  scenarioLap: number
  lapFraction: number
}) {
  const { totalLaps } = RACE
  const track = TRACKS[RACE.trackKey]
  const duels = [BATTLE, BATTLE_ALT]
  const [duel, setDuel] = useState(BATTLE)
  const nowPct = (scenarioLap / totalLaps) * 100

  return (
    <div className="view view--race">
      {/* ------------------------------------------------------------ parrilla */}
      <Panel title="Parrilla" note={`V${scenarioLap} / ${totalLaps}`}>
        <div className="grid-table">
          <div className="grid-table__h">P</div>
          <div className="grid-table__h">Piloto</div>
          <div className="grid-table__h" title="Compuesto">G</div>
          <div className="grid-table__h" title="Vueltas con esa goma">V</div>
          <div className="grid-table__h" title="Segundos por vuelta">Deg</div>
          <div className="grid-table__h">Ventana</div>

          {GRID.map((d) => (
            <div className="grid-row" key={d.code}>
              <div className="grid-row__pos num">{d.position}</div>
              <div className="grid-row__code">
                <span className="team-bar" style={{ background: d.teamColor }} />
                {d.code}
              </div>
              <div>
                <Tyre compound={d.compound} />
              </div>
              <div className="grid-row__pos num">{d.tyreAge}</div>
              <div
                className={`num grid-row__deg--${d.degradationS < 0 ? 'gaining' : 'losing'}`}
              >
                {fmt(d.degradationS, 2, true)}
              </div>
              <div
                className={`grid-row__win num${d.pitWindow ? '' : ' grid-row__win--none'}`}
              >
                {windowText(d)}
              </div>
            </div>
          ))}
        </div>
        <p className="footnote">
          <strong>Deg</strong> en segundos por vuelta. En verde, los que todavía{' '}
          <strong>mejoran</strong> porque queman combustible más rápido de lo que gastan la goma.
        </p>
      </Panel>

      {/* ------------------------------------------------- trazado + plan modal */}
      <div className="stack">
        <Panel
          title={`Trazado · ${track.name}`}
          note={`${track.lengthM.toLocaleString('es-AR')} m · geometría real (OSM · f1-circuits)`}
          fill
        >
          <CircuitMap track={track} drivers={GRID.slice(0, 8)} lapFraction={lapFraction}>
            <div className="overlay overlay--top">
              <BattleStrip
                battle={duel}
                others={duels.filter((b) => b !== duel)}
                onPick={setDuel}
              />
            </div>
            <InsightOverlay lap={scenarioLap} />
          </CircuitMap>
        </Panel>

      </div>

      {/* --------------------------------------------------- duelo + ventanas */}
      <div className="stack">
        <Panel title="Ventanas de boxes" note="rangos, no vueltas exactas" fill>
          <div className="window-list">
          {GRID.map((d) => {
            const w = d.pitWindow
            return (
              <div className="window-row" key={d.code}>
                <span className="num">{d.code}</span>
                <span className="window-track">
                  {w ? (
                    <span
                      className="window-bar"
                      style={{
                        left: `${(w.opensLap / totalLaps) * 100}%`,
                        width: `${((w.closesLap - w.opensLap) / totalLaps) * 100}%`,
                      }}
                    />
                  ) : (
                    <span className="window-none">sin proyectar</span>
                  )}
                  <span className="window-now" style={{ left: `${nowPct}%` }} />
                </span>
              </div>
            )
          })}
          </div>
          <p className="footnote">
            Eje = vueltas 1–{totalLaps}. La marca roja es la vuelta actual.{' '}
            <strong>Sin proyectar</strong> = la goma está plana o mejorando, así que no hay cruce
            que anticipar.
          </p>
        </Panel>
      </div>
    </div>
  )
}
