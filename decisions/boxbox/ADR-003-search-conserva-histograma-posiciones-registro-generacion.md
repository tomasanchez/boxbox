---
project: boxbox
adr: 003
title: Search conserva el histograma de posiciones y un registro por generación
category: architecture
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-003: Search conserva el histograma de posiciones y un registro por generación

## Context

Dos cosas que la feature necesita y que hoy el optimizador tira. (1) Las muestras de posición de llegada: se usan para `mean_position` y `sd_position` y después se descartan, así que no hay con qué calcular P(podio) — necesario para ADR-001. (2) La historia de la evolución: `optimise()` no guarda nada por generación, así que no se puede mostrar la población convergiendo — necesario para el intro didáctico (ver ADR-005).

## Decision

Se agrega a `Search` el histograma de puestos de llegada de las carreras sorteadas con el plan ganador, y un registro por generación con el mejor valor y la distribución de cantidad de paradas de la población. La instrumentación es opcional y apagada por defecto, para no pagar memoria en las miles de llamadas que no la necesitan.

## Alternatives Considered

- **Recalcular el histograma aparte**: correr otra vez las 1.200 carreras después de la búsqueda duplica cómputo y, si no se usan los mismos sorteos, da un número distinto del que eligió el plan.
- **Un callback por generación**: más flexible pero más invasivo; un registro opcional alcanza para el caso de uso y es más fácil de exportar.

## Consequences

Toca el archivo central del proyecto, que ya tiene resultados publicados en el informe. El cambio tiene que ser retrocompatible: los defaults deben dar exactamente lo de antes, y hay que verificar que los tres cuadernos y los scripts dependientes sigan corriendo (ver riesgo declarado en ADR-008).

## Status History

- 2026-09-17: accepted
