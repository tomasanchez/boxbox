/**
 * El plan que emitió el algoritmo, y lo que le costó elegirlo.
 *
 * La recomendación se emite en la vuelta 1 y no se recalcula (ADR-006): lo que
 * se ve acá es lo que el muro diría antes de largar, y la carrera animada se
 * contrasta contra esto.
 *
 * Además de las tandas van las cifras que son el antídoto contra leer la
 * recomendación como una certeza:
 *
 *   convergencia    cuánto de la población final quedó en esa cantidad de
 *                   paradas. Es confianza de la BÚSQUEDA, no de la carrera.
 *   valor de decidir  el mejor plan menos el peor de la población final. Cerca
 *                   de cero significa que da casi igual lo que haga.
 *   optimismo       cuánto más alto puntúa el plan sobre los sorteos con los que
 *                   fue elegido que sobre sorteos nuevos. Es el sobreajuste de
 *                   la búsqueda a sus propios dados, medido y publicado.
 */

import { COMPOUND_COLOR, COMPOUND_LETTER, RACE } from './data'
import { fmt } from './format'
import { plannedLaps, stintsOf } from './prerace'
import type { PreRaceCar } from './prerace'
import { Panel } from './ui'

export function PlanCard({ car }: { car: PreRaceCar }) {
  const stints = stintsOf(car.plan)
  const stops = car.stops.length
  const convergence = car.stop_distribution[String(stops)] ?? 0
  const covered = plannedLaps(car.plan)

  const width = (laps: number) => (laps / RACE.totalLaps) * 100

  return (
    <Panel
      title={`Plan recomendado · ${car.code}`}
      note={`${car.driver} · ${car.team} · larga P${car.grid_position}`}
    >
      <div className="plan__head">
        <span className="plan__stops">
          {stops} PARADA{stops === 1 ? '' : 'S'}
        </span>
        <span className="plan__seq num">{car.plan}</span>
      </div>

      <div className="plan__bar">
        {stints.map((stint, index) => (
          <span
            className="plan__stint"
            key={`${stint.compound}-${index}`}
            style={{ width: `${width(stint.laps)}%`, background: COMPOUND_COLOR[stint.compound] }}
            title={`${stint.compound}: vueltas ${stint.fromLap} a ${stint.fromLap + stint.laps - 1}`}
          >
            {COMPOUND_LETTER[stint.compound]} {stint.laps}
          </span>
        ))}
      </div>

      <div className="plan__stops-list">
        {car.stops.map((stop) => (
          <span className="plan__stop" key={stop.lap}>
            <span className="num">V{stop.lap}</span>
            <span
              className="plan__chip"
              style={{ background: COMPOUND_COLOR[stop.compound] }}
              title={stop.compound}
            >
              {COMPOUND_LETTER[stop.compound]}
            </span>
          </span>
        ))}
        <span className="plan__conv">
          convergencia {Math.round(convergence * 100)}% de la población final
        </span>
      </div>

      {/* Cuatro en una fila: en dos filas le come el alto al histograma de
          la tarjeta de abajo, que es el dato y no el contexto. */}
      <div className="facts facts--plan">
        <div className="fact">
          <div className="fact__k">Valor de decidir</div>
          <div className="fact__v num">{fmt(car.decision_value, 2)}</div>
        </div>
        <div className="fact">
          <div className="fact__k">Elegido con</div>
          <div className="fact__v num">{fmt(car.score_in_sample, 2, true)}</div>
        </div>
        <div className="fact">
          <div className="fact__k">Con dados nuevos</div>
          <div className="fact__v num">{fmt(car.score, 2, true)}</div>
        </div>
        <div className="fact">
          <div className="fact__k">Optimismo</div>
          <div className="fact__v num">{fmt(car.optimism, 2, true)}</div>
        </div>
      </div>

      <div className="alts">
        <span className="alts__label">Los que le siguieron</span>
        {car.alternatives.map((alt) => (
          <span className="alts__row" key={alt.plan}>
            <span className="num">{alt.plan}</span>
            <span className="alts__score num">{fmt(alt.score, 2, true)}</span>
          </span>
        ))}
      </div>

      <p className="footnote">
        Las tandas del export suman <strong>{covered}</strong> de {RACE.totalLaps} vueltas: se
        muestra lo que dice el archivo.
      </p>
    </Panel>
  )
}
