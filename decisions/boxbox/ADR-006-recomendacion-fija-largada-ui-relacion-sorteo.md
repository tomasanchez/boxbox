---
project: boxbox
adr: 006
title: La recomendación es fija desde la largada y la UI declara su relación con el sorteo que muestra
category: ux
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-006: La recomendación es fija desde la largada y la UI declara su relación con el sorteo que muestra

## Context

Dos tensiones juntas. Primera: mientras la carrera animada avanza, la recomendación podría recalcularse cada vuelta, en hitos, bajo evento, o quedar fija. Segunda, y más delicada: la UI anima UN sorteo y la recomendación sale de 1.200, así que lo que se ve en pantalla puede contradecir lo que dice la tarjeta — y eso, durante una defensa, es la UI desmintiéndose a sí misma.

## Decision

La recomendación se emite en la vuelta 1 y no se recalcula: la UI muestra cómo la carrera se acerca o se aleja del plan. Y la proyección de llegada se dibuja como BANDA (media ± desvío), con la trayectoria del sorteo en curso encima, más un botón para volver a sortear con otra semilla.

## Alternatives Considered

- **Recalcular cada vuelta**: 72 x 20 búsquedas de 1.200 sorteos. Bajar `draws` para que entre tiene un riesgo ya medido: por debajo de 1.200 la búsqueda sale peor que una regla simple.
- **Recalcular bajo evento**: es lo que hace un muro de boxes real y es lo más interesante, pero multiplica el precálculo por escenarios condicionales. Queda para la Entrega 2 junto al agente de refuerzo.
- **Sólo un rótulo «una de 1.200 carreras»**: barato y honesto, pero no ayuda a leer si la carrera que se está viendo es normal o rara.

## Consequences

El botón de re-sorteo convierte la contradicción en la demostración de la tesis: tirás los dados otra vez y sale distinto. La banda obliga a exportar el desvío, que `Search` ya calcula (ver ADR-003).

## Status History

- 2026-09-17: accepted
