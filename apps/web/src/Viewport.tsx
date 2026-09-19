/**
 * El piso de ancho, y qué se muestra debajo de él.
 *
 * El panel se diseñó para una pantalla de muro de boxes: la torre de tiempos,
 * el mapa y las tarjetas de estrategia, los tres a la vez. De 1024 px para
 * arriba eso entra en tres columnas sin scrollear; entre 768 y 1024 entra en
 * una sola columna con scroll. Abajo de 768 no entra de ninguna forma que
 * siga siendo honesta: el mapa se vuelve ilegible y las tarjetas se cortan.
 *
 * Entonces no se muestra recortado: se dice. Un aviso que nombra el piso y
 * explica por qué existe es información; una pantalla cortada en silencio es
 * un defecto disfrazado de diseño.
 *
 * El corte se decide con `matchMedia` y no con CSS a propósito: así `App` se
 * **desmonta**, la simulación deja de correr y no queda nada invisible en el
 * árbol de accesibilidad. El precio es que cruzar el umbral reinicia la
 * carrera, que es lo que corresponde — es otra sesión.
 */

import type { ReactNode } from 'react'
import { Alert, AlertTitle, useMediaQuery } from '@mui/material'

/**
 * Ancho mínimo con soporte, en px.
 *
 * Tiene que coincidir con el corte del bloque «hasta tablet» de `styles.css`:
 * si se mueve uno solo de los dos, queda una franja en la que la aplicación se
 * monta con la hoja del otro lado.
 */
const MIN_WIDTH = 768

const QUERY = `(min-width: ${MIN_WIDTH}px)`

/**
 * Deja pasar al panel sólo si hay ancho, y si no muestra el aviso.
 *
 * Los hijos llegan como elemento ya creado pero **no se montan** cuando no hay
 * ancho: crear el elemento no ejecuta nada, así que la simulación no arranca.
 *
 * `noSsr` en la consulta porque el valor se usa sólo del lado del cliente: sin
 * él la primera pasada devuelve el valor por defecto y el aviso parpadea en
 * pantallas anchas antes de que el efecto lo corrija.
 */
export function Viewport({ children }: { children: ReactNode }) {
  const wide = useMediaQuery(QUERY, { noSsr: true })
  return wide ? <>{children}</> : <TooSmall />
}

/**
 * El aviso. Sobrio: dice el piso, dice por qué, y dice qué hacer.
 *
 * Lleva ícono además del color —el amarillo de la paleta es el mismo de la
 * bandera amarilla— porque el estado no se comunica sólo con color.
 */
function TooSmall() {
  return (
    <main className="toosmall">
      <Alert
        severity="warning"
        variant="outlined"
        /* Contenido estático, no una alerta que irrumpe: `status` y no `alert`. */
        role="status"
        className="toosmall__alert"
      >
        {/* Es el título de la única pantalla que hay: encabezado de verdad. */}
        <AlertTitle component="h1" className="toosmall__title">
          El panel necesita al menos {MIN_WIDTH} px de ancho
        </AlertTitle>

        <p className="toosmall__body">
          Es un panel de muro de boxes: muestra la torre de tiempos, el mapa del circuito y
          las tarjetas de estrategia a la vez. Más angosto que esto el mapa deja de ser
          legible y las tarjetas se cortan, así que el teléfono queda fuera de alcance.
        </p>

        <p className="toosmall__body">
          Girá el dispositivo a horizontal, o abrilo en una pantalla más ancha.
        </p>

        <p className="toosmall__foot">
          Preferimos decirlo antes que mostrarte una pantalla recortada.
        </p>
      </Alert>
    </main>
  )
}
