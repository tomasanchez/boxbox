/**
 * Ventana de boxes, con la forma de la gráfica «Pit Window».
 *
 * Hasta acá la ventana existía sólo como una columna angosta de la torre. Es el
 * insumo del que cuelga medio panel —`battle.ts` no ofrece un duelo si el
 * perseguidor no está en ventana— y no tenía dónde leerse entera.
 *
 * ## Lo que esta tarjeta dice, y lo que deliberadamente NO dice
 *
 * La ventana es **cuándo el auto PODRÍA parar**, proyectada por `pit_window()`
 * sobre el desgaste medido. El **plan** es cuándo VA A parar. Son dos cosas y
 * la vista ya se cuidó una vez de no mezclarlas: la torre muestra una o la otra
 * según de dónde arranque la carrera, nunca las dos en la misma columna.
 *
 * Acá se mantiene: la tarjeta habla de la ventana y sólo de la ventana, y lo
 * dice con todas las letras al pie. El plan tiene su propia tarjeta.
 *
 * ## El `—` tiene tres motivos y la tarjeta dice cuál
 *
 * No es un hueco de datos, y no siempre es lo mismo:
 *
 *   1. la goma está plana o todavía mejorando, así que no hay cruce que
 *      anticipar — cerca de la mitad de la parrilla está así a mitad de carrera;
 *   2. el auto ya paró, y la ventana que traía era para esa parada;
 *   3. en este origen **no se proyectó ninguna ventana**. Desde la largada
 *      `PRERACE_GRID` pone `pitWindow: null` en los veintidós porque el export
 *      pre-carrera trae el plan del algoritmo y no la salida de `pit_window()`.
 *
 * Los tres se ven igual y significan cosas distintas. El tercero es un hueco de
 * dato nuestro y explicarlo como el primero sería afirmar algo sobre la goma de
 * ese auto que en ese origen nadie midió.
 */

import { RACE } from './data'
import { PALETTE } from './theme'
import { windowState } from './pitwindow'
import type { DriverState } from './types'

/**
 * Rótulo grande según la fase, más una cola chica con la cuenta de vueltas.
 *
 * Van separados porque la cuenta significa distinto en cada fase —cuánto falta
 * para que abra, cuánto queda antes de que cierre, hace cuánto cerró— y
 * pegarle una «v» al rótulo daba «ABIERTA v», que no es ninguna de las tres.
 *
 * El estado nunca es sólo color: siempre va escrito.
 */
function headline(
  phase: ReturnType<typeof windowState>['phase'],
  laps: number | null,
): { text: string; tone: string; tail: string } {
  switch (phase) {
    case 'pending':
      return {
        text: 'ABRE EN',
        tone: PALETTE.txt1,
        tail: `${laps} ${laps === 1 ? 'vuelta' : 'vueltas'}`,
      }
    case 'open':
      // `laps` es cuánto queda, así que 0 es la última vuelta útil, no «cerrada».
      return {
        text: 'ABIERTA',
        tone: PALETTE.green,
        tail: laps === 0 ? 'última vuelta' : `cierra en ${laps} v`,
      }
    case 'closed':
      return { text: 'CERRADA', tone: PALETTE.red, tail: `hace ${laps} v` }
    default:
      return { text: 'SIN VENTANA', tone: PALETTE.txt3, tail: '' }
  }
}

