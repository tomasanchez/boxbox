/**
 * El intro: cómo evoluciona la población del algoritmo genético (ADR-005).
 *
 * La tarjeta cuenta una búsqueda sobre las 26 generaciones que el buscador
 * registró, y lo hace en dos planos que comparten la misma línea de tiempo:
 *
 *   **qué encontró**  el mejor plan de la generación, escrito y dibujado como
 *            tandas. Es el plano que convierte la animación en una explicación:
 *            «el valor subió en la generación 12» es un gráfico, «en la
 *            generación 12 pasó de dos paradas a tres» es una explicación.
 *
 *   **cómo lo buscó**  el mejor valor generación a generación —una escalera que
 *            sube cuando aparece algo mejor y se queda quieta cuando no— y cómo
 *            se reparte la población entre cantidades de paradas, que al
 *            principio está desparramada y al final se apila en una sola.
 *
 * Los cambios de plan son **pocos y ahí está todo lo interesante**: siete en
 * veinticinco generaciones para NOR, uno solo para medio pelotón, ninguno para
 * OCO y ALB. Un dato raro no se puede mostrar igual que uno frecuente, así que
 * el cambio se anuncia por cuatro vías a la vez y ninguna es sólo color:
 *
 *   1. la animación **se demora** en la generación donde cambió (`DWELL_MS`),
 *      que es la única forma de que un evento de 190 ms se pueda leer;
 *   2. la fila del plan **cambia de texto** —«plan nuevo» en vez de «desde
 *      GEN nn»— y dice cuánto ganó;
 *   3. las **tandas se redibujan**, que es el cambio de forma que se ve incluso
 *      de reojo;
 *   4. queda una **marca en la escalera** y una ficha nueva en la tira de abajo.
 *
 * Y la tira de fichas existe para el otro caso: el que quiere la historia
 * entera de un vistazo y no quiere volver a animarla. Se revela hasta la
 * generación más lejana que se haya alcanzado, así que durante la primera
 * corrida no adelanta el final, y una vez que terminó se queda completa aunque
 * se vuelva atrás con la barra. Cada ficha es un botón: lleva a esa generación.
 *
 * Tres advertencias que la tarjeta se toma en serio:
 *
 *  - El reparto de la población es **convergencia de la búsqueda**, no
 *    probabilidad de la carrera. Confundirlos fue el error que originó esta
 *    vista, así que la palabra «convergencia» va en el rótulo y no al pie.
 *
 *  - Las cantidades de paradas **no son 0..4**. El reparador agrega una parada
 *    cuando el plan no cumple el reglamento, así que hay generaciones con
 *    cinco. Las claves se leen del dato, nunca se asumen.
 *
 *  - El valor del eje vertical no es comparable entre autos: para el que puede
 *    sumar son puntos esperados y para el resto es el puesto de llegada en
 *    negativo, porque el objetivo es adaptativo. Por eso la escala se arma con
 *    el mínimo y el máximo **de este auto** y los dos extremos van escritos.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { COMPOUND_COLOR, COMPOUND_LETTER, RACE } from './data'
import { fmt } from './format'
import { PRERACE, historyStopKeys, objectiveNote, planChanges, stintsOf, stopKeys } from './prerace'
import type { PreRaceCar } from './prerace'
import { Panel } from './ui'

/** Milisegundos por generación cuando no pasa nada. */
const STEP_MS = 190

/**
 * Lo que se demora en una generación donde el mejor plan cambió.
 *
 * No es adorno: a 190 ms un cambio de plan es un parpadeo, y los cambios son
 * justamente lo que hay que ver. Demorarse es pacing, no dato —el eje, la
 * escalera y las fichas siguen diciendo exactamente lo que dice el archivo—, y
 * es lo único que hace legible un evento que ocurre siete veces en veinticinco
 * generaciones. La corrida entera pasa de 4,8 s a 7,4 s para NOR y a 5,1 s para
 * un auto que no cambia nunca.
 */
const DWELL_MS = 520

