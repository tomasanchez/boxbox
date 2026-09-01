/**
 * Torre de tiempos: posiciones y ventanas de boxes.
 *
 * Como en la transmisión, **no se muestra todo junto**. La columna de datos
 * alterna entre intervalo al de adelante, distancia al líder, edad de la goma y
 * degradación; lo que siempre queda es la posición, el compuesto y la ventana,
 * que es lo que este sistema aporta.
 */

import { useState } from 'react'
import { GRID, RACE } from './data'
import { fmt } from './format'
import type { DriverState } from './types'
import { Panel, Tyre } from './ui'

type Metric = 'interval' | 'leader' | 'age' | 'deg'

const METRICS: { id: Metric; label: string; title: string }[] = [
  { id: 'interval', label: 'Int', title: 'Intervalo al auto de adelante' },
  { id: 'leader', label: 'Líder', title: 'Distancia al líder' },
  { id: 'age', label: 'Goma', title: 'Vueltas con el juego actual' },
  { id: 'deg', label: 'Deg', title: 'Segundos por vuelta que pierde por desgaste' },
]

function windowText(driver: DriverState): string {
  if (!driver.pitWindow) return '—'
  return `${driver.pitWindow.opensLap}–${driver.pitWindow.closesLap}`
}

/** Valor y clase de color de la métrica activa para un piloto. */
function metricCell(driver: DriverState, metric: Metric): { text: string; tone: string } {
  switch (metric) {
    case 'interval':
      return {
        text: driver.gapAheadS === null ? '—' : `+${fmt(driver.gapAheadS)}`,
        tone: '',
      }
    case 'leader':
      return {
        text: driver.gapLeaderS === null || driver.position === 1
          ? 'líder'
          : `+${fmt(driver.gapLeaderS)}`,
        tone: driver.position === 1 ? ' grid-row__pos' : '',
      }
    case 'age':
      return { text: `${driver.tyreAge}v`, tone: '' }
    case 'deg':
      return {
        text: fmt(driver.degradationS, 2, true),
        // Negativo = la goma todavía mejora; se marca en verde.
        tone: driver.degradationS < 0 ? ' grid-row__deg--gaining' : '',
      }
  }
}

export function GridPanel({ lap }: { lap: number }) {
  const { totalLaps } = RACE
  const [metric, setMetric] = useState<Metric>('interval')
  const nowPct = (lap / totalLaps) * 100
  const active = METRICS.find((m) => m.id === metric) ?? METRICS[0]

  return (
    <Panel title="Posiciones y ventanas" note={`V${lap} / ${totalLaps} · ${GRID.length} en pista`} fill>
      <div className="metrics" role="group" aria-label="Dato a mostrar">
        {METRICS.map((m) => (
          <button
            key={m.id}
            type="button"
            className="metric"
            aria-pressed={m.id === metric}
            title={m.title}
            onClick={() => setMetric(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="tower panel__grow">
        <div className="tower__h">P</div>
        <div className="tower__h">Piloto</div>
        <div className="tower__h" title="Compuesto">
          G
        </div>
        <div className="tower__h tower__h--num">{active.label}</div>
        <div className="tower__h">Vent.</div>
        <div className="tower__h">1–{totalLaps}</div>

        {GRID.map((d) => {
          const w = d.pitWindow
          const cell = metricCell(d, metric)
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
              <div className={`num tower__v${cell.tone}`}>{cell.text}</div>
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
        La marca roja es la vuelta actual. <strong>—</strong> en la ventana significa que la goma
        está plana o mejorando, así que no hay cruce que anticipar.
      </p>
    </Panel>
  )
}
