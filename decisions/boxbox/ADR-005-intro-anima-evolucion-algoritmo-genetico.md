---
project: boxbox
adr: 005
title: El intro anima la evolución del algoritmo genético
category: ux
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-005: El intro anima la evolución del algoritmo genético

## Context

El pedido dice «como intro cómo es que se SORTEA esa estrategia». Hay tres profundidades posibles: mostrar sólo insumos y resultado, mostrar las carreras sorteadas acumulándose en un histograma, o mostrar la población de planes evolucionando generación a generación. La materia es de algoritmos evolutivos y la defensa se evalúa sobre eso.

## Decision

El intro muestra la población convergiendo generación a generación: el mejor valor de la generación y cómo se reparte la población entre una, dos y tres paradas. Es lo que hace visible que el sistema ES un algoritmo genético y no una tabla de consulta.

## Alternatives Considered

- **Sólo insumos y resultado**: pantalla de configuración, no pieza didáctica. No muestra el algoritmo.
- **Animar las carreras sorteadas**: muestra bien la tesis del proyecto — la incertidumbre es más grande que la señal — pero no muestra el algoritmo, que es el criterio de evaluación.
- **Las dos animaciones**: el intro más didáctico y el de más trabajo; queda como extensión si sobra tiempo.

## Consequences

Depende del registro por generación introducido en ADR-003. El JSON exportado (ver ADR-002) crece: 25 generaciones por auto por escenario.

## Status History

- 2026-09-17: accepted
