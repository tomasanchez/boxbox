/**
 * Torre de tiempos, sobre MUI DataGrid.
 *
 * Estaba hecha con CSS Grid a mano y se rompía al cambiar la columna visible:
 * los anchos fijos no daban para todos los valores y las columnas numéricas
 * terminaban tocándose. DataGrid resuelve eso de raíz — mide, alinea y mantiene
 * el encabezado sobre su columna sin que haya que calcular nada.
 *
 * Como en la transmisión, **no se muestra todo junto**: la columna de datos
 * alterna entre intervalo, distancia al líder, edad de goma y degradación, y la
 * ventana de boxes se enciende o apaga aparte.
 *
 * Los que abandonan **no se borran**: bajan al pie marcados DNF con su vuelta.
 */

import { useMemo, useState } from 'react'
import { Box, ToggleButton, ToggleButtonGroup } from '@mui/material'
import { DataGrid, type GridColDef, type GridRenderCellParams } from '@mui/x-data-grid'
import { GRID, RACE } from './data'
import { fmt } from './format'
import { PALETTE } from './theme'
import type { Compound, DriverState } from './types'
import { Panel, Tyre } from './ui'

/**
 * Alto de fila, en px. Fijo y no automático porque el panel no scrollea: las
 * veintidós filas más el encabezado tienen que entrar en el alto disponible.
 */
const ROW_HEIGHT = 26

type Metric = 'interval' | 'leader' | 'age' | 'deg'

const METRICS: { id: Metric; label: string; title: string }[] = [
  { id: 'interval', label: 'Int', title: 'Intervalo al auto de adelante' },
  { id: 'leader', label: 'Líder', title: 'Distancia al líder' },
  { id: 'age', label: 'Goma', title: 'Vueltas con el juego actual' },
  { id: 'deg', label: 'Deg', title: 'Segundos por vuelta que pierde por desgaste' },
]

interface Row {
  id: string
  position: number
  code: string
  teamColor: string
  compound: Compound
  out: boolean
  retiredOnLap: number | null
  metric: string
  metricTone: 'normal' | 'gaining' | 'muted'
  windowText: string
  windowFrom: number | null
  windowTo: number | null
}

function isOut(driver: DriverState, lap: number): boolean {
  return driver.retiredOnLap != null && lap >= driver.retiredOnLap
}

