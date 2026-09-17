/** Controles de reproducción. La lógica del reloj vive en `playback.ts`. */

import type { Speed } from './playback-clock'
import { SPEEDS } from './playback-clock'

export function PlaybackControls({
  playing,
  onTogglePlay,
  speed,
  onSpeed,
  lap,
  totalLaps,
  onLap,
  homeLap,
}: {
  playing: boolean
  onTogglePlay: () => void
  speed: Speed
  onSpeed: (s: Speed) => void
  lap: number
  totalLaps: number
  onLap: (lap: number) => void
  /** Vuelta con datos medidos, a la que conviene poder volver. */
  homeLap: number
}) {
  const atEnd = lap >= totalLaps

  return (
    <div className="playback">
      <button
        type="button"
        className="playback__play"
        onClick={onTogglePlay}
        disabled={atEnd}
        aria-label={playing ? 'Pausar' : 'Reproducir'}
      >
        <span aria-hidden="true">{playing ? '❚❚' : '▶'}</span>
        <span className="playback__playlabel">{playing ? 'Pausa' : 'Reproducir'}</span>
      </button>

      <div className="playback__speeds" role="group" aria-label="Velocidad">
        {SPEEDS.map((s) => (
          <button
            key={s.id}
            type="button"
            className="playback__speed"
            aria-pressed={s.id === speed.id}
            onClick={() => onSpeed(s)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <input
        className="playback__scrub"
        type="range"
        min={1}
        max={totalLaps}
        value={lap}
        onChange={(e) => onLap(Number(e.target.value))}
        aria-label="Vuelta de la carrera"
      />

      <div className="playback__jumps">
        <button type="button" className="playback__jump" onClick={() => onLap(1)}>
          V1
        </button>
        {/* Corriendo desde la largada el atajo de arriba ya es la vuelta 1: dos
            botones iguales al lado del otro no ayudan a nadie. */}
        {homeLap === 1 ? null : (
          <button
            type="button"
            className="playback__jump"
            onClick={() => onLap(homeLap)}
            title="Vuelta con datos medidos"
          >
            V{homeLap}
          </button>
        )}
      </div>
    </div>
  )
}
