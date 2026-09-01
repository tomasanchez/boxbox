/**
 * Torre de tiempos: posiciones y ventanas de boxes.
 *
 * Como en la transmisión, **no se muestra todo junto**. La columna de datos
 * alterna entre intervalo al de adelante, distancia al líder, edad de la goma y
 * degradación, y la ventana de boxes se puede ocultar aparte.
 *
 * Los que abandonan **no se borran de la tabla**: bajan al pie marcados OUT con
 * la vuelta en la que se fueron, igual que en la torre de la transmisión.
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

/** Un auto está afuera si ya abandonó a esta altura de la carrera. */
function isOut(driver: DriverState, lap: number): boolean {
  return driver.retiredOnLap != null && lap >= driver.retiredOnLap
}

/** Valor y clase de color de la métrica activa para un piloto. */
function metricCell(driver: DriverState, metric: Metric): { text: string; tone: string } {
  switch (metric) {
    case 'interval':
      return { text: driver.gapAheadS === null ? '—' : `+${fmt(driver.gapAheadS)}`, tone: '' }
    case 'leader':
      return {
        text:
          driver.gapLeaderS === null || driver.position === 1
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
  const [showWindow, setShowWindow] = useState(true)

  const nowPct = (lap / totalLaps) * 100
  const active = METRICS.find((m) => m.id === metric) ?? METRICS[0]

  // Los que corren primero por posición; los que abandonaron al pie, del
  // abandono más reciente al más viejo.
  const order = [...GRID].sort((a, b) => {
    const outA = isOut(a, lap)
    const outB = isOut(b, lap)
    if (outA !== outB) return outA ? 1 : -1
    if (outA && outB) return (b.retiredOnLap ?? 0) - (a.retiredOnLap ?? 0)
    return a.position - b.position
  })
  const running = order.filter((d) => !isOut(d, lap)).length

  return (
    <Panel
      title="Posiciones y ventanas"
      note={`V${lap} / ${totalLaps} · ${running} en pista`}
      fill
    >
      <div className="metrics" role="group" aria-label="Columnas a mostrar">
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
        <button
          type="button"
          className="metric metric--sep"
          aria-pressed={showWindow}
          title="Mostrar u ocultar la ventana de boxes"
          onClick={() => setShowWindow((v) => !v)}
        >
          Vent.
        </button>
      </div>

      <div className={`tower panel__grow${showWindow ? '' : ' tower--nowindow'}`}>
        <div className="tower__h">P</div>
        <div className="tower__h">Piloto</div>
        <div className="tower__h" title="Compuesto">
          G
        </div>
        <div className="tower__h tower__h--num">{active.label}</div>
        {showWindow ? (
          <>
            <div className="tower__h tower__h--win">Vent.</div>
            <div className="tower__h">1–{totalLaps}</div>
          </>
        ) : null}

        {order.map((d) => {
          const out = isOut(d, lap)
          const w = d.pitWindow
          const cell = metricCell(d, metric)
          return (
            <div className={`grid-row${out ? ' grid-row--out' : ''}`} key={d.code}>
              <div className="grid-row__pos num">{out ? '—' : d.position}</div>
              <div className="grid-row__code">
                <span className="team-bar" style={{ background: d.teamColor }} />
                {d.code}
              </div>
              <div>
                <Tyre compound={d.compound} />
              </div>
              <div className={`num tower__v${cell.tone}`}>
                {out ? (
                  <>
                    <span className="tag-out">DNF</span>{' '}
                    <span className="tower__outlap">v{d.retiredOnLap}</span>
                  </>
                ) : (
                  cell.text
                )}
              </div>

              {showWindow ? (
                <>
                  <div className={`grid-row__win num${w ? '' : ' grid-row__win--none'}`}>
                    {out ? '' : windowText(d)}
                  </div>
                  <div className="grid-row__bar">
                    {w && !out ? (
                      <span
                        className="window-bar"
                        style={{
                          left: `${(w.opensLap / totalLaps) * 100}%`,
                          width: `${((w.closesLap - w.opensLap) / totalLaps) * 100}%`,
                        }}
                      />
                    ) : null}
                    {out ? null : <span className="window-now" style={{ left: `${nowPct}%` }} />}
                  </div>
                </>
              ) : null}
            </div>
          )
        })}
      </div>

      <p className="footnote">
        La marca roja es la vuelta actual. <strong>—</strong> en la ventana significa que la goma
        está plana o mejorando, así que no hay cruce que anticipar. Los <strong>DNF</strong>{' '}
        quedan listados con la vuelta en la que abandonaron.
      </p>
    </Panel>
  )
}
