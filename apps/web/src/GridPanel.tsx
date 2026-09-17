/**
 * Torre de tiempos, sobre el Table de MUI.
 *
 * Antes era CSS Grid a mano y se rompía al cambiar la métrica visible: los
 * anchos fijos no alojaban «+0,69» y «+99,46» y «líder» en el mismo lugar, y
 * con `auto` las columnas numéricas se colapsaban entre sí.
 *
 * Una tabla HTML resuelve eso por su naturaleza: el navegador mide el contenido
 * y reparte el ancho solo. No hace falta calcular nada, y por eso alcanza con
 * `Table` en lugar del DataGrid — no necesitamos ordenar, filtrar ni paginar.
 *
 * Como en la transmisión, **no se muestra todo junto**: la columna de datos
 * alterna entre intervalo, distancia al líder, edad de goma y degradación, y la
 * ventana de boxes se enciende o apaga aparte.
 *
 * Los que abandonan **no se borran**: bajan al pie marcados DNF con su vuelta.
 *
 * Posiciones e intervalos salen de la **simulación en curso**, no del dato de
 * la vuelta 30: si un auto adelanta, la tabla lo muestra. Lo que sí es estático
 * es la estrategia —compuesto, edad de goma, ventana de boxes—, que es la
 * medición sobre la que trabaja el sistema.
 */

import { useMemo, useState } from 'react'
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import { COMPOUND_COLOR, RACE } from './data'
import { fmt } from './format'
import { PALETTE } from './theme'
import type { PitStop } from './tyres'
import type { DriverState } from './types'
import type { Timing } from './useField'
import { Panel, Tyre } from './ui'

type Metric = 'interval' | 'leader' | 'age' | 'deg'

const METRICS: { id: Metric; label: string; title: string }[] = [
  { id: 'interval', label: 'Int', title: 'Intervalo al auto de adelante' },
  { id: 'leader', label: 'Líder', title: 'Distancia al líder' },
  { id: 'age', label: 'Goma', title: 'Vueltas con el juego actual' },
  { id: 'deg', label: 'Deg', title: 'Segundos por vuelta que pierde por desgaste' },
]

function isOut(driver: DriverState, lap: number): boolean {
  return driver.retiredOnLap != null && lap >= driver.retiredOnLap
}

function metricValue(
  d: DriverState,
  metric: Metric,
  live: { gapAhead: number | null; gapLeader: number; place: number; formation: boolean },
): { text: string; tone: 'normal' | 'gaining' | 'muted' } {
  switch (metric) {
    case 'interval':
      // Detenidos en formación no hay intervalo que medir.
      if (live.formation) return { text: '—', tone: 'muted' }
      return {
        text: live.gapAhead === null ? '—' : `+${fmt(live.gapAhead)}`,
        tone: 'normal',
      }
    case 'leader':
      if (live.formation) return { text: live.place === 1 ? 'pole' : '—', tone: 'muted' }
      return live.place === 1
        ? { text: 'líder', tone: 'muted' }
        : { text: `+${fmt(live.gapLeader)}`, tone: 'normal' }
    case 'age':
      return { text: `${d.tyreAge}v`, tone: 'normal' }
    case 'deg':
      return {
        text: fmt(d.degradationS, 2, true),
        // Negativo = la goma todavía mejora.
        tone: d.degradationS < 0 ? 'gaining' : 'normal',
      }
  }
}

const TONE_COLOR = {
  normal: PALETTE.txt1,
  gaining: PALETTE.green,
  muted: PALETTE.txt3,
} as const

