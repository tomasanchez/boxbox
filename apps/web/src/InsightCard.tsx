/**
 * Tarjeta de insight superpuesta sobre el trazado.
 *
 * Va abajo a la derecha del mapa, con borde blanco y cabecera invertida, tal
 * como en el concepto. A la izquierda queda la referencia de compuestos.
 */

import { COMPOUND_COLOR, PLAN_DISTRIBUTION } from './data'
import type { Compound } from './types'
import { pct } from './format'

const LEGEND: Compound[] = ['HARD', 'MEDIUM', 'SOFT']

const SHORT: Record<Compound, string> = {
  HARD: 'HARD',
  MEDIUM: 'MED',
  SOFT: 'SOFT',
  INTERMEDIATE: 'INTER',
  WET: 'WET',
}

export function InsightOverlay({ lap }: { lap: number }) {
  const plan = PLAN_DISTRIBUTION
  const stops = plan.modalPlan.length - 1
  const modalProbability = plan.stopDistribution[String(stops)] ?? 0
  const totalLaps = plan.modalPlan.reduce((sum, s) => sum + s.laps, 0)

  const alternatives = Object.entries(plan.stopDistribution)
    .filter(([key]) => key !== String(stops))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([key, p]) => `${key} PARADA${key === '1' ? '' : 'S'} ${pct(p)}`)
    .join(' · ')

  return (
    <div className="overlay">
      <div className="overlay__legend">
        <div>Línea de meta / entrada a boxes</div>
        <div className="overlay__chips">
          {LEGEND.map((c) => (
            <span className="overlay__chip" key={c}>
              <span
                className={`overlay__swatch${c === 'HARD' ? ' overlay__swatch--hard' : ''}`}
                style={{ background: COMPOUND_COLOR[c] }}
              />
              {SHORT[c]}
            </span>
          ))}
        </div>
      </div>

      <div className="insight">
        <div className="insight__head">
          <span className="insight__title">Insight de estrategia</span>
          <span className="insight__lap">V{lap}</span>
        </div>

        <div className="insight__body">
          <div className="insight__kicker">Plan más probable · {plan.driver}</div>

          <div className="insight__headline">
            <span className="insight__stops">
              {stops} PARADA{stops === 1 ? '' : 'S'}
            </span>
            <span className="insight__pct">{pct(modalProbability)}</span>
          </div>

          <div className="insight__seq">
            {plan.modalPlan.map((s, i) => (
              <span key={`${s.compound}-${i}`}>
                {i > 0 ? <span className="insight__dot">·</span> : null}
                <span style={{ color: COMPOUND_COLOR[s.compound] }}>{SHORT[s.compound]}</span>
              </span>
            ))}
          </div>

          {/* Ancho proporcional a las vueltas de cada stint. */}
          <div className="insight__bar">
            {plan.modalPlan.map((s, i) => (
              <span
                key={`bar-${i}`}
                style={{
                  width: `${(s.laps / totalLaps) * 100}%`,
                  background: COMPOUND_COLOR[s.compound],
                }}
              />
            ))}
          </div>

          <div className="insight__alt">
            <span>Alternativas</span>
            <span className="insight__altv">{alternatives}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
