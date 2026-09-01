/** Panel de carrera: parrilla, trazado, duelo y ventanas de boxes. */

import { BATTLE, BATTLE_ALT, COMPOUND_COLOR, GRID, PLAN_DISTRIBUTION, RACE } from './data'
import type { DriverState, StrategyBattle } from './types'
import { fmt, pct } from './format'
import { Panel, Tyre } from './ui'

const VERDICT_TEXT: Record<StrategyBattle['verdict'], string> = {
  SALE_ADELANTE: 'Sale adelante',
  CARA_O_CRUZ: 'A cara o cruz',
  SIGUE_ATRAS: 'Sigue atrás',
}

/** Trazado esquemático — no es la geometría real del circuito. */
const TRACK_PATH =
  'M 120 34 C 178 30 214 46 218 76 C 222 108 196 120 168 128 C 140 136 118 148 122 170 ' +
  'C 126 190 152 194 176 190 C 200 186 222 190 224 210 C 226 232 200 242 172 240 ' +
  'C 132 238 96 236 70 224 C 40 210 26 184 30 152 C 34 118 52 96 74 74 C 92 56 100 36 120 34 Z'

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

export function RaceView({ scenarioLap }: { scenarioLap: number }) {
  const { totalLaps } = RACE
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
        <Panel title="Trazado" note="esquemático · posiciones ilustrativas">
          <div className="circuit">
            <svg viewBox="0 0 254 274" role="img" aria-label="Trazado esquemático del circuito">
              <path className="circuit__path" d={TRACK_PATH} />
              <path className="circuit__inner" d={TRACK_PATH} />
              {GRID.slice(0, 6).map((d, i) => {
                const angle = (i / 6) * Math.PI * 2 - Math.PI / 2
                const cx = 127 + Math.cos(angle) * 88
                const cy = 137 + Math.sin(angle) * 96
                return (
                  <g key={d.code}>
                    <circle
                      className="circuit__car"
                      cx={cx}
                      cy={cy}
                      r={6.5}
                      fill={d.teamColor}
                    />
                    <text className="circuit__label" x={cx} y={cy + 3} textAnchor="middle">
                      {d.position}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>
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