export function GridPanel({
  lap,
  cars,
  timing,
  focal,
  plans,
}: {
  lap: number
  /** Los mismos autos que alimentan la simulación, en su orden de arreglo. */
  cars: DriverState[]
  /** Cronometraje vivo: de acá salen posiciones e intervalos. */
  timing: Timing
  /** El piloto elegido: se destaca en la torre además del mapa (ADR-007). */
  focal?: string
  /**
   * Plan de paradas de cada auto cuando la carrera corre desde la largada.
   *
   * Reemplaza a la columna de ventana, **no la acompaña**: la ventana es lo que
   * el modelo proyecta y el plan es lo que el auto va a hacer. Un auto puede
   * tener ventana abierta y no parar, o parar sin tenerla, así que mezclarlas en
   * la misma columna las haría pasar por lo mismo.
   */
  plans?: PitStop[][] | null
}) {
  const { totalLaps } = RACE
  const [metric, setMetric] = useState<Metric>('interval')
  const [showWindow, setShowWindow] = useState(true)

  const active = METRICS.find((m) => m.id === metric) ?? METRICS[0]
  const nowPct = (lap / totalLaps) * 100
  const planned = plans != null

  // Orden de carrera en vivo: sale de la simulación. Los que abandonaron van al
  // pie, del abandono más reciente al más viejo.
  const rows = useMemo(() => {
    const place = new Map(timing.order.map((carIndex, i) => [carIndex, i + 1]))
    return cars
      .map((driver, index) => ({
        driver,
        index,
        out: isOut(driver, lap),
        place: place.get(index) ?? 0,
        gapAhead: timing.gapAhead[index] ?? null,
        gapLeader: timing.gapLeader[index] ?? 0,
      }))
      .sort((a, b) => {
        if (a.out !== b.out) return a.out ? 1 : -1
        if (a.out && b.out) return (b.driver.retiredOnLap ?? 0) - (a.driver.retiredOnLap ?? 0)
        return a.place - b.place
      })
  }, [cars, timing, lap])

  const running = rows.filter((r) => !r.out).length

  return (
    <Panel
      title="Posiciones y ventanas"
      note={`V${lap} / ${totalLaps} · ${running} en pista`}
      fill
    >
      <Box sx={{ display: 'flex', alignItems: 'stretch' }}>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={metric}
          onChange={(_, next: Metric | null) => next && setMetric(next)}
          sx={{ flex: 1 }}
        >
          {METRICS.map((m) => (
            <ToggleButton key={m.id} value={m.id} title={m.title} sx={{ flex: 1 }}>
              {m.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        {/* Aparte del grupo: las métricas son «una de cuatro», esto es sí/no. */}
        <ToggleButton
          size="small"
          value="window"
          selected={showWindow}
          onChange={() => setShowWindow((v) => !v)}
          title={
            planned ? 'Mostrar u ocultar el plan de paradas' : 'Mostrar u ocultar la ventana de boxes'
          }
          sx={{ ml: '6px' }}
        >
          {planned ? 'Plan' : 'Vent.'}
        </ToggleButton>
      </Box>

      <Box className="panel__grow tower-wrap" sx={{ minHeight: 0 }}>
        <Table size="small" className="tower-table">
          <TableHead>
            <TableRow>
              <TableCell>P</TableCell>
              <TableCell>Piloto</TableCell>
              <TableCell title="Compuesto">G</TableCell>
              <TableCell align="right">{active.label}</TableCell>
              {showWindow ? (
                <>
                  <TableCell align="right">{planned ? 'Plan' : 'Vent.'}</TableCell>
                  {/* La barra se lleva el ancho que sobra. */}
                  <TableCell sx={{ width: '38%' }}>1–{totalLaps}</TableCell>
                </>
              ) : null}
            </TableRow>
          </TableHead>

          <TableBody>
            {rows.map(({ driver: d, index, out, place, gapAhead, gapLeader }) => {
              const w = d.pitWindow
              const stops = plans?.[index] ?? []
              const chosen = d.code === focal
              const cell = metricValue(d, metric, {
                gapAhead,
                gapLeader,
                place,
                formation: timing.formation,
              })
              return (
                <TableRow
                  key={d.code}
                  className={`${out ? 'row--out' : ''}${chosen ? ' row--focal' : ''}`.trim()}
                  aria-current={chosen ? 'true' : undefined}
                >
                  {/* El triángulo marca al elegido: el fondo teñido solo no
                      alcanza para distinguirlo de una fila resaltada al pasar. */}
                  <TableCell>
                    {chosen ? <span aria-hidden="true">▸</span> : null}
                    {out ? '—' : place}
                  </TableCell>

                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 700 }}>
                      <Box
                        sx={{
                          width: '3px',
                          height: '0.9em',
                          background: d.teamColor,
                          opacity: out ? 0.45 : 1,
                        }}
                      />
                      {d.code}
                    </Box>
                  </TableCell>

                  <TableCell sx={{ opacity: out ? 0.4 : 1 }}>
                    <Tyre compound={d.compound} />
                  </TableCell>

                  <TableCell align="right" sx={{ color: TONE_COLOR[cell.tone] }}>
                    {out ? (
                      <>
                        <span className="tag-out">DNF</span>{' '}
                        <span style={{ color: PALETTE.txt4 }}>v{d.retiredOnLap}</span>
                      </>
                    ) : (
                      cell.text
                    )}
                  </TableCell>

                  {showWindow ? (
                    <>
                      <TableCell
                        align="right"
                        sx={{ color: (planned ? stops.length > 0 : w) ? PALETTE.txt1 : PALETTE.txt4 }}
                      >
                        {planned
                          ? stops.length > 0
                            ? stops.map((stop) => stop.lap).join('·')
                            : '—'
                          : out
                            ? ''
                            : w
                              ? `${w.opensLap}–${w.closesLap}`
                              : '—'}
                      </TableCell>

                      <TableCell>
                        <Box
                          sx={{
                            position: 'relative',
                            height: '11px',
                            background: PALETTE.bg4,
                            borderRadius: '1px',
                            overflow: 'hidden',
                          }}
                        >
                          {planned
                            ? /* Las paradas del plan, marcadas en la línea de
                                 tiempo con el color del juego que calza. La vuelta
                                 va escrita en la columna de al lado, así que el
                                 color no es el único canal. */
                              stops.map((stop) => (
                                <Box
                                  key={stop.lap}
                                  title={`Parada en la vuelta ${stop.lap}: ${stop.compound}`}
                                  sx={{
                                    position: 'absolute',
                                    insetBlock: 0,
                                    left: `${(stop.lap / totalLaps) * 100}%`,
                                    width: '3px',
                                    background: COMPOUND_COLOR[stop.compound],
                                  }}
                                />
                              ))
                            : w && !out
                              ? (
                                  <Box
                                    sx={{
                                      position: 'absolute',
                                      insetBlock: 0,
                                      left: `${(w.opensLap / totalLaps) * 100}%`,
                                      width: `${((w.closesLap - w.opensLap) / totalLaps) * 100}%`,
                                      background: PALETTE.green,
                                      opacity: 0.55,
                                    }}
                                  />
                                )
                              : null}
                          {out ? null : (
                            <Box
                              sx={{
                                position: 'absolute',
                                insetBlock: 0,
                                left: `${nowPct}%`,
                                width: '2px',
                                background: PALETTE.red,
                              }}
                            />
                          )}
                        </Box>
                      </TableCell>
                    </>
                  ) : null}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Box>

      <p className="footnote">
        La marca roja es la vuelta actual.{' '}
        {planned ? (
          <>
            La columna <strong>Plan</strong> son las vueltas en las que cada auto para según el
            algoritmo, y las marcas de color, el juego que calza. No es una ventana proyectada: es
            lo que el auto va a hacer en este sorteo.
          </>
        ) : (
          <>
            <strong>—</strong> en la ventana significa que la goma está plana o mejorando, así que
            no hay cruce que anticipar. Los <strong>DNF</strong> quedan listados con la vuelta en la
            que abandonaron.
          </>
        )}
      </p>
    </Panel>
  )
}
