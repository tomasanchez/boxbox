/**
 * El intro: cómo evoluciona la población del algoritmo genético (ADR-005).
 *
 * Son dos gráficos sobre la misma línea de tiempo —las 26 generaciones que el
 * buscador registró— y se dibujan generación a generación para que se vea el
 * mecanismo, que es lo que se evalúa en la materia:
 *
 *   arriba   el **mejor valor** de cada generación. Es una escalera: sube
 *            cuando aparece un plan mejor y se queda quieta cuando no. Los
 *            escalones largos del final son la convergencia.
 *
 *   abajo    cómo se **reparte la población** entre cantidades de paradas. Al
 *            principio está desparramada, después se apila en una sola. Eso es
 *            la búsqueda decidiéndose.
 *
 * Dos advertencias que la tarjeta se toma en serio:
 *
 *  - Ese reparto es **convergencia de la búsqueda**, no probabilidad de la
 *    carrera. Confundirlos fue el error que originó esta vista, así que la
 *    palabra «convergencia» va en el rótulo y no en una nota al pie.
 *
 *  - Las cantidades de paradas **no son 0..4**. El reparador agrega una parada
 *    cuando el plan no cumple el reglamento, así que hay generaciones con cinco.
 *    Las claves se leen del dato, nunca se asumen.
 *
 * El valor del eje vertical no es comparable entre autos: para el que puede
 * sumar son puntos esperados y para el resto es el puesto de llegada en
 * negativo, porque el objetivo es adaptativo. Por eso la escala se arma con el
 * mínimo y el máximo **de este auto** y los dos extremos van escritos.
 */

import { useEffect, useState } from 'react'
import { fmt } from './format'
import { PRERACE, historyStopKeys, objectiveNote, stopKeys } from './prerace'
import type { PreRaceCar } from './prerace'
import { Panel } from './ui'

/** Milisegundos por generación. 26 generaciones entran en algo más de cinco segundos. */
const STEP_MS = 210

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

/**
 * La tarjeta se monta de nuevo con cada piloto —`key={car.code}` arriba— así que
 * el estado inicial ya es el correcto y no hace falta un efecto que lo reinicie:
 * la búsqueda arranca sola en la generación cero cada vez que se elige otro
 * auto, porque es la pieza didáctica de la vista y tiene que verse sin apretar
 * nada.
 *
 * Con movimiento reducido no arranca sola y queda en el resultado final, que es
 * lo que alguien que pidió menos animación quiere ver.
 */
export function EvolutionCard({ car }: { car: PreRaceCar }) {
  const reduced = useReducedMotion()
  const last = car.history.length - 1
  const [generation, setGeneration] = useState(() => (reduced ? last : 0))
  const [playing, setPlaying] = useState(!reduced)

  const shown = Math.min(generation, last)
  const running = playing && shown < last

  // Un temporizador por generación, no un intervalo que sigue girando: al llegar
  // a la última no queda nada corriendo de fondo.
  useEffect(() => {
    if (!running) return
    const timer = window.setTimeout(() => setGeneration(shown + 1), STEP_MS)
    return () => window.clearTimeout(timer)
  }, [running, shown])

  const entry = car.history[shown]
  const values = car.history.map((h) => h.best)
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || 1

  const x = (index: number) => PAD_X + (index / last) * (W - PAD_X * 2)
  const y = (value: number) => H_BEST - 10 - ((value - low) / span) * (H_BEST - 22)

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

  return (
    <Panel
      title="Cómo lo encontró el algoritmo"
      note={`${PRERACE.search.population} planes por generación · ${PRERACE.search.generations} generaciones · ${PRERACE.search.draws.toLocaleString('es-AR')} carreras sorteadas por evaluación`}
      fill
    >
      <div className="evo__head">
        <div>
          <span className="evo__gen num">
            GEN {String(entry.generation).padStart(2, '0')}
          </span>
          <span className="evo__of num"> / {PRERACE.search.generations}</span>
        </div>
        <div className="evo__best">
          <span className="evo__bestv num">{fmt(entry.best, 3, true)}</span>
          <span className="evo__bestl">
            mejor valor {improved ? '· mejoró' : shown === 0 ? '· inicial' : '· sin cambio'}
          </span>
        </div>
        <div className="evo__controls">
          <button
            type="button"
            className="scenario"
            onClick={() => {
              setGeneration(0)
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
            setGeneration(Number(event.target.value))
          }}
        />
      </label>

      <div className="evo__plot">
        <svg
          viewBox={`0 0 ${W} ${H_BEST}`}
          preserveAspectRatio="none"
          className="evo__svg"
          role="img"
          aria-label={`Mejor valor por generación. Generación ${entry.generation}: ${fmt(entry.best, 3, true)}`}
        >
          <line x1={PAD_X} y1={y(high)} x2={W - PAD_X} y2={y(high)} className="evo__rule" />
          <line x1={PAD_X} y1={y(low)} x2={W - PAD_X} y2={y(low)} className="evo__rule" />
          <path d={steps.join(' ')} className="evo__line" />
          {/* Marca vertical en vez de un punto: el gráfico se estira con el
              panel y un círculo saldría ovalado. */}
          <line x1={x(shown)} y1={0} x2={x(shown)} y2={H_BEST} className="evo__now" />
        </svg>
        <span className="evo__axis evo__axis--top num">{fmt(high, 3, true)}</span>
        <span className="evo__axis evo__axis--bottom num">{fmt(low, 3, true)}</span>
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

      <p className="footnote">
        {objectiveNote(car)} El valor del eje está en esas unidades y no se compara entre autos.
      </p>
    </Panel>
  )
}