export function PitWindowCard({
  car,
  lap,
  openNow,
  windowsProjected,
  running,
  stopsMade,
  lastStopLap,
  open,
  onToggle,
}: {
  /** El auto focal: el mismo que manda en el mapa y en la torre (ADR-007). */
  car: DriverState | undefined
  lap: number
  /** Cuántos autos en pista tienen la ventana abierta en esta vuelta. */
  openNow: number
  /**
   * Si este origen trae ventanas proyectadas.
   *
   * Desde la largada **no**: `PRERACE_GRID` pone `pitWindow: null` en los
   * veintidós porque el export pre-carrera trae el plan del algoritmo y no la
   * salida de `pit_window()`. Sin esta bandera la tarjeta explicaba ese `null`
   * como «la goma está plana», que es una afirmación sobre el auto que en ese
   * origen nadie midió.
   */
  windowsProjected: boolean
  /** Cuántos siguen en carrera, para que `openNow` tenga contra qué leerse. */
  running: number
  /** Paradas que este auto ya hizo en el sorteo en curso. */
  stopsMade: number
  /** Vuelta de la última parada hecha, o `null` si no hizo ninguna. */
  lastStopLap: number | null
  open: boolean
  onToggle: () => void
}) {
  const { totalLaps } = RACE
  const state = car ? windowState(car, lap) : { phase: 'none' as const, window: null, laps: null }
  const head = headline(state.phase, state.laps)
  const w = state.window

  return (
    <div className={`pw pw--${state.phase}`}>
      <div className="pw__head">
        <span className="pw__title">Ventana de boxes</span>
        {/*
         * Minimizada la tarjeta se queda en esta línea, así que el resumen
         * tiene que llevar también la cuenta de vueltas: sin ella quedaba
         * «NOR · abre en», que es una frase cortada al medio.
         */}
        <span className="pw__sub">
          {car ? car.code : '—'}
          {open ? null : ` · ${head.text.toLowerCase()}${head.tail ? ` ${head.tail}` : ''}`}
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
        <div className="pw__body">
          <div className="pw__state">
            <span className="pw__phase" style={{ color: head.tone }}>
              {head.text}
            </span>
            <span className="pw__range num">{w ? `${w.opensLap}–${w.closesLap}` : '—'}</span>
          </div>

          {head.tail ? <div className="pw__tail num">{head.tail}</div> : null}

          {/* Misma línea de tiempo que la torre: 1 a la última vuelta, la
              ventana sombreada y la vuelta actual en rojo. Lleva etiqueta
              propia porque la marca roja es la única que dice en qué vuelta
              estamos, y el color solo no la comunica. */}
          <div
            className="pw__track"
            role="img"
            aria-label={
              w
                ? `Ventana de la vuelta ${w.opensLap} a la ${w.closesLap}. Vuelta actual ${lap} de ${totalLaps}.`
                : `Sin ventana proyectada. Vuelta actual ${lap} de ${totalLaps}.`
            }
          >
            {w ? (
              <span
                className="pw__band"
                style={{
                  left: `${(w.opensLap / totalLaps) * 100}%`,
                  width: `${((w.closesLap - w.opensLap) / totalLaps) * 100}%`,
                }}
              />
            ) : null}
            <span className="pw__now" style={{ left: `${(lap / totalLaps) * 100}%` }} />
          </div>

          {/*
           * Sólo los extremos. La vuelta actual ya está marcada en rojo sobre
           * la línea: escribirla acá al medio la ponía en el centro visual
           * cuando la vuelta 30 de 72 cae al 41%, y el rótulo contradecía a la
           * marca que tenía al lado.
           */}
          <div className="pw__scale num">
            <span>V1</span>
            <span>V{totalLaps}</span>
          </div>

          <div className="pw__note">
            {state.phase === 'none' ? (
              /*
               * Tres motivos distintos para el mismo `—`, y sólo uno de ellos
               * es una afirmación sobre la goma. Se elige el que corresponde en
               * vez de explicar los tres con el más vistoso.
               */
              !windowsProjected ? (
                <>
                  En este origen <strong>no se proyectó ninguna ventana</strong>: el export trae el
                  plan del algoritmo, que es otra cosa.
                </>
              ) : stopsMade > 0 ? (
                <>
                  Ya paró {stopsMade === 1 ? 'una vez' : `${stopsMade} veces`}
                  {lastStopLap != null ? ` (última en la V${lastStopLap})` : null}. La ventana que
                  traía era para esa parada y no hay otra proyectada.
                </>
              ) : (
                <>La goma está plana o todavía mejorando: no hay cruce que anticipar.</>
              )
            ) : (
              <>
                <strong className="num">{openNow}</strong> de {running} en pista con la ventana
                abierta ahora.
              </>
            )}
          </div>

          {/*
           * La advertencia va en la tarjeta y no sólo en el código: es
           * exactamente la confusión que esta vista ya tuvo que desarmar una vez.
           */}
          <div className="pw__foot">
            Cuándo <strong>podría</strong> parar, proyectado por el modelo. No es el plan, que es
            cuándo <strong>va a</strong> parar.
          </div>
        </div>
      ) : null}
    </div>
  )
}
