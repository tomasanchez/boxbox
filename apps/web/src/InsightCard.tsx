/**
 * Tarjeta de insight superpuesta sobre el trazado.
 *
 * Va abajo a la derecha del mapa, con borde blanco y cabecera invertida, tal
 * como en el concepto. A la izquierda queda la referencia de compuestos.
 *
 * El plan **ya no está escrito a mano**. Sale del algoritmo genético de
 * `apps/ml/src/boxbox_ml/strategy.py`, que para cada auto busca la secuencia de
 * paradas que mejor le va sobre 300 carreras sorteadas — con el desgaste, la
 * pérdida de boxes y el safety car sacados de las distribuciones medidas.
 *
 * El porcentaje que se muestra no es «probabilidad de que la carrera termine con
 * tantas paradas»: es cuánto de la población final del algoritmo se quedó en esa
 * cantidad. Es la confianza de la búsqueda, y presentarlo de otro modo sería
 * atribuirle a la carrera una certeza que es del optimizador.
 *
 * El objetivo tiene **tres** valores posibles y no dos —puntos, entrar a los
 * puntos, posición—, así que la etiqueta sale de `objectiveLabel` en vez de un
 * ternario: con dos ramas, el auto de la burbuja se leía como si estuviera
 * maximizando posición cuando maximiza la chance de entrar a los diez.
 */

import { COMPOUND_COLOR } from './data'
import { pct } from './format'
import { PLANS } from './plans'
import type { RecommendedPlan } from './plans'
import { objectiveLabel } from './prerace'
import type { Compound } from './types'

const LEGEND: Compound[] = ['HARD', 'MEDIUM', 'SOFT']

const SHORT: Record<Compound, string> = {
  HARD: 'HARD',
  MEDIUM: 'MED',
  SOFT: 'SOFT',
  INTERMEDIATE: 'INTER',
  WET: 'WET',
}

const LETTER: Record<string, Compound> = { H: 'HARD', M: 'MEDIUM', S: 'SOFT' }

/** Las tandas que codifica un plan como «H17-H25». */
function stints(plan: string): { compound: Compound; laps: number }[] {
  return plan.split('-').map((part) => ({
    compound: LETTER[part[0]] ?? 'MEDIUM',
    laps: Number.parseInt(part.slice(1), 10) || 0,
  }))
}

export function InsightOverlay({
  lap,
  driver,
  plan: given,
  open,
  onToggle,
}: {
  lap: number
  /** De quién se muestra el plan. */
  driver: string
  /**
   * Plan a mostrar. Sin esto manda el de la búsqueda de la vuelta 30.
   *
   * Corriendo desde la largada el plan es otro —el del export pre-carrera— y es
   * el que el auto está ejecutando en el mapa. Mostrar el de la vuelta 30 ahí
   * sería la tarjeta hablando de una carrera distinta de la que se ve.
   */
  plan?: RecommendedPlan
  open: boolean
  onToggle: () => void
}) {
  const plan = given ?? PLANS[driver]
  const sequence = plan ? stints(plan.plan) : []
  const stops = plan ? plan.stops.length : 0
  const confidence = plan ? (plan.stopDistribution[String(stops)] ?? 0) : 0
  const totalLaps = sequence.reduce((sum, s) => sum + s.laps, 0) || 1

  const alternatives = plan
    ? Object.entries(plan.stopDistribution)
        .filter(([key]) => key !== String(stops))
        .sort((a, b) => b[1] - a[1])
        .slice(0, 2)
        .map(([key, p]) => `${key} PARADA${key === '1' ? '' : 'S'} ${pct(p)}`)
        .join(' · ')
    : ''

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

      {plan ? (
        <div className="insight">
          <div className="insight__head">
            <span className="insight__title">Plan recomendado</span>
            <span className="insight__lap">V{lap}</span>
            <button
              type="button"
              className="card__toggle card__toggle--invert"
              onClick={onToggle}
              aria-expanded={open}
              title={open ? 'Minimizar' : 'Mostrar'}
            >
              {open ? '–' : '+'}
            </button>
          </div>

          {open ? (
            <div className="insight__body">
              {/*
               * Se dice qué se estaba maximizando. Para un auto fuera de los
               * puntos el objetivo «puntos» está plano en cero y el algoritmo
               * pasa a posición; mostrar las dos cosas igual sería mentir sobre
               * qué se optimizó.
               */}
              <div className="insight__kicker">
                {driver} · {objectiveLabel(plan.objective)} · llega P{plan.meanPosition.toFixed(1)}
              </div>

              <div className="insight__headline">
                <span className="insight__stops">
                  {stops} PARADA{stops === 1 ? '' : 'S'}
                </span>
                <span
                  className="insight__pct"
                  title="Confianza de la búsqueda, no probabilidad de la carrera"
                >
                  {pct(confidence)}
                </span>
              </div>

              <div className="insight__seq">
                {sequence.map((s, i) => (
                  <span key={`${s.compound}-${i}`}>
                    {i > 0 ? <span className="insight__dot">·</span> : null}
                    <span style={{ color: COMPOUND_COLOR[s.compound] }}>
                      {SHORT[s.compound]} {s.laps}
                    </span>
                  </span>
                ))}
              </div>

              {/* Ancho proporcional a las vueltas de cada tanda. */}
              <div className="insight__bar">
                {sequence.map((s, i) => (
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
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
