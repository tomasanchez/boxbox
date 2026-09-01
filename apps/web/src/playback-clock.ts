/**
 * Controles de reproducción de la carrera.
 *
 * El concepto los tenía y la primera versión de esta UI se los comió: reproducir,
 * elegir velocidad y saltar a una vuelta. Sin esto el panel es una foto, y la
 * gracia de una ventana de boxes es verla abrirse.
 */

export interface Speed {
  id: string
  label: string
  /** Milisegundos de reloj por vuelta simulada. */
  msPerLap: number
}

/**
 * Velocidades de reproducción.
 *
 * El reloj en sí vive en `useField`, que interpola el avance del pelotón: la
 * velocidad elegida acá es sólo su escala.
 *
 * El multiplicador es relativo a la velocidad base de lectura del panel, **no
 * al tiempo real**: una vuelta de Zandvoort dura unos 72 segundos y nadie
 * quiere esperar eso. En 1× la carrera completa lleva algo menos de cuatro
 * minutos, que es el ritmo al que se alcanzan a leer las ventanas de boxes y
 * los duelos mientras cambian.
 */
export const SPEEDS: Speed[] = [
  { id: 'half', label: '½×', msPerLap: 6000 },
  { id: 'x1', label: '1×', msPerLap: 3000 },
  { id: 'x2', label: '2×', msPerLap: 1500 },
  { id: 'x4', label: '4×', msPerLap: 750 },
]
