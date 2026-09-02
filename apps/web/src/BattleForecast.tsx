/**
 * Pronóstico de batalla, con la forma de la gráfica «Battle Forecast».
 *
 * Sigue el reparto de la transmisión: los dos pilotos a los costados, el estado
 * en un recuadro al medio, y abajo el puesto que se disputa, el medidor de
 * dificultad y el intervalo.
 *
 * El recuadro del medio cambia según lo que esté pasando, igual que en la
 * televisión, que a veces muestra «CHASING» con las flechitas corriendo y a
 * veces «STRIKING DISTANCE IN 7 LAPS»:
 *
 *   a tiro         ya está dentro del segundo, con DRS
 *   a tiro en N    va a llegar, y en cuántas vueltas
 *
 * No hay estado para «se escapa»: `pickBattle` no elige esos pares, porque un
 * intervalo que se abre no es una batalla sino el orden de la carrera. La
 * tarjeta directamente no se muestra.
 *
 * Las flechas se encienden en cadena hacia el de adelante, que es la dirección
 * en la que se está cerrando el intervalo.
 */

import { STRIKE_S, type BattleForecast as Forecast } from './forecast'
import { MEASURED_CIRCUITS } from './overtaking'
import { GRID } from './data'
import { fmt } from './format'

/** Cuántas flechas lleva la cinta del medio. */
const CHEVRONS = 5

/** Tramos del medidor de dificultad. */
const GAUGE_STEPS = 10

/** Verde a rojo, el mismo degradado que usa la gráfica. */
const GAUGE_COLORS = ['#35c46f', '#8cc63f', '#c8c020', '#f5c518', '#f0a01a', '#e87818', '#ec3013']

function teamColor(code: string): string {
  return GRID.find((d) => d.code === code)?.teamColor ?? '#8f8b88'
}

/** Ordinal castellano, que es lo que dice el relato: «pelea por el 3.º». */
function ordinal(n: number): string {
  return `${n}º`
}

export function BattleForecastCard({
  forecast,
  open,
  onToggle,
}: {
  forecast: Forecast
  open: boolean
  onToggle: () => void
}) {
  const measured = forecast.overtaking
  const lit = Math.max(1, Math.round(measured.difficulty * GAUGE_STEPS))

  /*
   * El medidor es una posición dentro de los circuitos medidos, no una escala
   * absoluta, y con cuatro carreras por circuito el medio de la tabla no es
   * separable. El detalle va en el título para que el número no se lea con más
   * precisión de la que tiene.
   */
  const gaugeTitle = measured.rank
    ? `${measured.perLap.toFixed(2).replace('.', ',')} cambios de posición por vuelta en verde, ` +
      `medido sobre ${measured.races} carreras · puesto ${measured.rank} de ${MEASURED_CIRCUITS} ` +
      `(1 = el más difícil)`
    : 'circuito sin medir — se usa el promedio general'

  return (
    <div className={`bf bf--${forecast.state}`}>
      <div className="bf__head">
        <span className="bf__title">Batalla por el {ordinal(forecast.position)}</span>
        <span className="bf__sub">pronóstico</span>
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
        <div className="bf__body">
          <div className="bf__side">
            <span className="bf__bar" style={{ background: teamColor(forecast.chaser) }} />
            <span className="bf__code">{forecast.chaser}</span>
            <span className="bf__foot">va {ordinal(forecast.position + 1)}</span>
          </div>

          <div className="bf__middle">
            <div className="bf__state">
              {forecast.state === 'CLOSING' && forecast.lapsToStrike != null ? (
                <>
                  A tiro en <span className="bf__laps num">{forecast.lapsToStrike}</span>{' '}
                  {forecast.lapsToStrike === 1 ? 'vuelta' : 'vueltas'}
                </>
              ) : (
                'A tiro'
              )}
            </div>

            {/* Se encienden en cadena hacia el de adelante: la dirección del recorte. */}
            <div className="bf__chevrons" aria-hidden="true">
              {Array.from({ length: CHEVRONS }, (_, i) => (
                <span className="bf__chevron" key={i} style={{ animationDelay: `${i * 110}ms` }}>
                  ▶
                </span>
              ))}
            </div>

            <div className="bf__gauge" title={gaugeTitle}>
              <span className="bf__gaugel">Dificultad para pasar</span>
              <span className="bf__steps">
                {Array.from({ length: GAUGE_STEPS }, (_, i) => (
                  <span
                    className="bf__step"
                    key={i}
                    style={{
                      background:
                        i < lit
                          ? GAUGE_COLORS[Math.round((i / (GAUGE_STEPS - 1)) * (GAUGE_COLORS.length - 1))]
                          : undefined,
                    }}
                  />
                ))}
              </span>
              {/*
               * El puesto va escrito. El medidor solo se leería como una
               * medición del circuito, y es una posición dentro de los que
               * tenemos medidos — el detalle completo está en el título.
               */}
              {measured.rank ? (
                <span className="bf__rank num">
                  {measured.rank}º/{MEASURED_CIRCUITS}
                </span>
              ) : null}
            </div>
          </div>

          <div className="bf__side bf__side--right">
            <span className="bf__bar" style={{ background: teamColor(forecast.leader) }} />
            <span className="bf__code">{forecast.leader}</span>
            <span className="bf__foot num">
              {fmt(forecast.gapNow, 3)} s{' '}
              {forecast.gapNow <= STRIKE_S ? 'con DRS' : 'adelante'}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  )
}
