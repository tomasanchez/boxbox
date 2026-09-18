/**
 * Amenaza de undercut, con la forma de la gráfica «Undercut Threat».
 *
 * Es el **duelo de estrategia dado vuelta**. La tarjeta de al lado contesta la
 * pregunta del que viene de atrás —«si paro ahora, ¿salgo adelante?»—; ésta
 * contesta la del que va adelante, que es la que discute su propio muro: **«el
 * de atrás me puede undercutear, ¿cuánto peligro corro?»**.
 *
 * El número es el mismo `solveBattle` con los mismos insumos: no hay modelo
 * nuevo. Lo que cambia es de quién es el problema, y eso cambia qué hacés con
 * el número —el perseguidor decide si ataca, el de adelante decide si se cubre
 * parando primero—. Por eso la probabilidad se rotula como amenaza y no como
 * éxito: el 78% que allá era una buena noticia, acá es la mala.
 *
 * El auto del que habla es el **focal** (ADR-007), no el que más peligro corre:
 * la tarjeta acompaña al piloto elegido aunque no esté pasando nada, y cuando
 * no pasa nada lo dice. Una tarjeta que salta de auto en auto no se puede
 * seguir, y una que desaparece deja al usuario sin saber si no hay amenaza o si
 * se rompió algo.
 */

import { IN_RANGE_S, type NoThreatReason, type ThreatLevel, type ThreatView } from './battle'
import { fmt, pct } from './format'
import { GRID } from './data'

const LEVEL_TEXT: Record<ThreatLevel, string> = {
  ALTA: 'amenaza alta',
  MEDIA: 'a cara o cruz',
  BAJA: 'amenaza baja',
}

/**
 * Qué hacer con el número, dicho en una línea.
 *
 * Es la lectura del modelo, no una recomendación nueva: la probabilidad es de
 * que el de atrás salga adelante si para, así que cubrirse es parar primero.
 */
const LEVEL_ADVICE: Record<ThreatLevel, string> = {
  ALTA: 'se cubre parando primero',
  MEDIA: 'el volado lo decide la parada',
  BAJA: 'puede estirar la tanda',
}

function idleText(reason: NoThreatReason, chaser: string | null, gap: number | null): string {
  switch (reason) {
    case 'formation':
      return 'pelotón formado'
    case 'out':
      return 'fuera de carrera'
    case 'nobody-behind':
      return 'nadie atrás: va último'
    case 'chaser-no-window':
      // «no va a parar» seria mentira: casi todos paran, y el plan lo dice. Lo
      // que la ventana sostiene es que no esta POR parar ahora, que es otra
      // cosa y es la que importa para un undercut.
      return `${chaser ?? 'el de atrás'} no está en ventana: no está por parar`
    case 'chaser-far':
      return `${chaser ?? 'el de atrás'} a ${fmt(gap ?? 0, 1)} s, fuera de rango (${fmt(
        IN_RANGE_S,
        1,
      )} s)`
    case 'no-projection':
      return 'sin ventana proyectada en este origen'
  }
}

function teamColor(code: string): string {
  return GRID.find((d) => d.code === code)?.teamColor ?? '#8f8b88'
}

export function UndercutThreatCard({
  threat,
  driver,
  open,
  onToggle,
}: {
  threat: ThreatView
  /** El auto focal: de quién es el peligro que se está midiendo. */
  driver: string
  open: boolean
  onToggle: () => void
}) {
  const level = threat.kind === 'live' ? threat.level : null

  return (
    <div className={`ut ut--${level ?? 'idle'}`}>
      <div className="ut__head">
        <span className="ut__title">Amenaza de undercut</span>
        {/*
         * Sólo el código. «desde adelante» no entra sin recortarse en la
         * cabecera angosta, y recortado se lee peor que no estar: el punto de
         * vista queda dicho en el pie, con espacio para decirlo entero.
         */}
        <span className="ut__sub">
          {driver}
          {!open && threat.kind === 'live' ? ` · ${pct(threat.battle.probability)}` : null}
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
        threat.kind === 'live' ? (
          <div className="ut__body">
            <div className="ut__gauge">
              {/* El nivel va escrito además de teñido: el color solo no alcanza. */}
              <span className="ut__level">{LEVEL_TEXT[threat.level]}</span>
              <span className="ut__pct num">{pct(threat.battle.probability)}</span>
            </div>

            <div className="ut__who">
              <span className="ut__bar" style={{ background: teamColor(threat.battle.chaser) }} />
              <span className="ut__code">{threat.battle.chaser}</span>
              <span className="ut__gap num">a {fmt(threat.battle.gapNow)} s</span>
              {threat.battle.chaserWindow ? (
                <span className="ut__win">
                  ventana {threat.battle.chaserWindow.opensLap}–
                  {threat.battle.chaserWindow.closesLap}
                  {threat.chaserWindowOpen ? ' · abierta' : ' · entrando'}
                </span>
              ) : null}
            </div>

            <div className="ut__math">
              Si {threat.battle.chaser} para ahora, en {threat.battle.responseLaps} vueltas queda a{' '}
              <span className="num">{fmt(threat.battle.gapAfter, 2, true)} s</span> — recupera{' '}
              <span className="num">{fmt(threat.battle.perLapGain, 2)} s</span> por vuelta.
            </div>

            <div className="ut__foot">
              Riesgo de <strong>{driver}</strong>, que va adelante: {LEVEL_ADVICE[threat.level]}.
            </div>
          </div>
        ) : (
          <div className="ut__body ut__body--idle">
            <span className="ut__idle">{idleText(threat.reason, threat.chaser, threat.gapBehind)}</span>
            <div className="ut__foot">
              {threat.reason === 'no-projection' ? (
                /*
                 * El export pre-carrera trae el PLAN del algoritmo, no la
                 * ventana de `pit_window()`. Sin ventana no se puede decir si
                 * el de atrás está por parar, y decir que «no va a parar»
                 * sería falso: tiene plan y para. Se declara el hueco.
                 */
                <>
                  Desde la largada el export trae el <strong>plan</strong> de cada auto, no la
                  ventana proyectada. Sin ventana no hay con qué decidir si el de atrás está por
                  parar. Las paradas del plan están en la torre.
                </>
              ) : (
                <>
                  Riesgo de <strong>{driver}</strong>, que va adelante. Hace falta que el de atrás
                  esté <strong>en ventana</strong> y <strong>en rango</strong>: sin las dos cosas no
                  hay undercut que temer.
                </>
              )}
            </div>
          </div>
        )
      ) : null}
    </div>
  )
}
