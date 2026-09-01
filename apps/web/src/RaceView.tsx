/** Panel de carrera: parrilla, trazado, duelo y ventanas de boxes. */

import { CircuitMap } from './CircuitMap'
import { BATTLE, BATTLE_ALT, COMPOUND_COLOR, GRID, PLAN_DISTRIBUTION, RACE } from './data'
import { TRACKS } from './tracks'
import type { DriverState, StrategyBattle } from './types'
import { fmt, pct } from './format'
import { Panel, Tyre } from './ui'

const VERDICT_TEXT: Record<StrategyBattle['verdict'], string> = {
  SALE_ADELANTE: 'Sale adelante',
  CARA_O_CRUZ: 'A cara o cruz',
  SIGUE_ATRAS: 'Sigue atrás',
}


function windowText(driver: DriverState): string {
  if (!driver.pitWindow) return 'sin proyectar'
  return `${driver.pitWindow.opensLap}–${driver.pitWindow.closesLap}`
}

function Duel({ battle }: { battle: StrategyBattle }) {
  return (
    <div className="duel">
      <div className="duel__head">
        <span className="duel__who">{battle.chaser}</span>
        <span className="duel__vs">para ahora · persigue a</span>
        <span className="duel__who">{battle.leader}</span>
      </div>

      <div className={`verdict verdict--${battle.verdict}`}>
        <span className="verdict__text">{VERDICT_TEXT[battle.verdict]}</span>
        <span className="verdict__prob num">{pct(battle.probability)}</span>
      </div>

      <div className="facts">
        <div className="fact">
          <div className="fact__k">Gap ahora</div>
          <div className="fact__v num">{fmt(battle.gapNow, 2, true)} s</div>
        </div>
        <div className="fact">
          <div className="fact__k">Ganancia / vuelta</div>
          <div className="fact__v num">{fmt(battle.perLapGain)} s</div>
        </div>
        <div className="fact">
          <div className="fact__k">Respuesta de {battle.leader}</div>
          <div className="fact__v num">{battle.responseLaps} vueltas</div>
        </div>
        <div className="fact">
          <div className="fact__k">Gap proyectado</div>
          <div className="fact__v num">{fmt(battle.gapAfter, 2, true)} s</div>
        </div>
      </div>
    </div>
  )
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
      <div className="stack stack--centre">
        <Panel
          title={`Trazado · ${track.name}`}
          note={`${track.lengthM.toLocaleString('es-AR')} m · geometría real (OSM)`}
        >
          <CircuitMap track={track} drivers={GRID.slice(0, 8)} lapFraction={lapFraction} />
        </Panel>

        <Panel
          title={`Plan más probable · ${PLAN_DISTRIBUTION.driver}`}
          note="salida del algoritmo genético"
        >
          <div className="stints">
            {PLAN_DISTRIBUTION.modalPlan.map((s, i) => (
              <div
                className="stint"
                key={`${s.compound}-${i}`}
                style={{
                  flex: s.laps,
                  background: COMPOUND_COLOR[s.compound],
                }}
              >
                {s.compound} · {s.laps}
              </div>
            ))}
          </div>
          <div className="stints__legend">
            <span>2 paradas · 48%</span>
            <span>alternativas: 1 parada 31% · 3 paradas 19%</span>
          </div>
          <p className="footnote">
            El plan modal es el más probable, <strong>no una certeza</strong>: en algo más de la
            mitad de las simulaciones la carrera se resuelve de otra manera.
          </p>
        </Panel>
      </div>

      {/* --------------------------------------------------- duelo + ventanas */}
      <div className="stack">
        <Panel title="Si para ahora" note={`duelo medido · v${scenarioLap}`}>
          <Duel battle={BATTLE} />
        </Panel>

        <Panel title="Segundo duelo" note="banda de incertidumbre">
          <Duel battle={BATTLE_ALT} />
        </Panel>

        <Panel title="Ventanas de boxes" note="rangos, no vueltas exactas">
          <div className="window-list">
          {GRID.slice(0, 8).map((d) => {
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
