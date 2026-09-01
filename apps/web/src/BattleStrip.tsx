/**
 * Duelo de estrategia, con la forma de la gráfica «Pit Strategy Battle».
 *
 * Sigue el reparto de la transmisión: cabecera con el título, el **gap
 * proyectado grande y centrado** arriba, los dos pilotos enfrentados abajo con
 * su barra de equipo y la distancia dibujada entre ellos, y la probabilidad en
 * un recuadro destacado a la derecha.
 *
 * Es una tarjeta compacta, no una banda a todo el ancho: en la transmisión
 * ocupa poco más de un tercio de la pantalla.
 *
 * **Todo se recalcula con la simulación corriendo.** El duelo sale del orden en
 * pista de ese instante, así que el intervalo, el gap proyectado y la
 * probabilidad se mueven solos, y la barra entre los dos autos se llena a
 * medida que el perseguidor se acerca. No es una animación decorativa: es el
 * mismo número que marca la tabla de tiempos.
 *
 * La tarjeta aparece y desaparece sola: `battle.ts` sólo arma duelos de autos
 * que están en ventana de parada. La ventana se muestra en la cabecera, para
 * que se vea por qué es **este** duelo y no otro.
 *
 * Diferencia deliberada con la televisión: ahí el recuadro es siempre naranja y
 * la probabilidad es un dato más. Acá **manda**, y le da el color a la tarjeta,
 * porque un gap proyectado de −0,1 s al 47% es un volado y anunciarlo como
 * adelantamiento sería engañoso.
 */

import { useEffect, useRef, useState } from 'react'
import { IN_RANGE_S, battleKey } from './battle'
import { GRID } from './data'
import { fmt, pct } from './format'
import type { StrategyBattle } from './types'

const VERDICT_TEXT: Record<StrategyBattle['verdict'], string> = {
  SALE_ADELANTE: 'sale adelante',
  CARA_O_CRUZ: 'a cara o cruz',
  SIGUE_ATRAS: 'sigue atrás',
}

/** Cuánto pesa cada lectura nueva en la tendencia suavizada. */
const TREND_SMOOTH = 0.3

/** Debajo de esto el intervalo se considera estable, en segundos por segundo. */
const TREND_DEAD_ZONE = 0.015

function teamColor(code: string): string {
  return GRID.find((d) => d.code === code)?.teamColor ?? '#8f8b88'
}

/**
 * Velocidad a la que cambia el intervalo, en segundos de gap por segundo.
 *
 * El cronometraje llega a saltos, así que la derivada cruda salta con él: se
 * suaviza para que la flecha no titile entre «se acerca» y «se aleja» cuando en
 * realidad el intervalo está quieto.
 */
function useGapTrend(key: string, gap: number): number {
  const [rate, setRate] = useState(0)
  const prev = useRef({ key, gap, at: 0 })

  useEffect(() => {
    const at = performance.now()
    const last = prev.current

    // Duelo nuevo: no hay historia con la que comparar.
    if (last.key !== key) {
      prev.current = { key, gap, at }
      setRate(0)
      return
    }

    const dt = (at - last.at) / 1000
    if (dt <= 0.05) return

    const instant = (gap - last.gap) / dt
    prev.current = { key, gap, at }
    setRate((r) => r + (instant - r) * TREND_SMOOTH)
  }, [key, gap])

  return rate
}

export function BattleStrip({
  battle,
  others,
  onPick,
  open,
  onToggle,
}: {
  battle: StrategyBattle
  /** Otros duelos activos, para poder alternar sin abandonar el mapa. */
  others: StrategyBattle[]
  onPick: (b: StrategyBattle) => void
  open: boolean
  onToggle: () => void
}) {
  const rate = useGapTrend(battleKey(battle), battle.gapNow)
  const trend = rate < -TREND_DEAD_ZONE ? 'closing' : rate > TREND_DEAD_ZONE ? 'opening' : 'steady'

  // Cuánto del camino tiene recorrido el perseguidor: 0 a rango completo, 1
  // pegado al escape. Es lo que llena la barra entre los dos autos.
  const closed = 1 - Math.min(Math.max(battle.gapNow, 0) / IN_RANGE_S, 1)

  return (
    <div className={`battle battle--${battle.verdict}`}>
      <div className="battle__head">
        <span className="battle__title">Duelo de estrategia</span>
        <span className="battle__sub">
          si {battle.chaser} para ahora
          {/*
           * La ventana es el motivo por el que este duelo está en pantalla y no
           * otro: se muestra al lado, así se ve de dónde salió.
           */}
          {battle.chaserWindow
            ? ` · ventana ${battle.chaserWindow.opensLap}–${battle.chaserWindow.closesLap}`
            : null}
          {open ? null : ` · ${pct(battle.probability)}`}
        </span>
        <button
          type="button"
          className="card__toggle"
          onClick={onToggle}
          aria-expanded={open}
          title={open ? 'Minimizar' : 'Mostrar'}
        >
          {open ? '–' : '+'}
        </button>
      </div>

      {open ? (
        <>
          <div className="battle__body">
            <div className="battle__stage">
              <div className="battle__gap">
                {/*
                 * Con signo, no en valor absoluto: negativo quiere decir que el
                 * perseguidor salió adelante. Mostrando sólo la magnitud, un
                 * −2,36 se leía «va a estar 2,36 s atrás» junto a un 90% de
                 * adelantamiento, que es justo lo contrario de lo que pasa.
                 */}
                <span className="battle__gapv num">{fmt(battle.gapAfter, 2, true)}</span>
                <span className="battle__gapl">
                  gap proyectado
                  <br />
                  en {battle.responseLaps} vueltas
                </span>
              </div>

              <div className="battle__cars">
                <span className="battle__car">
                  <span className="battle__bar" style={{ background: teamColor(battle.chaser) }} />
                  <span className="battle__code">{battle.chaser}</span>
                </span>

                {/*
                 * La distancia real entre los dos, ahora mismo. La parte llena
                 * crece cuando el perseguidor recorta y se achica cuando lo
                 * dejan atrás.
                 */}
                <span className={`battle__lane battle__lane--${trend}`}>
                  <span
                    className="battle__closed"
                    style={{ width: `${closed * 100}%` }}
                    aria-hidden="true"
                  />
                  <span className="battle__live num">
                    <span className="battle__arrow" aria-hidden="true">
                      {trend === 'closing' ? '▼' : trend === 'opening' ? '▲' : '='}
                    </span>
                    {fmt(battle.gapNow)}
                  </span>
                </span>

                <span className="battle__car">
                  <span className="battle__bar" style={{ background: teamColor(battle.leader) }} />
                  <span className="battle__code">{battle.leader}</span>
                </span>
              </div>
            </div>

            <div className="battle__odds">
              <span className="battle__pct num">{pct(battle.probability)}</span>
              <span className="battle__verdict">
                {battle.chaser}
                <br />
                {VERDICT_TEXT[battle.verdict]}
              </span>
            </div>
          </div>

          {others.length > 0 ? (
            <div className="battle__others">
              <span className="battle__otherslabel">Otros duelos</span>
              {others.map((b) => (
                <button
                  type="button"
                  className="battle__other"
                  key={battleKey(b)}
                  onClick={() => onPick(b)}
                >
                  {b.chaser} vs {b.leader}
                  <span className="num"> {pct(b.probability)}</span>
                </button>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
