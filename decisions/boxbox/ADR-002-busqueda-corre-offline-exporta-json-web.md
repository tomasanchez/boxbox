---
project: boxbox
adr: 002
title: La búsqueda corre offline y se exporta a JSON; la web no llama a ningún servicio
category: architecture
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-002: La búsqueda corre offline y se exporta a JSON; la web no llama a ningún servicio

## Context

Hay tres formas de que la web tenga los planes: precalcular a JSON (lo que ya se hace con `plans.ts` desde `strategy_search.py --out`), consumir `apps/api` (que existe, con arquitectura Cosmic Python y 10+ ADRs propias, pero que la web nunca usó), o reimplementar el algoritmo genético en TypeScript.

## Decision

Se extiende el patrón vigente: un script nuevo en `apps/ml/scripts` con `--out` genera el JSON pre-carrera de los 20 autos, y la web lo consume como módulo generado. La web sigue siendo estática y se abre sin levantar backend. El RE-SORTEO de la carrera sí corre en el navegador, porque `tyres.ts` ya replica las distribuciones medidas en TypeScript.

## Alternatives Considered

- **Consumir `apps/api`**: obliga a levantar dos procesos para la demo y mete ML en una arquitectura pensada para dominio. La web nunca lo consumió; hacerlo ahora es un cambio de topología que la feature no necesita.
- **Reimplementar el AG en TypeScript**: daría interactividad total y riesgo real de que la web y Python den respuestas distintas — exactamente lo que el proyecto trata de no hacer.

## Consequences

El usuario sólo puede elegir entre combinaciones precalculadas. Si más adelante se quiere elegir objetivo y apetito de riesgo en vivo, hay que precalcular el producto cartesiano o revisar esta decisión. La divergencia web/Python queda acotada al sorteo de la carrera, que ya existe y ya se aceptó.

## Status History

- 2026-09-17: accepted
