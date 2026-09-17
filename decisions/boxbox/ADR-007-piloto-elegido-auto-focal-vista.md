---
project: boxbox
adr: 007
title: El piloto elegido es el auto focal de toda la vista
category: ux
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-007: El piloto elegido es el auto focal de toda la vista

## Context

«Donde se elige qué Piloto (Posición) simular». Elegir puede cambiar sólo la tarjeta que se lee, o puede cambiar toda la vista, o puede ser un puesto hipotético en vez de un piloto real.

## Decision

El piloto elegido pasa a ser el auto focal: se destaca en el mapa del circuito y en la torre de tiempos, y su plan es el que se contrasta con lo que va pasando en la carrera animada.

## Alternatives Considered

- **Sólo cambia la tarjeta**: mínimo trabajo de UI, pero el selector no se siente conectado con lo que se ve.
- **Puesto hipotético P1..P20**: es el hallazgo de `grid_position.py` — el plan cambia en la burbuja de los puntos — pero desconecta la vista de la parrilla real de Zandvoort (ver ADR-004).
- **Piloto más apetito de riesgo**: expondría la mesa medida en `risk_appetite.py`, pero multiplica el precálculo por el producto cartesiano de objetivo y riesgo.

## Consequences

Toca `RaceView` y `CircuitMap` además del panel nuevo. El estado del piloto focal tiene que vivir en `App.tsx`, que hoy es un switch de dos vistas sin router.

## Status History

- 2026-09-17: accepted
