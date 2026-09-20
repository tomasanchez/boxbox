---
project: boxbox
adr: 015
title: Bajo bandera roja el auto focal también cambia gratis, y el resto de su plan no se reprograma
category: architecture
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-015: Bajo bandera roja el auto focal también cambia gratis, y el resto de su plan no se reprograma

## Context

Bajo roja el 94,9% de los autos cambia gomas sin costo de posición (n=276).
El plan del auto focal es pre-carrera y fijo por definición (ADR-006). Las
dos cosas son incompatibles: si el focal no toma el cambio gratis, el modelo
lo castiga sistemáticamente en el 94,9% de las rojas, por una razón que no es
estratégica sino un defecto del modelo, y eso sesga la recomendación hacia
planes que paran temprano. Monza 2026, el caso de estudio del informe, es
exactamente esto: 22 de 32 paradas fueron gratis bajo roja.

## Decision

Al focal se le inserta una parada implícita con el costo de roja, se le
resetea la edad de goma, y ese compuesto cuenta para B6.3.8. Las paradas que
le quedaban en el plan se mantienen en su vuelta absoluta: el plan NO se
reprograma.

## Alternatives Considered

- **Plan clavado sin cambio**: rechazada por el sesgo sistemático descrito —
  castiga al 94,9% de las rojas por una razón ajena a la estrategia.
- **Reprogramar las paradas restantes según cuánta goma quedó en juego**:
  rechazada por ahora — es lo más fiel a lo que haría un muro real, pero
  convierte el plan en algo relativo en vez de vueltas absolutas, y eso toca
  el contrato con la UI que fija ADR-006 (la recomendación se emite en la
  vuelta 1 y no se recalcula).

## Consequences

Hay que decidir qué compuesto se calza en esa parada implícita y declararlo
— queda pendiente. Un plan puede terminar con más paradas de las que
declaró, y la UI tiene que poder mostrar la diferencia entre el plan y lo que
pasó en el sorteo, que es justo lo que ADR-006 regula con la banda de
proyección y el botón de re-sorteo. Enlazado con ADR-006.
