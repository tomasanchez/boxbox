---
project: boxbox
adr: 008
title: Riesgos asumidos de la vista pre-carrera
category: risks
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-008: Riesgos asumidos de la vista pre-carrera

## Context

La feature toca el archivo central del proyecto, agrega una tercera vista a un armazón que no tiene router, y publica números nuevos en pantalla en un trabajo cuya honestidad es criterio de evaluación.

## Decision

Se asumen y se declaran: (1) tocar `strategy.py`, que tiene resultados ya publicados en el informe, exige verificar que los tres cuadernos y todos los scripts dependientes sigan corriendo con los defaults intactos (ver ADR-003); (2) el repo pasa a tener dos convenciones de ADR conviviendo, `decisions/boxbox/` y `apps/api/docs/adr/`, y no se unifican en esta iteración; (3) `apps/web` no tiene script `test` aunque el Makefile invoca `pnpm test`, así que la lógica nueva de cálculo se mantiene del lado de Python siempre que se pueda; (4) el precálculo de 20 autos con campo completo puede tardar minutos, y hay que medirlo antes de comprometer el alcance.

## Alternatives Considered

- **Unificar las dos convenciones de ADR ahora**: es una migración que no tiene que ver con esta feature y que tocaría 10+ archivos de otra aplicación.
- **Montar Vitest en `apps/web`**: justificado sólo si la feature agrega lógica de cálculo en TypeScript; la decisión de arquitectura la deja en Python (ver ADR-002).

## Consequences

Los riesgos quedan por escrito y verificables, que es lo que el informe hace con los siete errores propios ya documentados.

## Status History

- 2026-09-17: accepted
