/**
 * Pronóstico congelado y su resultado.
 *
 * El caso cargado es uno que el sistema FALLÓ: Zandvoort tuvo bandera roja en
 * la vuelta 2 y terminó en 3 paradas. Se muestra al mismo tamaño que un acierto
 * — esconderlo sería el error que este trabajo trata de no cometer.
 */

import { useState } from 'react'
import { COMPOUND_COLOR, FORECAST } from './data'
import { fmt, pct } from './format'
import { Panel } from './ui'

export function ForecastView() {
  const [showActual, setShowActual] = useState(true)
  const f = FORECAST
  const actual = f.actual
  const visible = showActual && actual !== null

  const plannedLaps = f.modalPlan.reduce((sum, s) => sum + s.laps, 0)
  const modalStops = String(f.modalPlan.length - 1)
  const insideInterval =
    actual !== null &&
    actual.firstStopLap >= f.firstStopInterval.low &&
    actual.firstStopLap <= f.firstStopInterval.high

  const pos = (lap: number) => (lap / f.totalLaps) * 100

  return (
    <div className="view view--forecast">
      {/* ------------------------------------------------------- distribución */}
      <div className="stack stack--forecast-left">
        <Panel
          title={`Pronóstico congelado · ${f.season} R${f.round} ${f.circuit}`}
          note={`${f.totalLaps} vueltas`}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 'var(--gap)',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 800 }}>
                {f.driver} · plan de neumáticos
              </div>
              <div className="footnote">
                emitido {f.issuedAt} · antes de la clasificación · sin ediciones
              </div>
            </div>
            <span className="frozen">Congelado</span>
          </div>

          <div className="scenarios" role="group" aria-label="Ver antes o después">
            <button
              type="button"
              className="scenario"
              aria-pressed={!showActual}
              onClick={() => setShowActual(false)}
            >
              Antes
            </button>
            <button
              type="button"
              className="scenario"
              aria-pressed={showActual}
              onClick={() => setShowActual(true)}
            >
              Después
            </button>
          </div>
        </Panel>

        <Panel title="Distribución de paradas" note="lo que dijimos antes de largar">
          <div className="dist">
            {Object.entries(f.stopDistribution).map(([stops, p]) => {
              const isModal = stops === modalStops
              const isActual = visible && actual !== null && Number(stops) === actual.stops
              return (
                <div
                  className={`dist-row${isModal ? ' dist-row--modal' : ''}${
                    isActual ? ' dist-row--actual' : ''
                  }`}
                  key={stops}
                >
                  <span>{stops} parada{stops === '1' ? '' : 's'}</span>
                  <span className="dist-track">
                    <span className="dist-bar" style={{ width: `${p * 100}%` }} />
                  </span>
                  <span className="num" style={{ textAlign: 'right' }}>
                    {pct(p)}
                  </span>
                </div>
              )
            })}
          </div>
          {visible && actual ? (
            <p className="footnote">
              En verde, lo que realmente pasó: <strong>{actual.stops} paradas</strong>, a las que
              habíamos dado {pct(f.stopDistribution[String(actual.stops)] ?? 0)}.
            </p>
          ) : (
            <p className="footnote">
              Ninguna opción llega al 50%: la carrera estaba genuinamente abierta.
            </p>
          )}
        </Panel>

        <Panel title="Plan modal" note={`${plannedLaps} vueltas planificadas`}>
          <div className="stints">
            {f.modalPlan.map((s, i) => (
              <div
                className="stint"
                key={`p-${i}`}
                style={{ flex: s.laps, background: COMPOUND_COLOR[s.compound] }}
              >
                {s.compound} · {s.laps}
              </div>
            ))}
          </div>
          {visible && actual ? (
            <>
              <div className="stints__legend">
                <span>real ↓</span>
                <span>{actual.plan.length} stints</span>
              </div>
              <div className="stints">
                {actual.plan.map((s, i) => (
                  <div
                    className="stint"
                    key={`a-${i}`}
                    style={{ flex: s.laps, background: COMPOUND_COLOR[s.compound] }}
                  >
                    {s.laps}
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </Panel>
      </div>

      {/* ------------------------------------------------- intervalo + veredicto */}
      <div className="stack stack--forecast-right">
        <Panel title="Intervalo de la primera parada" note="vueltas, no una vuelta">
          <div className="interval">
            <span
              className="interval__band"
              style={{
                left: `${pos(f.firstStopInterval.low)}%`,
                width: `${pos(f.firstStopInterval.high - f.firstStopInterval.low)}%`,
              }}
            />
            <span
              className="interval__median"
              style={{ left: `${pos(f.firstStopInterval.median)}%` }}
            />
            <span
              className="interval__flag"
              style={{ left: `${pos(f.firstStopInterval.median)}%`, color: 'var(--yellow)' }}
            >
              V{f.firstStopInterval.median}
            </span>
            {visible && actual ? (
              <>
                <span
                  className="interval__actual"
                  style={{ left: `${pos(actual.firstStopLap)}%` }}
                />
                <span
                  className="interval__flag"
                  style={{
                    left: `${pos(actual.firstStopLap)}%`,
                    color: 'var(--red)',
                    top: 'auto',
                    bottom: '10px',
                  }}
                >
                  real V{actual.firstStopLap}
                </span>
              </>
            ) : null}
            {[1, 18, 36, 54, 72].map((lap, i, all) => (
              <span
                className={`interval__tick${i === 0 ? ' interval__tick--first' : ''}${
                  i === all.length - 1 ? ' interval__tick--last' : ''
                }`}
                key={lap}
                style={{ left: `${pos(lap)}%` }}
              >
                V{lap}
              </span>
            ))}
          </div>
          <p className="footnote">
            Intervalo creíble: <strong>V{f.firstStopInterval.low}–V{f.firstStopInterval.high}</strong>,
            mediana V{f.firstStopInterval.median}.
          </p>
        </Panel>

        <Panel title="Resultado" note="puntuado después de la carrera">
          <div className={`result result--${insideInterval ? 'hit' : 'miss'}`}>
            <span className="result__kicker">
              {insideInterval ? 'Dentro del intervalo' : 'Fuera del intervalo'}
            </span>
            <span className="result__verdict">
              {insideInterval ? 'Pronóstico acertado' : 'Pronóstico fallado'}
            </span>
            <p className="result__body">
              {actual ? (
                <>
                  Dijimos que la primera parada caía entre las vueltas {f.firstStopInterval.low} y{' '}
                  {f.firstStopInterval.high}. Ocurrió en la{' '}
                  <strong>vuelta {actual.firstStopLap}</strong>, porque hubo{' '}
                  <strong>bandera roja</strong> y 21 de 22 pilotos cambiaron goma gratis. La
                  carrera terminó en {actual.stops} paradas, a las que habíamos dado{' '}
                  {pct(f.stopDistribution[String(actual.stops)] ?? 0)}.
                </>
              ) : (
                'Pendiente: la carrera todavía no se corrió.'
              )}
            </p>
          </div>

          <div className="facts">
            <div className="fact">
              <div className="fact__k">Paradas dichas</div>
              <div className="fact__v num">{modalStops}</div>
            </div>
            <div className="fact">
              <div className="fact__k">Paradas reales</div>
              <div className="fact__v num">{actual ? actual.stops : '—'}</div>
            </div>
            <div className="fact">
              <div className="fact__k">Error 1.ª parada</div>
              <div className="fact__v num">
                {actual ? `${fmt(actual.firstStopLap - f.firstStopInterval.median, 0, true)} v` : '—'}
              </div>
            </div>
            <div className="fact">
              <div className="fact__k">Prob. asignada</div>
              <div className="fact__v num">
                {actual ? pct(f.stopDistribution[String(actual.stops)] ?? 0) : '—'}
              </div>
            </div>
          </div>

          <p className="footnote">
            Un pronóstico fallado se muestra al mismo tamaño que uno acertado. El acierto puntual
            no es la métrica.
          </p>
        </Panel>

        <Panel title="Calibración" note="la métrica principal del sistema">
          <div className="calib">
            <div className="calib__plot">
              <svg className="calib__diag" viewBox="0 0 100 100" preserveAspectRatio="none">
                <line x1="0" y1="100" x2="100" y2="0" />
              </svg>
              <span className="calib__axis" style={{ left: 4, top: 3 }}>
                100%
              </span>
              <span className="calib__axis" style={{ left: 4, bottom: 3 }}>
                0%
              </span>
              <span className="calib__axis" style={{ right: 4, bottom: 3 }}>
                dicho →
              </span>
              <span
                className="calib__axis"
                style={{ left: 4, top: '50%', transform: 'translateY(-50%)' }}
              >
                ↑
              </span>
            </div>
            <div className="calib__empty">
              <span className="calib__count num">0 / 11</span>
              <p className="footnote">
                Pronósticos emitidos sobre las carreras que faltan de 2026. El diagrama se llena a
                medida que se corren: cada punto compara <strong>lo que dijimos</strong> con{' '}
                <strong>lo que pasó</strong>, y la diagonal es la calibración perfecta.
              </p>
              <p className="footnote">
                Todavía vacío a propósito: <strong>no hay datos que mostrar</strong> hasta que se
                corra Monza.
              </p>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  )
}
