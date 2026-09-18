/**
 * Recuadro «IN PIT», el de la transmisión — con un número menos y una
 * aclaración más.
 *
 * La televisión muestra **dos** números mientras el auto está en el carril: el
 * tiempo detenido —los ~2,5 s en los gatos— y el total perdido en el pit lane.
 *
 * ## El tiempo detenido no está, así que no aparece
 *
 * FastF1 expone `PitInTime` y `PitOutTime` y nada entre medio: los segundos
 * parado no se pueden separar del recorrido por el carril. Sería el número más
 * visible del recuadro y sería inventado, así que en su lugar el recuadro
 * **declara que falta**. Ver `pitlane.ts`.
 *
 * ## Los dos números que sí van, y por qué no son el mismo
 *
 *   TRÁNSITO   reloj, de la línea de entrada a la de salida del pit lane.
 *              Mediana medida del circuito — en Zandvoort 18,0 s sobre 38
 *              paradas. Es un dato del carril, no de esta parada.
 *
 *   PÉRDIDA    lo que esta parada le cuesta al auto en la simulación, sorteado
 *              de los cuartiles medidos. Se mide sobre **dos vueltas** contra la
 *              mediana del campo, así que incluye la vuelta de entrada
 *              levantando el pie y la de salida con goma fría.
 *
 * En el agregado el tránsito da 23,0 s y la pérdida 22,6: **se parecen por
 * casualidad**. Por eso van rotulados distinto y con la aclaración al pie, y no
 * uno debajo del otro como si fueran la misma cuenta en dos escalas.
 */

import { fmt } from './format'
import { TRANSIT } from './pitlane'
import type { InPitCar } from './pitlane'
import { RACE } from './data'

export function InPitBox({ cars }: { cars: InPitCar[] }) {
  if (cars.length === 0) return null

  const [first, ...rest] = cars

  return (
    <div className="inpit" role="status" aria-live="polite">
      <div className="inpit__head">
        <span className="inpit__flag">En boxes</span>
        <span className="inpit__car">
          <span className="inpit__bar" style={{ background: first.teamColor }} />
          {first.code}
        </span>
      </div>

      <div className="inpit__rows">
        <div className="inpit__row">
          <span className="inpit__k">Tránsito por el pit lane</span>
          <span className="inpit__v num">{fmt(TRANSIT.median, 1)} s</span>
          <span className="inpit__src">
            {TRANSIT.ownCircuit
              ? `mediana medida · ${RACE.circuit} · ${TRANSIT.stops} paradas`
              : `sin medición de ${RACE.circuit}: mediana de las ${TRANSIT.stops} en verde`}
          </span>
        </div>

        {/*
         * Sin plan cargado no hay pérdida que mostrar. Se omite la fila en vez
         * de rellenarla: es el único número de acá que depende de esta parada en
         * particular, y aproximarlo sería inventar justo lo que falta.
         */}
        {first.stop ? (
          <div className="inpit__row">
            <span className="inpit__k">Pérdida de boxes</span>
            <span className="inpit__v num">{fmt(first.stop.lossS, 1)} s</span>
            <span className="inpit__src">sorteada de cuartiles medidos · 2 vueltas vs. el campo</span>
          </div>
        ) : null}

        <div className="inpit__row inpit__row--missing">
          <span className="inpit__k">Tiempo detenido</span>
          <span className="inpit__v inpit__v--none">sin dato</span>
          <span className="inpit__src">
            el dato sólo tiene entrada y salida: los gatos no se miden
          </span>
        </div>
      </div>

      {/*
       * La aclaración va en pantalla y no sólo en el código porque los dos
       * números se parecen —23,0 contra 22,6 en el agregado— y esa coincidencia
       * es la que invita a leerlos como si fueran el mismo.
       */}
      <p className="inpit__foot">
        Tránsito y pérdida <strong>no son lo mismo</strong>: reloj del carril contra dos vueltas
        medidas frente al campo. Que den parecido es casualidad.
      </p>

      {rest.length > 0 ? (
        <div className="inpit__also">
          También en boxes:{' '}
          {rest.map((c) => (
            <span className="inpit__alsocar" key={c.code}>
              <span className="inpit__bar" style={{ background: c.teamColor }} />
              {c.code}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
