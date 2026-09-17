---
project: boxbox
adr: 004
title: El escenario es Zandvoort 2026 con clasificación real, y se elimina la escalera inventada
category: data
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-004: El escenario es Zandvoort 2026 con clasificación real, y se elimina la escalera inventada

## Context

El pre-carrera necesita el ritmo relativo de cada auto, que sale del hueco de clasificación vía `pace_from_qualifying` (`QUALI_TO_RACE_PACE = 0.835`, validado r = 0.880 sobre 277 pilotos-carrera). Pero `prerace_strategy.py` usa hoy una escalera INVENTADA de 0,25 segundos por puesto de grilla (`GRID_GAP_S`), que contradice la regla del proyecto de no mostrar números que no vengan de una medición. Los únicos huecos de clasificación reales cargados son los de Madrid 2026, hardcodeados en dos scripts.

## Decision

El escenario de la vista es Zandvoort 2026 (fecha 12, 72 vueltas), que es el circuito que el resto de la web ya usa y que tiene desgaste medido propio. Se ingiere su clasificación real de FastF1 y se reemplaza `GRID_GAP_S` por los huecos medidos. La constante inventada se elimina, no se deja como fallback.

## Alternatives Considered

- **Madrid 2026**: ya tiene clasificación real y predicción pre-registrada, pero la web no dibuja ese circuito ni tiene su desgaste medido — Madrid cae al promedio de la temporada.
- **Selector de circuito**: el producto más completo y el que multiplica ingesta, trazado y validación por cada circuito. Queda para después.
- **Escalera medida por puesto**: reemplazar 0,25 s/puesto por la distribución medida de huecos por puesto sobre las 14 fechas es un dato real y sirve para cualquier parrilla, pero es un promedio donde se puede tener el dato exacto de la carrera que se muestra.

## Consequences

Hay que escribir la ingesta de clasificación y versionar el resultado. La caché de FastF1 ya tiene la sesión, así que no hay descarga nueva ni riesgo de tocar el límite de 500 requests/hora.

## Status History

- 2026-09-17: accepted