/**
 * Un color por cantidad de paradas, de la paleta del panel.
 *
 * El color no alcanza solo: cada tramo lleva el número adentro cuando entra, y
 * la referencia de abajo repite la cifra. Quien no distinga los tonos igual lee
 * cuántas paradas es cada franja.
 */
const STOP_COLOR: Record<number, string> = {
  1: '#3671c6',
  2: '#35c46f',
  3: '#f5c518',
  4: '#ec3013',
  5: '#c9c5c2',
}

const W = 300
const H_BEST = 76
const H_POP = 74
const PAD_X = 6

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  )
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!query) return
    const update = () => setReduced(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return reduced
}

/** Dos cifras siempre: «GEN 4» y «GEN 15» tienen que alinear. */
function gen(value: number): string {
  return String(value).padStart(2, '0')
}

/**
 * La tarjeta se monta de nuevo con cada piloto —`key={car.code}` arriba— así que
 * el estado inicial ya es el correcto y no hace falta un efecto que lo reinicie:
 * la búsqueda arranca sola en la generación cero cada vez que se elige otro
 * auto, porque es la pieza didáctica de la vista y tiene que verse sin apretar
 * nada.
 *
 * Con movimiento reducido no arranca sola y queda en el resultado final, que es
 * lo que alguien que pidió menos animación quiere ver. Ahí la tira de fichas
 * aparece completa de entrada: si no se anima, la historia tiene que estar
 * escrita.
 */
