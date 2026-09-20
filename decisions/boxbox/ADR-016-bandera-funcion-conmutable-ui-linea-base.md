---
project: boxbox
adr: 016
title: Todo va detrás de una bandera de función conmutable desde la UI, con la línea base de plan fijo preservada
category: business
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-016: Todo va detrás de una bandera de función conmutable desde la UI, con la línea base de plan fijo preservada

## Context

El usuario pidió explícitamente que la feature «rivales reactivos» vaya
detrás de una feature flag activable desde la UI. Además resuelve un
problema real: cambiar el comportamiento de los rivales vuelve a mover
cifras ya publicadas en el informe y en ADR-001, ADR-003, ADR-006 y ADR-008.
Con el interruptor, la línea base de rivales con plan fijo queda viva y
comparable en vez de reemplazada.

## Decision

La reactividad es un modo, no un reemplazo. El simulador acepta el modo como
parámetro, el export emite las dos variantes, y la web expone un interruptor
que cambia entre «rivales con plan fijo» y «rivales reactivos» (ver ADR-012 y
ADR-013 para qué implica cada modo). El entregable de la feature es poder ver
el plan pre-carrera de un piloto evaluado contra un campo que reacciona a
VSC, SC, roja y a su propia parada, y poder apagarlo para ver el antes.

## Alternatives Considered

- **Reemplazar el comportamiento sin interruptor**: rechazada — destruye la
  comparabilidad con todo lo publicado y obliga a re-medir el informe entero
  sin poder mostrar el contraste.
- **Interruptor sólo como parámetro de línea de comandos, sin exponerlo en la
  UI**: rechazada — el usuario lo pidió en la UI, y el contraste es
  justamente lo que hace didáctica la demostración.

## Consequences

El JSON del export crece: lleva las dos corridas. Hay que decidir si eso
entra en el mismo archivo o en dos, dado que el actual ya pesa 330 KB y
`apps/web/src/prerace-zandvoort.json` tiene que quedar byte a byte igual a
`docs/research/` (ADR-010) — queda pendiente de definir en la
implementación. El informe puede mostrar el antes y el después como una
tabla en vez de como una corrección, que es mejor para el trabajo.
