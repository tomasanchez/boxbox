/** Primitivas compartidas por las dos vistas. */

import type { ReactNode } from 'react'
import { COMPOUND_COLOR, COMPOUND_LETTER } from './data'
import type { Compound } from './types'

export function Panel({
  title,
  note,
  fill,
  children,
}: {
  title: string
  note?: string
  /** El contenido ocupa todo el alto en vez de medir lo que necesita. */
  fill?: boolean
  children: ReactNode
}) {
  return (
    <section className="panel">
      <header className="panel__head">
        <h2 className="panel__title">{title}</h2>
        {note ? <span className="panel__note">{note}</span> : null}
      </header>
      <div className={`panel__body${fill ? ' panel__body--fill' : ''}`}>{children}</div>
    </section>
  )
}

/** Disco de compuesto. La letra acompaña al color: el color solo no alcanza. */
export function Tyre({ compound }: { compound: Compound }) {
  return (
    <span
      className={`tyre tyre--${compound}`}
      style={{ background: COMPOUND_COLOR[compound] }}
      title={compound}
    >
      {COMPOUND_LETTER[compound]}
    </span>
  )
}

export function Kpi({
  label,
  value,
  note,
  tone,
}: {
  label: string
  value: string
  note?: string
  tone?: 'alert' | 'good'
}) {
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : ''}`}>
      <span className="kpi__label">{label}</span>
      <span className="kpi__value num">{value}</span>
      {note ? <span className="kpi__note">{note}</span> : null}
    </div>
  )
}
