/**
 * Parrilla y ventanas de boxes en una sola tabla.
 *
 * Antes eran dos paneles en columnas distintas que listaban los mismos diez
 * pilotos. Unificarlos libera la columna izquierda entera para el mapa y evita
 * que el ojo tenga que cruzar la pantalla para relacionar la degradación de un
 * auto con su ventana.
 */

import { GRID, RACE } from './data'
import { fmt } from './format'
import type { DriverState } from './types'
import { Panel, Tyre } from './ui'

function windowText(driver: DriverState): string {
  if (!driver.pitWindow) return 'sin proy.'
  return `${driver.pitWindow.opensLap}–${driver.pitWindow.closesLap}`
}

export function GridPanel({ lap }: { lap: number }) {
  const { totalLaps } = RACE
  const nowPct = (lap / totalLaps) * 100

  return (
    <Panel
      title="Parrilla y ventanas de boxes"
      note={`V${lap} / ${totalLaps} · rangos, no vueltas exactas`}
      fill
    >
      <div className="grid-table">
        <div className="grid-table__h">P</div>
        <div className="grid-table__h">Piloto</div>
        <div className="grid-table__h" title="Compuesto">
          G
        </div>
        <div className="grid-table__h" title="Vueltas con esa goma">
          V
        </div>
        <div className="grid-table__h" title="Segundos por vuelta">
          Deg
        </div>
        <div className="grid-table__h">Vent.</div>
        <div className="grid-table__h">Vueltas 1–{totalLaps}</div>

        {GRID.map((d) => {
          const w = d.pitWindow
          return (
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
              <div className={`num grid-row__deg--${d.degradationS < 0 ? 'gaining' : 'losing'}`}>
                {fmt(d.degradationS, 2, true)}
              </div>
              <div className={`grid-row__win num${w ? '' : ' grid-row__win--none'}`}>
                {windowText(d)}
              </div>
              <div className="grid-row__bar">
                {w ? (
                  <span
                    className="window-bar"
                    style={{
                      left: `${(w.opensLap / totalLaps) * 100}%`,
                      width: `${((w.closesLap - w.opensLap) / totalLaps) * 100}%`,
                    }}
                  />
                ) : null}
                <span className="window-now" style={{ left: `${nowPct}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      <p className="footnote">
        <strong>Deg</strong> en segundos por vuelta; en verde los que todavía mejoran porque
        queman combustible más rápido de lo que gastan la goma. La marca roja es la vuelta
        actual. <strong>Sin proy.</strong> = la goma está plana o mejorando, así que no hay
        cruce que anticipar.
      </p>
    </Panel>
  )
}