function metricValue(d: DriverState, metric: Metric): { text: string; tone: Row['metricTone'] } {
  switch (metric) {
    case 'interval':
      return { text: d.gapAheadS === null ? '—' : `+${fmt(d.gapAheadS)}`, tone: 'normal' }
    case 'leader':
      return d.position === 1 || d.gapLeaderS === null
        ? { text: 'líder', tone: 'muted' }
        : { text: `+${fmt(d.gapLeaderS)}`, tone: 'normal' }
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

export function GridPanel({ lap }: { lap: number }) {
  const { totalLaps } = RACE
  const [metric, setMetric] = useState<Metric>('interval')
  const [showWindow, setShowWindow] = useState(true)

  const active = METRICS.find((m) => m.id === metric) ?? METRICS[0]
  const nowPct = (lap / totalLaps) * 100

  const rows = useMemo<Row[]>(() => {
    const ordered = [...GRID].sort((a, b) => {
      const outA = isOut(a, lap)
      const outB = isOut(b, lap)
      if (outA !== outB) return outA ? 1 : -1
      if (outA && outB) return (b.retiredOnLap ?? 0) - (a.retiredOnLap ?? 0)
      return a.position - b.position
    })

    return ordered.map((d) => {
      const out = isOut(d, lap)
      const value = metricValue(d, metric)
      return {
        id: d.code,
        position: d.position,
        code: d.code,
        teamColor: d.teamColor,
        compound: d.compound,
        out,
        retiredOnLap: d.retiredOnLap ?? null,
        metric: value.text,
        metricTone: value.tone,
        windowText: d.pitWindow ? `${d.pitWindow.opensLap}–${d.pitWindow.closesLap}` : '—',
        windowFrom: d.pitWindow?.opensLap ?? null,
        windowTo: d.pitWindow?.closesLap ?? null,
      }
    })
  }, [lap, metric])

  const running = rows.filter((r) => !r.out).length

  const columns = useMemo<GridColDef<Row>[]>(() => {
    const base: GridColDef<Row>[] = [
      {
        field: 'position',
        headerName: 'P',
        width: 34,
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) => (p.row.out ? '—' : p.row.position),
      },
      {
        field: 'code',
        headerName: 'Piloto',
        width: 68,
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 700 }}>
            <Box
              sx={{
                width: '3px',
                height: '0.9em',
                background: p.row.teamColor,
                opacity: p.row.out ? 0.45 : 1,
              }}
            />
            {p.row.code}
          </Box>
        ),
      },
      {
        field: 'compound',
        headerName: 'G',
        width: 34,
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) => (
          <Box
            sx={{
              opacity: p.row.out ? 0.4 : 1,
              display: 'flex',
              alignItems: 'center',
              height: '100%',
            }}
          >
            <Tyre compound={p.row.compound} />
          </Box>
        ),
      },
      {
        field: 'metric',
        // El encabezado sigue a la métrica elegida.
        headerName: active.label,
        // `flex` deja que la columna crezca con el valor más largo, que es
        // justamente lo que fallaba con los anchos fijos.
        flex: 1,
        minWidth: 78,
        align: 'right',
        headerAlign: 'right',
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) =>
          p.row.out ? (
            <span>
              <span className="tag-out">DNF</span>{' '}
              <span style={{ color: PALETTE.txt4 }}>v{p.row.retiredOnLap}</span>
            </span>
          ) : (
            <span
              style={{
                color:
                  p.row.metricTone === 'gaining'
                    ? PALETTE.green
                    : p.row.metricTone === 'muted'
                      ? PALETTE.txt3
                      : PALETTE.txt1,
              }}
            >
              {p.row.metric}
            </span>
          ),
      },
    ]

    if (!showWindow) return base

    return [
      ...base,
      {
        field: 'windowText',
        headerName: 'Vent.',
        width: 62,
        align: 'right',
        headerAlign: 'right',
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) =>
          p.row.out ? null : (
            <span style={{ color: p.row.windowFrom === null ? PALETTE.txt4 : PALETTE.txt1 }}>
              {p.row.windowText}
            </span>
          ),
      },
      {
        field: 'bar',
        headerName: `1–${totalLaps}`,
        flex: 1.4,
        minWidth: 84,
        sortable: false,
        renderCell: (p: GridRenderCellParams<Row>) => (
          <Box
            sx={{
              position: 'relative',
              width: '100%',
              height: '11px',
              background: PALETTE.bg4,
              borderRadius: '1px',
              overflow: 'hidden',
            }}
          >
            {p.row.windowFrom !== null && p.row.windowTo !== null && !p.row.out ? (
              <Box
                sx={{
                  position: 'absolute',
                  insetBlock: 0,
                  left: `${(p.row.windowFrom / totalLaps) * 100}%`,
                  width: `${((p.row.windowTo - p.row.windowFrom) / totalLaps) * 100}%`,
                  background: PALETTE.green,
                  opacity: 0.55,
                }}
              />
            ) : null}
            {p.row.out ? null : (
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
        ),
      },
    ]
  }, [active.label, showWindow, totalLaps, nowPct])

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
          title="Mostrar u ocultar la ventana de boxes"
          sx={{ ml: '6px' }}
        >
          Vent.
        </ToggleButton>
      </Box>

      <Box className="panel__grow" sx={{ minHeight: 0 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          density="compact"
          rowHeight={ROW_HEIGHT}
          hideFooter
          disableColumnMenu
          disableColumnResize
          disableRowSelectionOnClick
          columnHeaderHeight={26}
          getRowClassName={(p) => (p.row.out ? 'row--out' : '')}
          sx={{
            height: '100%',
            border: 0,
            fontSize: 'var(--fs-tiny)',
            '--DataGrid-rowBorderColor': PALETTE.lineSoft,
            '& .MuiDataGrid-columnHeaders': { borderBottom: `1px solid ${PALETTE.line}` },
            '& .MuiDataGrid-columnHeaderTitle': {
              fontSize: 'var(--fs-micro)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: PALETTE.txt4,
            },
            '& .MuiDataGrid-cell': {
              borderBottom: `1px solid ${PALETTE.lineSoft}`,
              fontFamily: 'var(--mono)',
              fontVariantNumeric: 'tabular-nums',
              px: '6px',
            },
            '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': { outline: 'none' },
            '& .MuiDataGrid-row:hover': { background: PALETTE.bg2 },
            '& .row--out .MuiDataGrid-cell': { color: PALETTE.txt4 },
            '& .MuiDataGrid-filler, & .MuiDataGrid-scrollbarFiller': { display: 'none' },
          }}
        />
      </Box>

      <p className="footnote">
        La marca roja es la vuelta actual. <strong>—</strong> en la ventana significa que la goma
        está plana o mejorando, así que no hay cruce que anticipar. Los <strong>DNF</strong>{' '}
        quedan listados con la vuelta en la que abandonaron.
      </p>
    </Panel>
  )
}
