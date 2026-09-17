/**
 * Qué le pasa al piloto elegido si corre el plan recomendado (ADR-001).
 *
 * No hay «% de éxito», porque ese dato no existe: éxito no significa lo mismo
 * desde la pole que desde el puesto 19. Se muestran **las cuatro
 * probabilidades** del mismo plan y el lector elige la que le importa.
 *
 * Y la llegada va como **banda**, nunca como número solo. Decir «llega 3,2» es
 * decir una cifra que no va a ocurrir jamás —no existe el puesto 3,2— y esconde
 * que el mismo plan termina segundo o noveno según cómo salga la carrera. La
 * banda es media ± un desvío, y abajo está el histograma completo de las 1.200
 * carreras sorteadas, que es el dato del que sale todo lo demás.
 */

import { fmt } from './format'
import { PRERACE, arrivalBand, histogramBars, riskNote } from './prerace'
import type { PreRaceCar } from './prerace'
import { Panel } from './ui'

/**
 * Probabilidad con un decimal.
 *
 * Con porcentaje entero, P(ganar) = 0,0067 y P(ganar) = 0,0 se ven las dos como
 * «1%» y «0%», y la diferencia entre «casi nunca» y «nunca» es justo la que
 * importa en el fondo de la parrilla.
 */
function prob(value: number): string {
  return `${fmt(value * 100, 1)}%`
}

const ROWS = [
  { key: 'p_ganar', label: 'Gana la carrera' },
  { key: 'p_podio', label: 'Termina en el podio' },
  { key: 'p_puntos', label: 'Termina en zona de puntos' },
  { key: 'p_mejora', label: 'Mejora su puesto de largada' },
] as const

export function OutcomeCard({ car }: { car: PreRaceCar }) {
  const band = arrivalBand(car)
  const bars = histogramBars(car)
  const peak = Math.max(...bars.map((b) => b.count), 1)
  const cars = PRERACE.race.cars

  /** Posición en el eje del histograma, que va de P1 a P22 a lo ancho. */
  const at = (position: number) => ((position - 0.5) / cars) * 100

  return (
    <Panel
      title="Cómo termina"
      note={`${PRERACE.checks.draws.toLocaleString('es-AR')} carreras sorteadas con el plan recomendado`}
      fill
    >
      <div className="band">
        <span className="band__kicker">Llegada esperada</span>
        <span className="band__value num">
          entre P{fmt(band.low, 1)} y P{fmt(band.high, 1)}
        </span>
        <span className="band__note">
          media P{fmt(band.mean, 1)} · desvío {fmt(car.sd_position, 2)} puestos · larga P
          {car.grid_position}
        </span>
      </div>

      <div className="probs">
        {ROWS.map((row) => {
          const value = car[row.key]
          return (
            <div className="prob" key={row.key}>
              <span className="prob__label">{row.label}</span>
              <span className="prob__track">
                <span className="prob__bar" style={{ width: `${value * 100}%` }} />
              </span>
              <span className="prob__value num">{prob(value)}</span>
            </div>
          )
        })}
      </div>

      <div className="hist panel__grow">
        {/* La banda, dibujada debajo de las barras: es el resumen de lo mismo. */}
        <span
          className="hist__band"
          style={{ left: `${at(band.low)}%`, width: `${at(band.high) - at(band.low)}%` }}
        />
        <span className="hist__mean" style={{ left: `${at(band.mean)}%` }} />
        <div className="hist__bars">
          {bars.map((bar) => (
            <span
              className={`hist__bar${bar.count === peak ? ' hist__bar--peak' : ''}`}
              key={bar.position}
              style={{ height: `${(bar.count / peak) * 100}%` }}
              title={`P${bar.position}: ${bar.count} de ${PRERACE.checks.draws} carreras (${prob(
                bar.share,
              )})`}
            />
          ))}
        </div>
      </div>

      <div className="hist__axis">
        <span>P1</span>
        <span>puesto de llegada en las {PRERACE.checks.draws.toLocaleString('es-AR')} carreras</span>
        <span>P{cars}</span>
      </div>

      <p className="footnote">
        {riskNote(car)}
        {car.p_mejora === 0 && car.grid_position === 1
          ? ' Larga desde la pole: no hay puesto que mejorar, y por eso esa probabilidad es cero.'
          : ''}
        {car.p_puntos === 1
          ? ' P(zona de puntos) = 100% es una afirmación sobre el modelo, no sobre la carrera: el simulador no modela abandonos.'
          : ''}
      </p>
    </Panel>
  )
}
