/**
 * Duelo de estrategia, con la forma de la gráfica «Pit Strategy Battle».
 *
 * Es una franja horizontal sobre el mapa, no un panel lateral: el gap
 * proyectado va grande y al centro, los dos pilotos abajo con su color de
 * equipo, y la probabilidad en un recuadro a la derecha.
 *
 * Diferencia deliberada con la gráfica de televisión: ahí la probabilidad es un
 * dato más, acá **manda**. El texto del veredicto sale de la probabilidad y no
 * del gap proyectado, porque un gap de −0,1 s al 47% es un volado y anunciarlo
 * como adelantamiento sería engañoso.
 */

import { GRID } from './data'
import { fmt, pct } from './format'
import type { StrategyBattle } from './types'

const VERDICT_TEXT: Record<StrategyBattle['verdict'], string> = {
  SALE_ADELANTE: 'Sale adelante',
  CARA_O_CRUZ: 'A cara o cruz',
  SIGUE_ATRAS: 'Sigue atrás',
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
      <div className="battle__main">
        <div className="battle__gap">
          <span className="battle__gapv num">{fmt(Math.abs(battle.gapAfter))}</span>
          <span className="battle__gapl">
            gap proyectado
            <br />
            en {battle.responseLaps} vueltas
          </span>
        </div>

        <div className="battle__cars">
          {[battle.chaser, battle.leader].map((code, i) => (
            <span className="battle__car" key={code}>
              <span className="battle__bar" style={{ background: teamColor(code) }} />
              <span className="battle__code">{code}</span>
              <span className="battle__role">{i === 0 ? 'para' : 'responde'}</span>
            </span>
          ))}
        </div>

        <div className="battle__odds">
          <span className="battle__pct num">{pct(battle.probability)}</span>
          <span className="battle__verdict">{VERDICT_TEXT[battle.verdict]}</span>
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
