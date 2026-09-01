/**
 * Simulador de estrategia — armazón.
 *
 * Todo entra en el viewport: el `.app` es una grilla de tres filas con la
 * última en `minmax(0,1fr)`, y ningún contenedor scrollea. Ver `styles.css`.
 */

import { useState } from 'react'
import { ForecastView } from './ForecastView'
import { RaceView } from './RaceView'
import { RACE, SCENARIOS } from './data'
import { Kpi } from './ui'
import type { TrackStatus } from './types'

type View = 'race' | 'forecast'

const TABS: { id: View; label: string }[] = [
  { id: 'race', label: 'Panel de carrera' },
  { id: 'forecast', label: 'Pronóstico' },
]

export default function App() {
  // El hash permite abrir una vista directo (y sacarle captura sin interactuar).
  const initial: View = window.location.hash === '#forecast' ? 'forecast' : 'race'
  const [view, setView] = useState<View>(initial)
  const [status, setStatus] = useState<TrackStatus>('GREEN')
  const [lap, setLap] = useState(RACE.currentLap)

  const scenario = SCENARIOS.find((s) => s.id === status) ?? SCENARIOS[0]

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <div>
            <div className="brand__name">Simulador de estrategia</div>
            <div className="brand__race">
              {RACE.season} · R{RACE.round} {RACE.circuit}
            </div>
          </div>
        </div>

        <div className="tabs" role="tablist" aria-label="Vistas">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              className="tab"
              aria-selected={view === t.id}
              onClick={() => {
                setView(t.id)
                window.location.hash = t.id
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="scenarios" role="group" aria-label="Estado de pista">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              type="button"
              className="scenario"
              aria-pressed={status === s.id}
              onClick={() => setStatus(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </header>

      <div className="strip">
        <Kpi
          label="Vuelta"
          value={`${lap} / ${RACE.totalLaps}`}
          note={`quedan ${RACE.totalLaps - lap}`}
        />
        <Kpi
          label="Costo de parar"
          value={`${scenario.pitCostPositions} pos`}
          note={scenario.note}
          tone={scenario.pitCostPositions === 0 ? 'good' : 'alert'}
        />
        <Kpi
          label="Prob. Safety Car"
          value="0,571"
          note="tasa global medida"
        />
        <Kpi
          label="Compuestos obligatorios"
          value={RACE.mandatoryCompounds.length === 2 ? 'M + H' : '—'}
          note={`mínimo ${RACE.minSets} juegos · B6.3.8`}
        />
        <div className="kpi">
          <span className="kpi__label">Avanzar vuelta</span>
          <input
            type="range"
            min={1}
            max={RACE.totalLaps}
            value={lap}
            onChange={(e) => setLap(Number(e.target.value))}
            aria-label="Vuelta de la carrera"
            style={{ width: '100%', accentColor: 'var(--red)' }}
          />
        </div>
      </div>

      {view === 'race' ? <RaceView scenarioLap={lap} /> : <ForecastView />}
    </div>
  )
}
