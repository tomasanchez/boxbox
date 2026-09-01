/**
 * Duelo de estrategia, con la forma de la gráfica «Pit Strategy Battle».
 *
 * Sigue el reparto de la transmisión: cabecera con el título, el **gap
 * proyectado grande y centrado** arriba, los dos pilotos enfrentados abajo con
 * su barra de equipo y una línea punteada entre ellos que representa la
 * distancia, y la probabilidad en un recuadro destacado a la derecha.
 *
 * Es una tarjeta compacta, no una banda a todo el ancho: en la transmisión
 * ocupa poco más de un tercio de la pantalla.
 *
 * Diferencia deliberada con la televisión: ahí el recuadro es siempre naranja y
 * la probabilidad es un dato más. Acá **manda**, y le da el color a la tarjeta,
 * porque un gap proyectado de −0,1 s al 47% es un volado y anunciarlo como
 * adelantamiento sería engañoso.
 */

import { GRID } from './data'
import { fmt, pct } from './format'
import type { StrategyBattle } from './types'

const VERDICT_TEXT: Record<StrategyBattle['verdict'], string> = {
  SALE_ADELANTE: 'sale adelante',
  CARA_O_CRUZ: 'a cara o cruz',
  SIGUE_ATRAS: 'sigue atrás',
}

function teamColor(code: string): string {
  return GRID.find((d) => d.code === code)?.teamColor ?? '#8f8b88'
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
  return (
    <div className={`battle battle--${battle.verdict}`}>
      <div className="battle__head">
        <span className="battle__title">Duelo de estrategia</span>
        <span className="battle__sub">
          si {battle.chaser} para ahora
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
                <span className="battle__gapv num">{fmt(Math.abs(battle.gapAfter))}</span>
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

                {/* La línea punteada representa la distancia entre los dos. */}
                <span className="battle__track" aria-hidden="true" />

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
                  key={`${b.chaser}-${b.leader}`}
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