export function EvolutionCard({ car }: { car: PreRaceCar }) {
  const reduced = useReducedMotion()
  const last = car.history.length - 1

  /**
   * Dónde está la animación y **hasta dónde llegó alguna vez**.
   *
   * Las dos cosas van en un solo estado porque se actualizan juntas y no pueden
   * quedar desfasadas ni por un cuadro. `reached` es una marca de agua: la tira
   * de fichas se revela hasta ahí, así que vuelve atrás con la barra sin borrar
   * lo que ya se vio, y no adelanta lo que todavía no ocurrió.
   */
  const [step, setStep] = useState(() => ({
    at: reduced ? last : 0,
    reached: reduced ? last : 0,
  }))
  const [playing, setPlaying] = useState(!reduced)

  const shown = Math.min(step.at, last)
  const reached = Math.min(step.reached, last)
  const running = playing && shown < last

  const goTo = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(next, last))
      setStep((current) => ({ at: clamped, reached: Math.max(current.reached, clamped) }))
    },
    [last],
  )

  const entry = car.history[shown]

  /*
   * Los momentos en los que la búsqueda cambió de mejor plan, con la semilla de
   * la generación cero a la cabeza. Se comparan planes y no valores: ver
   * `planChanges`.
   */
  const changes = useMemo(() => planChanges(car), [car])
  const changeAt = useMemo(() => new Set(changes.map((change) => change.index)), [changes])

  // Siempre hay uno: la generación cero entra en la lista por definición.
  const current = changes.findLast((change) => change.index <= shown) ?? changes[0]
  const isNew = changeAt.has(shown)

  // Un temporizador por generación, no un intervalo que sigue girando: al llegar
  // a la última no queda nada corriendo de fondo. La demora depende de si en
  // esta generación cambió el plan, que es lo que hay que alcanzar a leer.
  useEffect(() => {
    if (!running) return
    const timer = window.setTimeout(() => goTo(shown + 1), changeAt.has(shown) ? DWELL_MS : STEP_MS)
    return () => window.clearTimeout(timer)
  }, [running, shown, changeAt, goTo])

  const values = car.history.map((h) => h.best)
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || 1

  /*
   * Hay autos cuyo mejor plan aparece en la generación cero y no se mueve más
   * —OCO es uno—. Ahí no hay escala que armar: la línea va al medio y se dice
   * que nunca mejoró, en vez de dibujarla pegada al piso, que se lee como si el
   * gráfico estuviera vacío.
   */
  const flat = high === low
  const x = (index: number) => PAD_X + (index / last) * (W - PAD_X * 2)
  const y = (value: number) =>
    flat ? H_BEST / 2 : H_BEST - 10 - ((value - low) / span) * (H_BEST - 22)

  // Escalera, no recta: el mejor valor se sostiene hasta que aparece uno mejor.
  // Interpolar entre generaciones dibujaría mejoras que nunca ocurrieron.
  const steps: string[] = []
  for (let i = 0; i <= shown; i += 1) {
    const value = car.history[i].best
    steps.push(i === 0 ? `M ${x(0)} ${y(value)}` : `L ${x(i)} ${y(car.history[i - 1].best)}`)
    if (i > 0) steps.push(`L ${x(i)} ${y(value)}`)
  }

  const keys = historyStopKeys(car)
  const colWidth = (W - PAD_X * 2) / car.history.length
  const improved = shown > 0 && entry.best > car.history[shown - 1].best

  /*
   * Qué hizo la POBLACIÓN cuando el mejor no se movió.
   *
   * La línea plana se leía como «el algoritmo no hizo nada», y no es cierto: el
   * mejor individuo puede venir sembrado desde la generación 0 mientras el resto
   * converge hacia él. Está dibujado en las barras de abajo, pero un gráfico que
   * hay que interpretar no contesta la pregunta que el usuario se hace mirando la
   * línea. Esto lo dice con palabras.
   */
  const spread = (bars: Record<string, number>) =>
    Object.values(bars).filter((share) => share >= 0.05).length
  const settled = car.history[car.history.length - 1].stop_distribution
  const opening = spread(car.history[0].stop_distribution)
  const closing = spread(settled)
  // Por PESO y no por cantidad: `stopKeys` ordena por número de paradas, así que
  // tomarle el primero daría el reparto más chico y no el que la población eligió.
  const winner = stopKeys(settled).reduce((best, key) =>
    (settled[String(key)] ?? 0) > (settled[String(best)] ?? 0) ? key : best,
  )
  const settling =
    opening > closing
      ? `· la población se concentró de ${opening} repartos a ${closing}, en ${winner} paradas`
      : '· y la población tampoco se movió'

  /*
   * Las tandas del plan del momento, en la misma escala que la tarjeta «Plan
   * recomendado»: sobre las 72 vueltas de la carrera y no sobre las 71 que el
   * plan cubre. Así la barra que la búsqueda va encontrando termina midiendo
   * exactamente lo mismo que la barra de al lado, que es el plan que sale.
   */
  const stints = stintsOf(current.plan)

  const switches = changes.length - 1

  return (
    <Panel
      title="Cómo lo encontró el algoritmo"
      note={`${PRERACE.search.population} planes por generación · ${PRERACE.search.generations} generaciones · ${PRERACE.search.draws.toLocaleString('es-AR')} carreras sorteadas por evaluación`}
      className="panel--evo"
      fill
    >
      <div className="evo__head">
        <div>
          <span className="evo__gen num">GEN {gen(entry.generation)}</span>
          <span className="evo__of num"> / {PRERACE.search.generations}</span>
        </div>
        <div className="evo__best">
          <span className="evo__bestv num">{fmt(entry.best, 3, true)}</span>
          <span className="evo__bestl">
            mejor valor{' '}
            {flat
              ? `· nunca mejoró: el mejor plan ya estaba en la generación 0 ${settling}`
              : improved
                ? '· mejoró'
                : shown === 0
                  ? '· inicial'
                  : '· sin cambio'}
          </span>
        </div>
        <div className="evo__controls">
          <button
            type="button"
            className="scenario"
            onClick={() => {
              setStep({ at: 0, reached: 0 })
              setPlaying(true)
            }}
          >
            ▶ Volver a correr
          </button>
          <button
            type="button"
            className="scenario"
            aria-pressed={running}
            onClick={() => setPlaying((v) => !v)}
            disabled={shown >= last}
          >
            {running ? '❚❚ Pausa' : 'Seguir'}
          </button>
        </div>
      </div>

      {/*
       * El plan del momento y la historia entera, en un solo bloque: son la
       * misma cosa contada dos veces —lo que hay ahora y por dónde se llegó—, y
       * juntarlas ahorra el hueco que el panel no tiene.
       *
       * `key` por plan en la caja de adentro: al cambiar el plan se monta de
       * nuevo y con eso vuelve a arrancar la animación de aviso, que en CSS se
       * apaga sola si el sistema pidió menos movimiento. Las fichas quedan
       * afuera de esa caja para que no parpadeen con cada cambio. Las barras
       * **no** hacen transición de ancho: interpolar dibujaría tandas
       * intermedias que la búsqueda nunca evaluó, que es la misma razón por la
       * que la escalera es escalera.
       */}
      <div className="evo__plan">
        <div className={`evo__planbox${isNew ? ' evo__planbox--new' : ''}`} key={current.plan}>
          <div className="evo__planhead">
            <span className="evo__planseq num">{current.plan}</span>
            <span className="evo__planstops">
              {current.stops} parada{current.stops === 1 ? '' : 's'}
            </span>
            <span className={`evo__since${isNew ? ' evo__since--new' : ''}`}>
              {isNew
                ? shown === 0
                  ? 'semilla heurística'
                  : `plan nuevo ${fmt(current.gain, 3, true)}`
                : `desde GEN ${gen(current.generation)}`}
            </span>
          </div>
          <div
            className="evo__bar"
            role="img"
            aria-label={`Plan de la generación ${entry.generation}: ${stints
              .map((stint) => `${stint.compound} ${stint.laps} vueltas`)
              .join(', ')}`}
          >
            {stints.map((stint, index) => (
              <span
                className="evo__stint"
                key={`${stint.compound}-${index}`}
                style={{
                  width: `${(stint.laps / RACE.totalLaps) * 100}%`,
                  background: COMPOUND_COLOR[stint.compound],
                }}
                title={`${stint.compound}: vueltas ${stint.fromLap} a ${stint.fromLap + stint.laps - 1}`}
              >
                {COMPOUND_LETTER[stint.compound]}
                {stint.laps}
              </span>
            ))}
          </div>
        </div>

        {/*
         * La tira se revela hasta `reached` y no hasta `shown`: durante la
         * primera corrida no adelanta el final, y cuando terminó se queda
         * entera aunque se vuelva atrás con la barra. El rótulo va **adentro**
         * de la misma fila que las fichas para no gastar un renglón en un panel
         * donde el alto es el recurso escaso.
         */}
        <div className="evo__chips">
          <span className="evo__storyl">
            {switches === 0
              ? 'El mejor plan nunca cambió:'
              : `${switches} cambio${switches === 1 ? '' : 's'} en ${last} generaciones:`}
          </span>
          {changes.map((change) =>
            change.index > reached ? null : (
              <button
                type="button"
                key={change.index}
                className={`evo__chip${change.index === current.index ? ' evo__chip--now' : ''}${
                  change.index > shown ? ' evo__chip--ahead' : ''
                }`}
                aria-current={change.index === current.index ? 'true' : undefined}
                title={`Generación ${change.generation}: ${change.plan}, ${change.stops} paradas, valor ${fmt(change.best, 3, true)}`}
                aria-label={`Ir a la generación ${change.generation}: plan ${change.plan}, ${change.stops} paradas, valor ${fmt(change.best, 3, true)}${
                  change.index === 0 ? ', la semilla' : `, ganó ${fmt(change.gain, 3, true)}`
                }`}
                onClick={() => {
                  setPlaying(false)
                  goTo(change.index)
                }}
              >
                <span className="evo__chipg num">G{gen(change.generation)}</span>
                <span className="num">{change.plan}</span>
              </button>
            ),
          )}
        </div>
      </div>

      <label className="evo__scrub">
        <span className="evo__scrubl">Generación</span>
        <input
          type="range"
          className="playback__scrub"
          min={0}
          max={last}
          value={shown}
          onChange={(event) => {
            setPlaying(false)
            goTo(Number(event.target.value))
          }}
        />
      </label>

      <div className="evo__plot">
        <svg
          viewBox={`0 0 ${W} ${H_BEST}`}
          preserveAspectRatio="none"
          className="evo__svg"
          role="img"
          aria-label={`Mejor valor por generación. Generación ${entry.generation}: ${fmt(entry.best, 3, true)} con el plan ${current.plan}`}
        >
          <line x1={PAD_X} y1={y(high)} x2={W - PAD_X} y2={y(high)} className="evo__rule" />
          {flat ? null : (
            <line x1={PAD_X} y1={y(low)} x2={W - PAD_X} y2={y(low)} className="evo__rule" />
          )}
          {/* Dónde cambió el plan. Son los escalones de la escalera —en este
              export mejorar y cambiar de plan son el mismo evento— y quedan
              marcados para que se vea de un vistazo que fueron pocos y
              temprano. */}
          {changes.map((change) =>
            change.index > shown ? null : (
              <line
                key={change.index}
                x1={x(change.index)}
                y1={0}
                x2={x(change.index)}
                y2={H_BEST}
                className="evo__mark"
              />
            ),
          )}
          <path d={steps.join(' ')} className="evo__line" />
          {/* Marca vertical en vez de un punto: el gráfico se estira con el
              panel y un círculo saldría ovalado. */}
          <line x1={x(shown)} y1={0} x2={x(shown)} y2={H_BEST} className="evo__now" />
        </svg>
        <span className={`evo__axis num evo__axis--${flat ? 'mid' : 'top'}`}>
          {fmt(high, 3, true)}
        </span>
        {flat ? null : (
          <span className="evo__axis evo__axis--bottom num">{fmt(low, 3, true)}</span>
        )}
      </div>

      <div className="evo__label">
        Reparto de la población entre cantidades de paradas
        <strong> — convergencia de la búsqueda, no probabilidad de la carrera</strong>
      </div>

      <div className="evo__plot evo__plot--pop">
        <svg
          viewBox={`0 0 ${W} ${H_POP}`}
          preserveAspectRatio="none"
          className="evo__svg"
          role="img"
          aria-label={`Reparto de la población en la generación ${entry.generation}: ${stopKeys(
            entry.stop_distribution,
          )
            .map((k) => `${k} paradas ${Math.round(entry.stop_distribution[String(k)] * 100)}%`)
            .join(', ')}`}
        >
          {car.history.map((h, index) => {
            const drawn = index <= shown
            let offset = 0
            return (
              <g key={h.generation}>
                {drawn ? (
                  keys.map((key) => {
                    const share = h.stop_distribution[String(key)] ?? 0
                    if (share <= 0) return null
                    const height = share * H_POP
                    const top = offset
                    offset += height
                    return (
                      <rect
                        key={key}
                        x={PAD_X + index * colWidth + 0.6}
                        y={top}
                        width={Math.max(colWidth - 1.2, 0.8)}
                        height={height}
                        fill={STOP_COLOR[key] ?? '#8f8b88'}
                        opacity={index === shown ? 1 : 0.62}
                      />
                    )
                  })
                ) : (
                  <rect
                    x={PAD_X + index * colWidth + 0.6}
                    y={0}
                    width={Math.max(colWidth - 1.2, 0.8)}
                    height={H_POP}
                    className="evo__pending"
                  />
                )}
              </g>
            )
          })}
        </svg>
      </div>

      <div className="evo__legend">
        {keys.map((key) => (
          <span className="evo__key" key={key}>
            <span className="evo__swatch" style={{ background: STOP_COLOR[key] ?? '#8f8b88' }} />
            {key} parada{key === 1 ? '' : 's'}
            <span className="evo__keyv num">
              {Math.round((entry.stop_distribution[String(key)] ?? 0) * 100)}%
            </span>
          </span>
        ))}
      </div>

      <p className="footnote evo__foot">
        {objectiveNote(car)} El valor del eje está en esas unidades y no se compara entre autos.
      </p>
    </Panel>
  )
}
